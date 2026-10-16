#!/usr/bin/env python3
"""Transcribe un video con timestamps por palabra (faster-whisper).

Salidas en --out-dir:
  words.json            -> {"language","duration","words":[{"word","start","end"}]}
  transcript.txt        -> una línea por frase: [inicio-fin] texto
  transcript_indexed.txt-> texto con el índice de cada palabra: hola(0) a(1) todos(2)
                           (sirve para elegir rangos a cortar con build_edl.py --cut-words)

Uso:
  python transcribe.py video.mp4 --out-dir work --lang es --model medium \
      --prompt "<nombres propios: tu nombre, tu marca, herramientas que mencionas>"
"""
import argparse
import json
import os
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out-dir", default="work")
    ap.add_argument("--lang", default="es")
    ap.add_argument("--model", default="medium",
                    help="tiny/base/small/medium/large-v3. En CPU: small o medium. Con GPU: large-v3")
    ap.add_argument("--prompt", default="", help="Vocabulario de marca para mejorar ortografía de nombres propios")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--compute-type", default="auto")
    ap.add_argument("--no-vad", action="store_true", help="Desactiva el filtro VAD")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    wav = os.path.join(args.out_dir, "audio.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", args.video, "-vn", "-ac", "1", "-ar", "16000", wav],
        check=True,
    )

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("Falta faster-whisper. Instala con:  pip install faster-whisper --break-system-packages\n"
                 "(o sin el flag en tu propia máquina). Alternativa: openai-whisper o la API de transcripción.")

    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    segments, info = model.transcribe(
        wav,
        language=args.lang,
        word_timestamps=True,
        vad_filter=not args.no_vad,
        vad_parameters={"min_silence_duration_ms": 300},
        initial_prompt=args.prompt or None,
        condition_on_previous_text=False,
    )

    words, lines, indexed = [], [], []
    for seg in segments:
        seg_words = []
        for w in seg.words or []:
            token = w.word.strip()
            if not token:
                continue
            words.append({"word": token, "start": round(w.start, 3), "end": round(w.end, 3)})
            seg_words.append(f"{token}({len(words) - 1})")
        lines.append(f"[{seg.start:7.2f}-{seg.end:7.2f}] {seg.text.strip()}")
        indexed.append(f"[{seg.start:7.2f}] " + " ".join(seg_words))

    with open(os.path.join(args.out_dir, "words.json"), "w", encoding="utf-8") as f:
        json.dump({"language": info.language, "duration": round(info.duration, 3), "words": words},
                  f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out_dir, "transcript.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(args.out_dir, "transcript_indexed.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(indexed) + "\n")

    print(f"OK: {len(words)} palabras, {info.duration:.1f}s, idioma={info.language}")
    print(f"Archivos en {args.out_dir}/: words.json, transcript.txt, transcript_indexed.txt")


if __name__ == "__main__":
    main()
