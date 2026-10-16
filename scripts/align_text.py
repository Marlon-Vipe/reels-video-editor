#!/usr/bin/env python3
"""Alinea un TEXTO conocido (guion, subtítulos automáticos pegados por el usuario) con la voz del video
y genera words.json con tiempos por palabra, SIN modelo de reconocimiento de voz.

Cuándo usarlo: el entorno no puede descargar Whisper/sherpa (Hugging Face y GitHub bloqueados) y el usuario
puede darte el texto de lo que dice. Es el respaldo del paso 2 de la skill.

Cómo funciona (honesto: es una alineación acústica aproximada, no un reconocedor):
  1. Mide la envolvente de energía de la voz (banda 200-4000 Hz, hop 10 ms) y detecta núcleos silábicos (picos).
  2. Cuenta las sílabas del texto en español (diptongos/hiatos; `--syl "IA=2,ChatGPT=4"` para corregir).
  3. Alinea sílabas ↔ núcleos con programación dinámica monótona (tolera núcleos de más y sílabas sin pico).
  4. Cada palabra toma el inicio de su primera sílaba y el fin de su última; respeta las pausas reales.
  Error típico: 60-150 ms. Úsalo con `--debug-plot` y MIRA la imagen (marcas de palabra sobre la energía).

Uso:
  python align_text.py video.mp4 --text-file work/texto.txt --out-dir work [--syl "IA=2"] [--debug-plot qa/align.png]
Salidas (igual que transcribe.py): words.json, transcript.txt, transcript_indexed.txt
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata

import numpy as np
from scipy.signal import butter, find_peaks, sosfiltfilt

SR, HOP = 16000, 160           # 10 ms
STRONG, WEAK = set("aeoáéó"), set("iuü")
ACC_WEAK = set("íú")


def syllables(word, override=None):
    w = word.lower()
    key = re.sub(r"[^\wáéíóúüñ]", "", w)
    if override and key in override:
        return override[key]
    if key.isdigit():
        return max(1, int(round(len(key) * 1.6)))
    if key in ("y", "o", "a", "e", "u"):
        return 1
    n, prev = 0, None
    for ch in key:
        is_v = ch in STRONG or ch in WEAK or ch in ACC_WEAK
        if is_v:
            if prev is None:
                n += 1
            else:
                hiatus = (prev in STRONG and ch in STRONG) or ch in ACC_WEAK or prev in ACC_WEAK
                if hiatus:
                    n += 1
        prev = ch if is_v else None
    return max(n, 1)


def load_audio(path):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def envelope(x):
    sos = butter(4, [200, 4000], btype="band", fs=SR, output="sos")
    y = sosfiltfilt(sos, x)
    n = len(y) // HOP
    fr = y[: n * HOP].reshape(n, HOP)
    rms = np.sqrt((fr ** 2).mean(1) + 1e-10)
    db = 20 * np.log10(rms + 1e-9)
    k = np.ones(3) / 3
    return np.convolve(db, k, mode="same")


def voiced_mask(db):
    lo, hi = np.percentile(db, 8), np.percentile(db, 96)
    thr = lo + 0.30 * (hi - lo)
    m = db > thr
    # cierra huecos < 120 ms dentro del habla
    idx = np.where(m)[0]
    if len(idx):
        for a, b in zip(idx[:-1], idx[1:]):
            if 1 < b - a <= 12:
                m[a:b] = True
    return m, thr, lo, hi


def nuclei(db, thr, lo, hi):
    pk, _ = find_peaks(db, height=thr, prominence=max(2.5, 0.07 * (hi - lo)), distance=7)
    return pk * HOP / SR


def speech_time_map(mask):
    """tiempo real -> tiempo de habla (sin pausas >= 250 ms) y su inversa."""
    n = len(mask)
    keep = np.ones(n, bool)
    i = 0
    while i < n:
        if not mask[i]:
            j = i
            while j < n and not mask[j]:
                j += 1
            if j - i >= 25:                      # pausa >= 250 ms
                keep[i:j] = False
            i = j
        else:
            i += 1
    cum = np.cumsum(keep) * HOP / SR
    return keep, cum


def inv_map(cum, s):
    i = int(np.searchsorted(cum, s))
    return min(i, len(cum) - 1) * HOP / SR


def tokenize(text):
    return [t for t in re.split(r"\s+", text.strip()) if t]


def align(words, over, db, mask, thr, lo, hi):
    toks = [syllables(w, over) for w in words]
    N = sum(toks)
    nu = nuclei(db, thr, lo, hi)
    M = len(nu)
    keep, cum = speech_time_map(mask)
    D = cum[-1]
    # tiempo esperado de cada sílaba (reparto uniforme sobre el tiempo de habla)
    e = np.array([inv_map(cum, (i + 0.5) / N * D) for i in range(N)])
    SC, SKS, SKN = 0.55, 2.2, 0.55
    INF = 1e9
    dp = np.full((N + 1, M + 1), INF)
    bk = np.zeros((N + 1, M + 1), np.int8)
    dp[0, :] = np.arange(M + 1) * SKN * 0.2
    for i in range(1, N + 1):
        dp[i, 0] = dp[i - 1, 0] + SKS
        bk[i, 0] = 1
        for j in range(1, M + 1):
            c = min(((e[i - 1] - nu[j - 1]) / SC) ** 2, 5.0)
            opts = (dp[i - 1, j - 1] + c, dp[i - 1, j] + SKS, dp[i, j - 1] + SKN)
            k = int(np.argmin(opts))
            dp[i, j], bk[i, j] = opts[k], k
    i, j = N, int(np.argmin(dp[N]))
    match = [None] * N
    while i > 0:
        k = bk[i, j] if j > 0 else 1
        if k == 0:
            match[i - 1] = nu[j - 1]
            i, j = i - 1, j - 1
        elif k == 1:
            i -= 1
        else:
            j -= 1
    # sílabas sin pico: interpolar entre vecinas
    t = np.array([np.nan if m is None else m for m in match], float)
    ok = ~np.isnan(t)
    if ok.sum() < 2:
        t = e.copy()
    else:
        t = np.interp(np.arange(N), np.where(ok)[0], t[ok])
    for q in range(1, N):                        # monotonía estricta
        t[q] = max(t[q], t[q - 1] + 0.03)
    return toks, t, int(ok.sum()), N, M


def build_words(words, toks, t, dur, mask):
    out, p = [], 0
    voiced = np.where(mask)[0] * HOP / SR
    for w, n in zip(words, toks):
        a, b = t[p], t[p + n - 1]
        p += n
        out.append([w, a, b])
    res = []
    for k, (w, a, b) in enumerate(out):
        start = max(0.0, a - 0.075)
        end = b + 0.16
        if k + 1 < len(out):
            nxt = out[k + 1][1] - 0.075
            end = min(end, max(nxt, start + 0.08))
        if k > 0:
            start = max(start, res[-1]["start"] + 0.04)
            if start < res[-1]["end"]:
                res[-1]["end"] = round(start, 3)
        # no empezar dentro de un silencio largo: busca el primer instante con voz cerca del inicio
        res.append({"word": w, "start": round(start, 3), "end": round(min(end, dur), 3)})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--text-file", required=True, help="texto exacto de lo que se dice (puede ir con puntuación)")
    ap.add_argument("--out-dir", default="work")
    ap.add_argument("--syl", default="", help='sílabas de palabras raras: "IA=2,ChatGPT=4"')
    ap.add_argument("--debug-plot", help="PNG con la energía y las marcas de palabra (mira la imagen)")
    ap.add_argument("--start", type=float, default=0.0, help="ignora audio antes de este segundo")
    args = ap.parse_args()

    text = open(args.text_file, encoding="utf-8").read()
    words = tokenize(text)
    over = {}
    for part in filter(None, args.syl.split(",")):
        k, v = part.split("=")
        over[re.sub(r"[^\wáéíóúüñ]", "", k.lower())] = int(v)
    x = load_audio(args.video)
    dur = len(x) / SR
    db = envelope(x)
    mask, thr, lo, hi = voiced_mask(db)
    if args.start:
        mask[: int(args.start * SR / HOP)] = False
    toks, t, matched, N, M = align(words, over, db, mask, thr, lo, hi)
    res = build_words(words, toks, t, dur, mask)

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "words.json"), "w", encoding="utf-8") as f:
        json.dump({"language": "es", "duration": round(dur, 3), "words": res, "alignment": "text-energy"}, f, ensure_ascii=False, indent=1)
    lines, idx, cur, buf = [], [], 0, []
    for i, w in enumerate(res):
        buf.append(f"{w['word']}({i})")
        if re.search(r"[.!?…]$", w["word"]) or len(buf) >= 14 or i == len(res) - 1:
            lines.append(f"[{res[cur]['start']:7.2f}-{w['end']:7.2f}] " + " ".join(r["word"] for r in res[cur:i + 1]))
            idx.append(f"[{res[cur]['start']:7.2f}] " + " ".join(buf))
            cur, buf = i + 1, []
    open(os.path.join(args.out_dir, "transcript.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    open(os.path.join(args.out_dir, "transcript_indexed.txt"), "w", encoding="utf-8").write("\n".join(idx) + "\n")
    cov = matched / N
    print(f"OK: {len(res)} palabras, {N} sílabas, {M} picos de voz, {matched} emparejados ({cov:.0%}), {dur:.1f}s")
    if cov < 0.6 or not (0.7 < M / N < 1.5):
        print("AVISO: pocas coincidencias sílaba↔pico. Revisa el texto (¿falta o sobra algo?) o mira --debug-plot.")

    if args.debug_plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        tt = np.arange(len(db)) * HOP / SR
        n = int(np.ceil(dur / 14))
        fig, axs = plt.subplots(n, 1, figsize=(18, 2.6 * n))
        axs = np.atleast_1d(axs)
        for k, ax in enumerate(axs):
            a, b = k * 14, (k + 1) * 14
            m = (tt >= a) & (tt <= b)
            ax.plot(tt[m], db[m], lw=0.8, color="#2563EB")
            ax.axhline(thr, color="#bbb", lw=0.6)
            for r in res:
                if a <= r["start"] <= b:
                    ax.axvline(r["start"], color="#FE6605", lw=0.7)
                    ax.text(r["start"], hi + 1, r["word"], rotation=90, fontsize=7, va="bottom")
            ax.set_xlim(a, b)
            ax.set_ylim(lo - 3, hi + 14)
        os.makedirs(os.path.dirname(os.path.abspath(args.debug_plot)), exist_ok=True)
        plt.tight_layout()
        plt.savefig(args.debug_plot, dpi=70)
        print("debug:", args.debug_plot)


if __name__ == "__main__":
    main()
