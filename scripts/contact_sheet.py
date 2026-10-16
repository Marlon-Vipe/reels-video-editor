#!/usr/bin/env python3
"""Genera una hoja de contactos (un solo JPG con fotogramas) para revisar el video de un vistazo.

Uso:
  python contact_sheet.py final/reel.mp4 --every 3 --cols 5 --out qa/sheet.jpg
  python contact_sheet.py final/reel.mp4 --at 0.5,2,10.5 --out qa/frames.jpg   # momentos específicos
"""
import argparse
import os
import subprocess

from common import probe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--every", type=float, default=3.0, help="un fotograma cada N segundos")
    ap.add_argument("--at", help="lista de segundos separados por coma (ignora --every)")
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--thumb-width", type=int, default=270)
    ap.add_argument("--out", default="qa/sheet.jpg")
    args = ap.parse_args()

    info = probe(args.video)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    tw = args.thumb_width
    if args.at:
        times = [float(x) for x in args.at.split(",")]
        tmp = os.path.splitext(args.out)[0] + "_tmp"
        os.makedirs(tmp, exist_ok=True)
        files = []
        for i, t in enumerate(times):
            fp = os.path.join(tmp, f"f{i:03d}.png")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", args.video,
                            "-frames:v", "1", fp], check=True)
            files.append(fp)
        rows = (len(files) + args.cols - 1) // args.cols
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", "1", "-i", os.path.join(tmp, "f%03d.png"),
               "-vf", f"scale={tw}:-1,tile={args.cols}x{rows}", "-frames:v", "1", args.out]
    else:
        n = max(1, int(info["duration"] / args.every))
        rows = (n + args.cols - 1) // args.cols
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", args.video,
               "-vf", f"fps=1/{args.every},scale={tw}:-1,tile={args.cols}x{rows}", "-frames:v", "1", args.out]
    subprocess.run(cmd, check=True)
    print(f"OK: {args.out}")


if __name__ == "__main__":
    main()
