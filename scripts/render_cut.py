#!/usr/bin/env python3
"""Aplica la EDL (edl.json): une los segmentos, recuadra al formato destino y
alterna zooms (punch-in) para disimular los saltos de corte.

Uso:
  python render_cut.py work/edl.json --aspect 9:16 --punch 1.10 --out work/cut.mp4
  python render_cut.py work/edl.json --aspect 16:9 --punch 1.06 --out work/cut.mp4
  python render_cut.py work/edl.json --aspect keep --punch 1.0 --out work/cut.mp4   # solo cortar

--focus-x  posición horizontal del sujeto al pasar de horizontal a vertical (0=izq, .5=centro, 1=der)
--face-y   hacia dónde se acerca el zoom en vertical (0=arriba, .5=centro). 0.4 favorece el rostro.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

from common import probe

TARGETS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def even(v):
    return max(2, int(round(v / 2.0)) * 2)


def plan_crop(W, H, ar, focus_x, zoom, face_y):
    if W / H > ar:
        cw, ch = H * ar, H
        x0, y0 = (W - cw) * focus_x, 0.0
    else:
        cw, ch = W, W / ar
        x0, y0 = 0.0, (H - ch) * 0.5
    cw2, ch2 = cw / zoom, ch / zoom
    x = x0 + (cw - cw2) * 0.5
    y = y0 + (ch - ch2) * face_y
    cw2, ch2 = even(cw2), even(ch2)
    x = min(max(0, int(x)), W - cw2)
    y = min(max(0, int(y)), H - ch2)
    return cw2, ch2, x, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edl")
    ap.add_argument("--out", default="work/cut.mp4")
    ap.add_argument("--aspect", default="9:16", choices=list(TARGETS) + ["keep"])
    ap.add_argument("--punch", type=float, default=1.10, help="Factor de zoom en segmentos alternos (1.0 = sin zoom)")
    ap.add_argument("--focus-x", type=float, default=0.5)
    ap.add_argument("--face-y", type=float, default=0.4)
    ap.add_argument("--start-zoomed", action="store_true", help="el primer plano ya lleva zoom (más energía en el gancho)")
    ap.add_argument("--fps", type=float, help="Forzar fps de salida (por defecto, los del original)")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preset", default="medium")
    args = ap.parse_args()

    with open(args.edl, encoding="utf-8") as f:
        edl = json.load(f)
    src = edl["source"]
    info = probe(src)
    if not info["has_audio"]:
        sys.exit("El video no tiene audio.")
    W, H = info["width"], info["height"]

    if args.aspect == "keep":
        TW, TH = even(W), even(H)
        ar = W / H
    else:
        TW, TH = TARGETS[args.aspect]
        ar = TW / TH

    fade = 0.015
    fps = args.fps or info["fps"]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    tmp = os.path.splitext(args.out)[0] + "_segs"
    os.makedirs(tmp, exist_ok=True)
    segs_all = edl["segments"]
    n_segs = len(segs_all)

    if args.aspect != "keep":
        cw0, _, _, _ = plan_crop(W, H, ar, args.focus_x, 1.0, args.face_y)
        if cw0 < TW * 0.75:
            print(f"AVISO: el recorte base mide {cw0}px de ancho y se estira a {TW}px. Se verá suave; "
                  f"ideal grabar en vertical 4K/1080p o usar --aspect keep.", file=sys.stderr)

    # Se renderiza cada segmento por separado (poca memoria, sirve para videos largos) y luego se unen
    # sin recodificar. Los límites se ajustan a la rejilla de fotogramas para que audio y video no se desfasen.
    print(f"Renderizando {n_segs} segmentos -> {TW}x{TH} ...")
    list_path = os.path.join(tmp, "list.txt")
    with open(list_path, "w") as lf:
        for i, seg in enumerate(segs_all):
            frames = max(1, round((seg["end"] - seg["start"]) * fps))
            s0 = round(seg["start"] * fps) / fps
            d = frames / fps
            zoom = args.punch if ((i % 2 == 0) == args.start_zoomed) else 1.0
            cw, ch, x, y = plan_crop(W, H, ar, args.focus_x, zoom, args.face_y)
            vf = f"crop={cw}:{ch}:{x}:{y},scale={TW}:{TH}:flags=lanczos,setsar=1,fps={fps:.5f}"
            # en cortes de zoom "continuos" el audio no se interrumpe: sin micro-fundidos en esa unión
            fade_in = "" if seg.get("continuous") else f",afade=t=in:d={fade}"
            nxt_cont = i + 1 < n_segs and segs_all[i + 1].get("continuous")
            fade_out = "" if nxt_cont else f",afade=t=out:st={max(0, d - fade):.3f}:d={fade}"
            af = f"aresample=48000{fade_in}{fade_out}"
            seg_file = os.path.join(tmp, f"seg_{i:03d}.mkv")
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{s0:.4f}", "-t", f"{d:.4f}",
                            "-i", src, "-vf", vf, "-af", af, "-frames:v", str(frames), "-c:v", "libx264", "-preset", args.preset,
                            "-crf", str(args.crf), "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", seg_file], check=True)
            lf.write(f"file '{os.path.abspath(seg_file)}'\n")
            print(f"  segmento {i + 1}/{n_segs} listo")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list_path,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", args.out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    out = probe(args.out)
    print(f"OK: {args.out}  ({out['width']}x{out['height']}, {out['duration']:.1f}s)")


if __name__ == "__main__":
    main()
