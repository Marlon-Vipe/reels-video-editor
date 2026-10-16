#!/usr/bin/env python3
"""Segunda hipótesis de TEXTO con Whisper (vía sherpa-onnx, modelo desde GitHub Releases; no usa Hugging Face).
No da tiempos por palabra: sirve para CORREGIR el texto del respaldo CTC (transcribe_sherpa.py), que sí tiene tiempos reales.

Uso:
  pip install sherpa-onnx --break-system-packages
  python transcribe_whisper_sherpa.py work/audio.wav [--model sherpa-onnx-whisper-small] [--chunk 25]
Imprime el texto por bloques de ~25 s. Compáralo con work/transcript_indexed.txt y arma edits.json para fix_words.py.
Modelos: sherpa-onnx-whisper-small (~640 MB, buen equilibrio), sherpa-onnx-whisper-base (más rápido, menos fino),
sherpa-onnx-whisper-medium (más fino y lento). Cuando CTC y Whisper discrepan en una frase, cuenta las sílabas de cada
versión contra el tiempo real de esa frase (la que no cabe en el tiempo está mal) y marca lo incierto en tu entrega.
"""
import argparse
import os
import tarfile
import urllib.request
import wave

import numpy as np
import sherpa_onnx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav", help="WAV mono 16 kHz (work/audio.wav lo deja transcribe_sherpa.py)")
    ap.add_argument("--model", default="sherpa-onnx-whisper-small")
    ap.add_argument("--chunk", type=float, default=25.0)
    ap.add_argument("--lang", default="es")
    args = ap.parse_args()
    d = os.path.expanduser(f"~/.cache/sherpa-models/{args.model}")
    if not os.path.isdir(d):
        os.makedirs(os.path.dirname(d), exist_ok=True)
        arc = d + ".tar.bz2"
        print(f"Descargando {args.model} desde GitHub Releases...")
        urllib.request.urlretrieve(f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{args.model}.tar.bz2", arc)
        tarfile.open(arc).extractall(os.path.dirname(d))
        os.remove(arc)
    files = os.listdir(d)
    pick = lambda suf: next(f for f in files if f.endswith(suf))
    enc = next((f for f in files if f.endswith("encoder.int8.onnx")), None) or pick("encoder.onnx")
    dec = next((f for f in files if f.endswith("decoder.int8.onnx")), None) or pick("decoder.onnx")
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(encoder=f"{d}/{enc}", decoder=f"{d}/{dec}", tokens=f"{d}/{pick('tokens.txt')}",
                                                     language=args.lang, task="transcribe", num_threads=4)
    w = wave.open(args.wav)
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    sr, step = w.getframerate(), int(args.chunk * w.getframerate())
    for a in range(0, len(x), step):
        s = rec.create_stream()
        s.accept_waveform(sr, x[a:a + step])
        rec.decode_stream(s)
        print(f"[{a / sr:5.1f}] {s.result.text.strip()}")


if __name__ == "__main__":
    main()
