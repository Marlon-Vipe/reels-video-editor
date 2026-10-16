#!/usr/bin/env python3
"""Construye la lista de cortes (EDL) de un video hablado: quita silencios y
tomas malas, y remapea los timestamps de las palabras a la nueva línea de tiempo.

Uso típico:
  python build_edl.py video.mp4 --words work/words.json --preset reels --out-dir work
  python build_edl.py video.mp4 --words work/words.json --preset youtube \
      --cut-words 41-47 --cut 95.2-97.0 --keep 30.1-31.0 --cut-fillers
  python build_edl.py largo.mp4 --words work/words.json --preset reels --trim 120-175   # clip para Reel/Short

Presets (se pueden sobrescribir con las opciones individuales):
  reels   : pausas > 0.28s se recortan; queda ~0.14s de respiro  (ritmo rápido)
  youtube : pausas > 0.50s se recortan; queda ~0.30s de respiro  (ritmo natural)

Salidas en --out-dir:
  edl.json         segmentos a conservar {start,end,out_start} en tiempo del original
  words_cut.json   palabras con tiempos en el video ya cortado (para subtítulos)
"""
import argparse
import json
import os
import re
import subprocess
import sys

from common import norm_word, parse_range_list, probe

PRESETS = {
    "reels":   dict(noise=-32.0, min_silence=0.28, pad_before=0.05, pad_after=0.09),
    "youtube": dict(noise=-34.0, min_silence=0.50, pad_before=0.12, pad_after=0.18),
}
FILLERS = {"eh", "ehh", "ehhh", "em", "emm", "mm", "mmm", "hmm", "um", "umm", "uh", "ah", "ahh"}


def detect_silences(path, noise_db, min_dur, duration):
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn",
           "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", r.stderr)]
    sil = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else duration
        sil.append([max(0.0, s), min(duration, e)])
    return sil


def complement(silences, duration):
    speech, cur = [], 0.0
    for s, e in silences:
        if s - cur > 0.001:
            speech.append([cur, s])
        cur = max(cur, e)
    if duration - cur > 0.001:
        speech.append([cur, duration])
    return speech


def merge(segs, gap=0.0):
    segs = sorted(segs)
    out = []
    for s, e in segs:
        if out and s - out[-1][1] <= gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def subtract(segs, cuts):
    for cs, ce in cuts:
        new = []
        for s, e in segs:
            if ce <= s or cs >= e:
                new.append([s, e])
                continue
            if cs > s:
                new.append([s, cs])
            if ce < e:
                new.append([ce, e])
        segs = new
    return segs


def remap_words(words, segments):
    """Palabras -> línea de tiempo del video cortado. Una palabra cuya marca cae en una parte eliminada NO se
    descarta (el subtítulo perdería texto): se pega al borde del segmento más cercano."""
    out = []
    for i, w in enumerate(words):
        mid = (w["start"] + w["end"]) / 2
        hit = None
        for seg in segments:
            if seg["start"] <= mid <= seg["end"]:
                hit = seg
                break
        if hit:
            length = hit["end"] - hit["start"]
            ns = hit["out_start"] + max(0.0, w["start"] - hit["start"])
            ne = hit["out_start"] + min(length, w["end"] - hit["start"])
        else:
            near = min(segments, key=lambda sg: min(abs(mid - sg["start"]), abs(mid - sg["end"])))
            edge_start = abs(mid - near["start"]) < abs(mid - near["end"])
            ns = near["out_start"] if edge_start else near["out_start"] + (near["end"] - near["start"]) - 0.08
            ne = ns + 0.08
        if ne <= ns:
            ne = ns + 0.05
        out.append({**w, "start": round(ns, 3), "end": round(ne, 3), "src_index": i})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--words", help="words.json de transcribe.py (para remapear subtítulos y cortar por palabra)")
    ap.add_argument("--preset", choices=PRESETS.keys(), default="reels")
    ap.add_argument("--noise", type=float, help="Umbral de silencio en dB (más negativo = más estricto)")
    ap.add_argument("--min-silence", type=float, help="Duración mínima de pausa a recortar (s)")
    ap.add_argument("--pad-before", type=float, help="Aire que se conserva antes de cada frase (s)")
    ap.add_argument("--pad-after", type=float, help="Aire que se conserva después de cada frase (s)")
    ap.add_argument("--min-keep", type=float, default=0.15, help="Descarta fragmentos más cortos que esto (s)")
    ap.add_argument("--cut", default="", help="Rangos extra a eliminar, tiempo original: '12.5-14,40-41.2'")
    ap.add_argument("--cut-words", default="", help="Rangos de índices de palabras a eliminar: '12-15,40-41'")
    ap.add_argument("--keep", default="", help="Rangos a proteger (pausas dramáticas): '30.1-31.0'")
    ap.add_argument("--zoom-cuts", type=float, default=0.0,
                    help="Segundos objetivo entre cambios de plano SIN quitar contenido: parte los segmentos largos "
                         "en límites de frase/cláusula para alternar el zoom (ej. 4). Útil si casi no hay pausas.")
    ap.add_argument("--trim", default="", help="Solo procesar esta ventana del original, ej. '120-175' (para sacar un Short/Reel de un video largo)")
    ap.add_argument("--cut-fillers", action="store_true", help="Elimina muletillas aisladas (eh, mmm, um...)")
    ap.add_argument("--out-dir", default="work")
    args = ap.parse_args()

    p = dict(PRESETS[args.preset])
    for k in ("noise", "min_silence", "pad_before", "pad_after"):
        v = getattr(args, k)
        if v is not None:
            p[k] = v

    info = probe(args.video)
    if not info["has_audio"]:
        sys.exit("El video no tiene audio; no hay nada que detectar.")
    dur = info["duration"]
    window = dur

    silences = detect_silences(args.video, p["noise"], p["min_silence"], dur)
    speech = complement(silences, dur)
    padded = [[max(0.0, s - p["pad_before"]), min(dur, e + p["pad_after"])] for s, e in speech]
    padded += parse_range_list(args.keep)
    segs = merge(padded)

    words = []
    if args.words:
        with open(args.words, encoding="utf-8") as f:
            words = json.load(f)["words"]

    cuts = parse_range_list(args.cut)
    for a, b in parse_range_list(args.cut_words):
        a, b = int(a), int(b)
        if words and 0 <= a <= b < len(words):
            cuts.append([words[a]["start"] - 0.02, words[b]["end"] + 0.02])
        else:
            print(f"AVISO: rango de palabras {a}-{b} fuera de rango o sin --words; ignorado", file=sys.stderr)
    if args.cut_fillers:
        for w in words:
            if norm_word(w["word"]) in FILLERS:
                cuts.append([w["start"] - 0.02, w["end"] + 0.03])

    segs = subtract(segs, cuts)
    if args.trim:
        (ta, tb), = parse_range_list(args.trim)
        window = min(tb, dur) - max(ta, 0.0)
        segs = [[max(s, ta), min(e, tb)] for s, e in segs if e > ta and s < tb]
    segs = merge([s for s in segs if s[1] - s[0] >= args.min_keep], gap=0.04)
    if not segs:
        sys.exit("Todos los segmentos fueron eliminados. Sube el umbral --noise (ej. -28) o revisa los cortes.")

    pieces = [(s, e, False) for s, e in segs]
    if args.zoom_cuts > 0:
        if not words:
            print("AVISO: --zoom-cuts necesita --words; ignorado", file=sys.stderr)
        else:
            pieces = []
            for s, e in segs:
                cands = []  # (tiempo de corte) en el hueco tras palabras con puntuación
                for i, w in enumerate(words[:-1]):
                    if re.search(r"[.?!,;:…]$", w["word"]) and s + 1.2 < w["end"] < e - 1.2:
                        cands.append((w["end"] + words[i + 1]["start"]) / 2)
                last, cuts_here = s, []
                for c in cands:
                    if c - last >= args.zoom_cuts * 0.85 and e - c >= 1.2:
                        cuts_here.append(c)
                        last = c
                bounds = [s] + cuts_here + [e]
                for k in range(len(bounds) - 1):
                    pieces.append((bounds[k], bounds[k + 1], k > 0))
    edl_segments, t = [], 0.0
    for s, e, cont in pieces:
        edl_segments.append({"start": round(s, 3), "end": round(e, 3), "out_start": round(t, 3), "continuous": cont})
        t += e - s

    os.makedirs(args.out_dir, exist_ok=True)
    edl = {
        "source": os.path.abspath(args.video),
        "source_duration": round(dur, 3),
        "duration": round(t, 3),
        "params": {**p, "preset": args.preset, "extra_cuts": cuts},
        "segments": edl_segments,
    }
    with open(os.path.join(args.out_dir, "edl.json"), "w", encoding="utf-8") as f:
        json.dump(edl, f, indent=1)
    if words:
        with open(os.path.join(args.out_dir, "words_cut.json"), "w", encoding="utf-8") as f:
            json.dump({"duration": round(t, 3), "words": remap_words(words, edl_segments)},
                      f, ensure_ascii=False, indent=1)

    removed = window - t
    avg = t / len(edl_segments)
    label = "Ventana" if args.trim else "Original"
    print(f"{label}: {window:.1f}s  ->  Editado: {t:.1f}s  (se eliminó {removed:.1f}s = {100 * removed / window:.0f}%)")
    print(f"Segmentos: {len(edl_segments)}  |  duración media por segmento: {avg:.1f}s")
    print(f"Parámetros: {p}")
    if removed / window < 0.03:
        print("AVISO: casi no se quitó nada. Si hay ruido de fondo, sube --noise (ej. -28) o baja --min-silence.")
    if removed / window > 0.45:
        print("AVISO: se quitó más del 45%. Puede que el umbral corte voz suave: baja --noise (ej. -38).")
    if avg < 1.0:
        print("AVISO: segmentos muy cortos (<1s de media): el video puede sentirse entrecortado.")
    print(f"Guardado: {args.out_dir}/edl.json" + (" y words_cut.json" if words else ""))


if __name__ == "__main__":
    main()
