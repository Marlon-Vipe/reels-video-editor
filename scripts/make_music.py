#!/usr/bin/env python3
"""Genera una pista de fondo ORIGINAL (sintetizada, sin derechos de autor) para poner bajo la voz.

Estilos:
  pulse  tech/motivacional, 104 bpm: bombo, hi-hats, bajo, pad y arpegio (el más versátil para IA/tecnología)
  hype   más rápido y percutido, 120 bpm: para ganchos intensos
  calm   suave, 84 bpm: pad y arpegio con bombo ligero, para explicaciones

Uso: python make_music.py --style pulse --dur 60 --out work/music.wav [--seed 1]
En export.py se usa con --music work/music.wav --music-db -22 (baja sola cuando hablas).
"""
import argparse
import wave

import numpy as np
from scipy import signal

SR = 48000
CHORDS = [  # Am - F - C - G
    ([55.0, 55.0, 65.41, 49.0], [220.0, 261.63, 329.63]),
    ([43.65, 43.65, 43.65, 43.65], [174.61, 220.0, 261.63]),
    ([65.41, 65.41, 65.41, 65.41], [261.63, 329.63, 392.0]),
    ([49.0, 49.0, 49.0, 49.0], [196.0, 246.94, 293.66]),
]
STYLES = {"pulse": dict(bpm=104, kick="four", clap=True, hats=True, bass=True, pad=.30, arp=.20),
          "hype": dict(bpm=120, kick="four", clap=True, hats=True, bass=True, pad=.22, arp=.26),
          "calm": dict(bpm=84, kick="soft", clap=False, hats=False, bass=False, pad=.42, arp=.24)}


def lp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, btype="low", fs=SR, output="sos"), x)


def hp(x, fc):
    return signal.sosfilt(signal.butter(2, fc, btype="high", fs=SR, output="sos"), x)


def add(track, start, sig):
    if start >= len(track):
        return
    end = min(len(track), start + len(sig))
    track[start:end] += sig[:end - start]


def kick(dur=0.3):
    t = np.arange(int(SR * dur)) / SR
    f = 48 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def clap(rng, dur=0.18):
    t = np.arange(int(SR * dur)) / SR
    x = signal.sosfilt(signal.butter(2, [900, 4500], btype="band", fs=SR, output="sos"), rng.standard_normal(len(t)))
    return x * (np.exp(-t * 26) + 0.6 * np.exp(-((t - 0.012) * 90) ** 2))


def hat(rng, dur=0.06, open_=False):
    n = int(SR * (0.25 if open_ else dur))
    t = np.arange(n) / SR
    return hp(rng.standard_normal(n), 7000) * np.exp(-t * (14 if open_ else 70))


def saw_note(f, dur, detune=0.0):
    t = np.arange(int(SR * dur)) / SR
    y = signal.sawtooth(2 * np.pi * f * (1 + detune) * t)
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", choices=STYLES, default="pulse")
    ap.add_argument("--dur", type=float, default=60.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="work/music.wav")
    a = ap.parse_args()
    S = STYLES[a.style]
    rng = np.random.RandomState(a.seed)
    beat = 60.0 / S["bpm"]
    n = int(SR * a.dur)
    drums, bass, pad, arp = (np.zeros(n) for _ in range(4))
    K = kick()
    bars = int(a.dur / (beat * 4)) + 1
    for bar in range(bars):
        ch = CHORDS[bar % 4]
        t0 = bar * beat * 4
        for b in range(4):
            tb = t0 + b * beat
            s = int(tb * SR)
            if S["kick"] == "four" or (S["kick"] == "soft" and b in (0, 2)):
                add(drums, s, K * (0.9 if S["kick"] == "four" else 0.5))
            if S["clap"] and b in (1, 3):
                add(drums, s, clap(rng) * 0.35)
            if S["hats"]:
                add(drums, s, hat(rng) * 0.13)
                add(drums, int((tb + beat / 2) * SR), hat(rng, open_=(b % 2 == 1)) * 0.10)
            if S["bass"]:
                f = ch[0][b]
                for h in range(2):
                    d = beat / 2
                    note = lp(saw_note(f, d), 420) * np.exp(-np.arange(int(SR * d)) / SR * 5)
                    add(bass, int((tb + h * d) * SR), note * 0.55)
        # pad: acorde sostenido (sierras desafinadas filtradas)
        dur_bar = beat * 4
        tp = np.arange(int(SR * dur_bar)) / SR
        env = np.minimum(1, tp / 0.4) * np.minimum(1, (dur_bar - tp) / 0.5)
        chord = sum(saw_note(f, dur_bar, d) for f in ch[1] for d in (-0.004, 0.0, 0.004))
        add(pad, int(t0 * SR), lp(chord, 1500) * env * 0.08)
        # arpegio en semicorcheas
        for step in range(16):
            if rng.rand() < 0.62:
                f = ch[1][step % 3] * (2 if step % 5 == 0 else 1)
                d = 0.22
                tn = np.arange(int(SR * d)) / SR
                pl = (np.sin(2 * np.pi * f * tn) + 0.35 * signal.sawtooth(2 * np.pi * f * tn)) * np.exp(-tn * 13)
                add(arp, int((t0 + step * beat / 4) * SR), pl * 0.2)
    mix = drums + bass + pad * S["pad"] * 6 + arp * S["arp"] * 3
    mix = np.tanh(mix * 1.4) / 1.4
    fade = np.minimum(1, np.arange(n) / (0.6 * SR)) * np.minimum(1, (n - np.arange(n)) / (2.0 * SR))
    mix = mix * fade
    mix = mix / max(1e-6, np.max(np.abs(mix))) * 0.8
    st = np.stack([mix, np.roll(mix, int(0.011 * SR))], axis=1)  # ancho estéreo leve
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    print(f"OK: {a.out} ({a.style}, {S['bpm']} bpm, {a.dur:.0f}s)")


if __name__ == "__main__":
    main()
