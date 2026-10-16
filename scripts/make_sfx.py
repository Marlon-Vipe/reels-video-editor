#!/usr/bin/env python3
"""Sintetiza efectos de sonido originales (sin derechos de autor) para reforzar cortes, tarjetas y ganchos.

  whoosh.wav / whoosh_short.wav   barrido de aire para entradas y salidas de tarjetas
  riser.wav                       tensión ascendente (~1.4 s) para llegar a un golpe (hook, revelación)
  impact.wav                      golpe grave con cola (palabra que cae, "slam")
  pop.wav / tick.wav              texto que aparece / clic de teclado
  ding.wav / sparkle.wav          logro, alianza, algo positivo
  glitch.wav                      tartamudeo digital para transiciones tipo glitch

Uso: python make_sfx.py --out-dir work/sfx
"""
import argparse
import os
import wave

import numpy as np
from scipy import signal

SR = 48000
RNG = np.random.RandomState(4)


def write(path, x):
    x = np.clip(x / max(1e-6, np.max(np.abs(x))) * 0.9, -1, 1)
    st = np.stack([x, x], axis=1) if x.ndim == 1 else x
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())


def tt(dur):
    return np.arange(int(SR * dur)) / SR


def noise(dur):
    return RNG.standard_normal(int(SR * dur))


def band(x, lo, hi):
    return signal.sosfilt(signal.butter(2, [lo, hi], btype="band", fs=SR, output="sos"), x)


def low(x, fc):
    return signal.sosfilt(signal.butter(2, fc, btype="low", fs=SR, output="sos"), x)


def whoosh(dur=0.7, up=True):
    t = tt(dur)
    x = noise(dur)
    bands = [(250, 800), (600, 1600), (1400, 3200), (2800, 7000)]
    y = np.zeros_like(t)
    for i, (lo, hi) in enumerate(bands):
        c = (0.22 + 0.16 * i) * dur if up else (0.82 - 0.16 * i) * dur
        y += band(x, lo, hi) * np.exp(-((t - c) / (0.16 * dur)) ** 2)
    return y * np.minimum(1, t / 0.05) * np.minimum(1, (dur - t) / 0.08)


def riser(dur=1.4):
    t = tt(dur)
    f = 180 * (2200 / 180) ** (t / dur)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25
    n = np.zeros_like(t)
    x = noise(dur)
    for i, (lo, hi) in enumerate([(300, 900), (900, 2200), (2200, 6500)]):
        n += band(x, lo, hi) * np.clip((t / dur - 0.25 * i) * 1.8, 0, 1)
    y = (tone + n * 0.7) * (t / dur) ** 2.2 * (0.7 + 0.3 * np.sin(2 * np.pi * (6 + 14 * t / dur) * t))
    return y * np.minimum(1, (dur - t) / 0.02)


def impact(dur=1.1):
    t = tt(dur)
    f = 42 + 90 * np.exp(-t * 20)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.4)
    body = low(noise(dur), 2200) * np.exp(-t * 13) * 0.7
    click = low(noise(dur), 4500) * np.exp(-t * 260) * 0.35
    ir = low(noise(0.5), 1500) * np.exp(-np.arange(int(SR * 0.5)) / SR * 7)
    y = sub + body + click
    y = y + 0.25 * np.convolve(y, ir, mode="full")[:len(y)] / np.sqrt(len(ir))
    return y


def pop(dur=0.2):
    t = tt(dur)
    return np.sin(2 * np.pi * (900 - 3200 * t) * t) * np.exp(-t * 22)


def tick(dur=0.05):
    t = tt(dur)
    return band(noise(dur), 2000, 6000) * np.exp(-t * 90)


def ding(dur=0.9):
    t = tt(dur)
    return (np.sin(2 * np.pi * 1320 * t) + 0.5 * np.sin(2 * np.pi * 1980 * t)) * np.exp(-t * 6)


def sparkle(dur=0.7):
    t = tt(dur)
    y = np.zeros_like(t)
    for i, f in enumerate((1568, 2093, 2637, 3136)):
        s = int(SR * 0.07 * i)
        tail = t[:len(t) - s]
        y[s:] += np.sin(2 * np.pi * f * tail) * np.exp(-tail * 9) * 0.6
    return y


def glitch(dur=0.4):
    y = np.zeros(int(SR * dur))
    pos = 0
    while pos < len(y) - 800:
        n = int(SR * RNG.uniform(0.02, 0.05))
        f = RNG.uniform(200, 2400)
        seg = np.sign(np.sin(2 * np.pi * f * np.arange(n) / SR)) * RNG.uniform(0.3, 0.9)
        seg = np.round(seg * 4) / 4
        y[pos:pos + n] += seg[:len(y) - pos]
        pos += n + int(SR * RNG.uniform(0.0, 0.04))
    return y * np.minimum(1, (dur - tt(dur)) / 0.05)


FX = {"whoosh.wav": lambda: whoosh(0.7), "whoosh_short.wav": lambda: whoosh(0.3), "riser.wav": riser,
      "impact.wav": impact, "pop.wav": pop, "tick.wav": tick, "ding.wav": ding, "sparkle.wav": sparkle, "glitch.wav": glitch}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="work/sfx")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    for name, fn in FX.items():
        write(os.path.join(a.out_dir, name), fn())
        print("OK:", os.path.join(a.out_dir, name))
