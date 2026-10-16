#!/usr/bin/env python3
"""Transcripción de respaldo con TIEMPOS POR PALABRA REALES, sin Hugging Face.

Usa sherpa-onnx + un modelo NeMo FastConformer CTC en español descargado de GitHub Releases.
Un modelo CTC emite el momento en que suena cada token (resolución ~80 ms), así que los
subtítulos quedan sincronizados con la voz. A cambio, el texto es menos fino que el de Whisper:
comete errores en nombres propios, marcas y modismos. Por eso el flujo es:

  1) python transcribe_sherpa.py video.mp4 --out-dir work
  2) leer work/transcript_indexed.txt y corregir el texto con fix_words.py
     (las correcciones conservan los tiempos reales)

Uso:
  pip install sherpa-onnx
  python transcribe_sherpa.py video.mp4 --out-dir work [--lead 0.06]

Salidas (mismo formato que transcribe.py): words.json, transcript.txt, transcript_indexed.txt
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import urllib.request
import wave

MODEL_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{m}.tar.bz2"
DEFAULT_MODEL = "sherpa-onnx-nemo-fast-conformer-ctc-es-1424"  # solo español
PUNCT_END = re.compile(r"^[.,;:?!…]+$")      # cierra la palabra anterior
PUNCT_OPEN = re.compile(r"^[¿¡]+$")           # abre la palabra siguiente


def silences(wav, noise=-38, dur=0.15):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af",
                        f"silencedetect=noise={noise}dB:d={dur}", "-f", "null", "-"], capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", r.stderr)]
    return [[max(0.0, s), en[i] if i < len(en) else 1e9] for i, s in enumerate(st)]


def chunk_points(sil, total, max_len=90.0, min_len=20.0):
    pts, start = [0.0], 0.0
    mids = [(s + min(e, total)) / 2 for s, e in sil if s > 0.5 and min(e, total) < total - 0.5]
    while total - start > max_len:
        cands = [m for m in mids if start + min_len < m <= start + max_len]
        start = cands[-1] if cands else start + max_len
        pts.append(start)
    pts.append(total)
    return pts


def ensure_model(name, model_dir):
    d = os.path.join(model_dir, name)
    if not os.path.isdir(d):
        os.makedirs(model_dir, exist_ok=True)
        arc = os.path.join(model_dir, name + ".tar.bz2")
        print(f"Descargando {name} desde GitHub Releases (~430 MB)...")
        urllib.request.urlretrieve(MODEL_URL.format(m=name), arc)
        with tarfile.open(arc) as t:
            t.extractall(model_dir)
        os.remove(arc)
    return d


def tokens_to_words(tokens, stamps, offset, lead):
    words, cur, prefix = [], None, ""
    for tok, t in zip(tokens, stamps):
        t = t + offset
        if PUNCT_END.match(tok.strip()) and cur:
            cur["word"] += tok.strip()
            continue
        if PUNCT_OPEN.match(tok.strip()):
            prefix = tok.strip()
            continue
        if tok.startswith(" ") or cur is None or prefix:
            if cur:
                words.append(cur)
            cur = {"word": prefix + tok.strip(), "start": t, "last": t}
            prefix = ""
        else:
            cur["word"] += tok
            cur["last"] = t
    if cur:
        words.append(cur)
    out = []
    for i, w in enumerate(words):
        nxt = words[i + 1]["start"] if i + 1 < len(words) else None
        s = max(0.0, w["start"] - lead)
        natural = w["last"] + 0.16 - lead
        e = natural if nxt is None else min(natural + 0.1, max(nxt - lead - 0.02, s + 0.08))
        out.append({"word": w["word"], "start": round(s, 3), "end": round(max(e, s + 0.08), 3)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out-dir", default="work")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--model-dir", default=os.path.expanduser("~/.cache/sherpa-models"))
    ap.add_argument("--lead", type=float, default=0.06,
                    help="adelanta cada palabra N s: el pico del CTC cae un poco después del inicio real")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    wav = os.path.join(args.out_dir, "audio.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", args.video, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    with wave.open(wav) as wf:
        sr, n = wf.getframerate(), wf.getnframes()
        total = n / sr
    try:
        import numpy as np
        import sherpa_onnx
    except ImportError:
        sys.exit("Falta sherpa-onnx:  pip install sherpa-onnx (--break-system-packages en el sandbox)")
    d = ensure_model(args.model, args.model_dir)
    rec = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(model=f"{d}/model.onnx", tokens=f"{d}/tokens.txt",
                                                      num_threads=os.cpu_count() or 2)
    with wave.open(wav) as wf:
        x = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768

    words = []
    pts = chunk_points(silences(wav), total)
    for a, b in zip(pts[:-1], pts[1:]):
        st = rec.create_stream()
        st.accept_waveform(sr, x[int(a * sr):int(b * sr)])
        rec.decode_stream(st)
        r = st.result
        words += tokens_to_words(list(r.tokens), list(r.timestamps), a, args.lead)
        print(f"  bloque {a:.0f}-{b:.0f}s listo")

    lines, indexed, cur, cur_idx = [], [], [], []
    for i, w in enumerate(words):
        cur.append(w["word"]); cur_idx.append(f"{w['word']}({i})")
        if re.search(r"[.?!]$", w["word"]) or i == len(words) - 1:
            t0 = words[i - len(cur) + 1]["start"]
            lines.append(f"[{t0:7.2f}] " + " ".join(cur))
            indexed.append(f"[{t0:7.2f}] " + " ".join(cur_idx))
            cur, cur_idx = [], []
    json.dump({"language": "es", "duration": round(total, 3), "timing": "ctc", "words": words},
              open(os.path.join(args.out_dir, "words.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(args.out_dir, "transcript.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    open(os.path.join(args.out_dir, "transcript_indexed.txt"), "w", encoding="utf-8").write("\n".join(indexed) + "\n")
    print(f"OK: {len(words)} palabras con tiempos reales (CTC), {total:.1f}s")


if __name__ == "__main__":
    main()
