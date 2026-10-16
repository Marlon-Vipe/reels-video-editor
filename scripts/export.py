#!/usr/bin/env python3
"""Exportación final: colorización ligera, cutaways (B-roll/tarjetas), subtítulos y overlays (.ass),
logo, efectos de sonido, música con ducking, normalización de volumen y codificación para publicar.

Uso:
  python export.py work/cut.mp4 --ass work/captions.ass work/overlays.ass --out final/reel.mp4
  python export.py work/cut.mp4 --ass work/captions.ass --grade \
      --broll work/cards/caida.mp4@0.3 --broll work/cards/alianza.mp4@28.6 \
      --sfx work/sfx/whoosh.wav@0.3 --sfx work/sfx/ding.wav@30.0@-10 \
      --music assets/music.mp3 --music-db -24 --out final/reel.mp4

--broll clip@inicio   clip de video (ideal 1080x1920) que TAPA la imagen desde `inicio` (s del video ya cortado)
                      durante su duración; la voz sigue. Si existe <clip>.matte.mp4 (lo crea make_cards.py) se usa como
                      transparencia animada (transiciones incluidas); si no, entra y sale con fundido de 0.12 s.
                      Los stickers (fondo transparente) se colocan igual, se pueden solapar con el video base.
--sfx archivo@t[@dB]  efecto de sonido en el segundo t, con volumen relativo en dB (por defecto -14).
El orden de --ass importa: los primeros quedan debajo, los últimos encima. Los subtítulos se queman
DESPUÉS de los cutaways, así que siempre se ven encima.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile

from common import probe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--ass", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--fonts-dir", help="carpeta con fuentes .ttf/.otf de la marca")
    ap.add_argument("--grade", action="store_true", help="colorización ligera (contraste, saturación, nitidez)")
    ap.add_argument("--broll", action="append", default=[], help="clip@inicio (repetible)")
    ap.add_argument("--sfx", action="append", default=[], help="archivo@t[@dB] (repetible)")
    ap.add_argument("--logo")
    ap.add_argument("--logo-pos", choices=["tl", "tr", "bl", "br"], default="tl")
    ap.add_argument("--logo-width", type=float, default=0.14, help="ancho del logo como fracción del ancho del video")
    ap.add_argument("--music")
    ap.add_argument("--music-db", type=float, default=-22.0, help="volumen de la música antes del ducking (dB)")
    ap.add_argument("--no-duck", action="store_true")
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--no-loudnorm", action="store_true")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preset", default="medium")
    args = ap.parse_args()

    info = probe(args.video)
    W, H, dur = info["width"], info["height"], info["duration"]
    video = os.path.abspath(args.video)
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    tmp = tempfile.mkdtemp(prefix="export_")
    try:
        ass_names = []
        for i, a in enumerate(args.ass):
            name = f"sub{i}.ass"
            shutil.copy(a, os.path.join(tmp, name))
            ass_names.append(name)

        inputs = ["-i", video]
        idx = 1

        def add_input(path):
            nonlocal idx
            inputs.extend(["-i", os.path.abspath(path)])
            idx += 1
            return idx - 1

        f = []
        vlabel = "[0:v]"
        if args.grade:
            f.append(f"{vlabel}eq=contrast=1.05:saturation=1.12:gamma=1.0,unsharp=5:5:0.5:5:5:0.0[vg]")
            vlabel = "[vg]"

        # --- cutaways (B-roll / tarjetas) ---
        for n, spec in enumerate(args.broll):
            path, _, start = spec.rpartition("@")
            a = float(start)
            k = add_input(path)
            d = probe(path)["duration"]
            matte = path[:-4] + ".matte.mp4" if path.endswith(".mp4") else None
            if matte and os.path.exists(matte):
                # tarjeta con transparencia animada (iris, cortinas, glitch...) hecha por make_cards.py
                km = add_input(matte)
                f.append(f"[{k}:v]format=yuv420p[cc{n}];[{km}:v]format=gray[mm{n}];"
                         f"[cc{n}][mm{n}]alphamerge,setpts=PTS-STARTPTS+{a}/TB[bk{n}]")
            else:
                f.append(f"[{k}:v]format=yuva420p,fade=t=in:st=0:d=0.12:alpha=1,"
                         f"fade=t=out:st={max(0.0, d - 0.15):.3f}:d=0.15:alpha=1,setpts=PTS-STARTPTS+{a}/TB[bk{n}]")
            f.append(f"{vlabel}[bk{n}]overlay=enable='between(t,{a},{a + d:.3f})':eof_action=pass[vb{n}]")
            vlabel = f"[vb{n}]"

        # --- subtítulos y overlays ---
        fd = f":fontsdir={os.path.abspath(args.fonts_dir)}" if args.fonts_dir else ""
        if ass_names:
            f.append(f"{vlabel}" + ",".join(f"ass={n}{fd}" for n in ass_names) + "[vs]")
            vlabel = "[vs]"

        # --- logo ---
        if args.logo:
            k = add_input(args.logo)
            m = int(min(W, H) * 0.04)
            pos = {"tl": f"x={m}:y={m}", "tr": f"x=W-w-{m}:y={m}", "bl": f"x={m}:y=H-h-{m}", "br": f"x=W-w-{m}:y=H-h-{m}"}[args.logo_pos]
            f.append(f"[{k}:v]scale={int(W * args.logo_width)}:-1,format=rgba[lg]")
            f.append(f"{vlabel}[lg]overlay={pos}[vl]")
            vlabel = "[vl]"

        # --- audio: voz (+ música con ducking) (+ efectos) + loudnorm de dos pasadas ---
        fa = []
        fade_out = max(0.0, dur - 1.5)
        alabel = "[0:a]"
        if args.music:
            k = add_input(args.music)
            fa.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,aloop=loop=-1:size=2000000000,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                      f"volume={args.music_db}dB,afade=t=in:d=1,afade=t=out:st={fade_out:.3f}:d=1.5[mus]")
            if args.no_duck:
                fa.append("[0:a][mus]amix=inputs=2:duration=first:dropout_transition=0,volume=2[mix]")
            else:
                fa.append("[0:a]asplit=2[vo][sc]")
                fa.append("[mus][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=450[duck]")
                fa.append("[vo][duck]amix=inputs=2:duration=first:dropout_transition=0,volume=2[mix]")
            alabel = "[mix]"
        if args.sfx:
            labels = []
            for n, spec in enumerate(args.sfx):
                parts = spec.split("@")
                path, t = parts[0], float(parts[1])
                db = float(parts[2]) if len(parts) > 2 else -14.0
                k = add_input(path)
                ms = int(max(0.0, t) * 1000)
                fa.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={ms}|{ms},volume={db}dB,apad=whole_dur={dur:.3f}[sx{n}]")
                labels.append(f"[sx{n}]")
            fa.append(f"{alabel}aformat=sample_rates=48000:channel_layouts=stereo[base]")
            n_in = 1 + len(labels)
            fa.append(f"[base]{''.join(labels)}amix=inputs={n_in}:duration=first:dropout_transition=0,volume={n_in}[sfxmix]")
            alabel = "[sfxmix]"
        if args.no_loudnorm:
            fa.append(f"{alabel}anull[aout]")
        else:
            target = f"I={args.lufs}:TP=-1.5:LRA=11"
            # pasada 1: medir (solo audio, rápido)
            m1 = subprocess.run(["ffmpeg", "-hide_banner", "-nostats"] + inputs + [
                "-filter_complex", ";".join(fa + [f"{alabel}loudnorm={target}:print_format=json[aout]"]),
                "-map", "[aout]", "-f", "null", "-"], capture_output=True, text=True, cwd=tmp)
            mj = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", m1.stderr, re.S)
            if mj:
                mv = json.loads(mj.group(0))
                fa.append(f"{alabel}loudnorm={target}:measured_I={mv['input_i']}:measured_LRA={mv['input_lra']}:"
                          f"measured_TP={mv['input_tp']}:measured_thresh={mv['input_thresh']}:offset={mv['target_offset']}:linear=true[aout]")
            else:  # si no se pudo medir, una sola pasada
                fa.append(f"{alabel}loudnorm={target}[aout]")
        f.append(f"{vlabel}null[vout]")
        f.extend(fa)

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats"] + inputs + [
            "-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out,
        ]
        subprocess.run(cmd, check=True, cwd=tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    o = probe(out)
    print(f"OK: {args.out}  ({o['width']}x{o['height']}, {o['duration']:.1f}s, {os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
