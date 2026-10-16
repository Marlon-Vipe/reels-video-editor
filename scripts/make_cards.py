#!/usr/bin/env python3
"""Tarjetas animadas (motion graphics 1080x1920) para cutaways y stickers, con la paleta de la marca.

Cada tarjeta se exporta como DOS videos: <name>.mp4 (imagen) y <name>.matte.mp4 (transparencia animada).
export.py --broll las une (alphamerge), así las transiciones (iris, cortinas, glitch...) son parte de la tarjeta.

Plantillas (todas distintas entre sí: alterna diseños en un mismo video, no repitas dos seguidas):
  alert     problema / error / caída                 {"title","code","sub"}
  pillars   lista de 1-4 conceptos que entran         {"title","items":[{"icon","text","t"}]}
  partner   A × B  ó  A ≠ B con insignia              {"title","a","b","b_color","symbol","badge","t_a","t_x","t_b","t_badge"}
  growth    barras que crecen + flecha                {"title","label"}
  strike    una palabra tachada con señal de "no"     {"chip","text","t_x"}
  terminal  ventana de terminal que escribe comandos  {"title","lines":[{"text","t","result"}]}
  orbit     concepto central con palabras alrededor   {"icon","items":[{"text","t"}]}
  meter     barras de medidor que se llenan (versus)  {"title","bars":[{"label","value","color","t"}],"caption"}
  slam      una palabra gigante que cae con impacto   {"text","sub"}
  sticker   icono suelto sobre el video (sin fondo)   {"icon","label","pos":[fx,fy],"size"}
  panel     panel de cristal "A ≠ B" sobre el video     {"items":[{"icon","text"}],"symbols":["≠"],"pos":[0.5,0.185]}
Iconos: bolt chart shield check x doc search gear neq star heart bulb clock rocket
  --- Kit "UI" (look del video de referencia: borde grueso + sombra dura, sin fondo, sobre el video) ---
  kicker_slam  palabra gigante + etiqueta mono arriba   {"kicker","text","pos":[fx,fy],"size"}
  toast        notificaciones/DMs que bajan una tras otra  {"items":[{"user","text","t","badge"}],"pos"}
  ui_meter     medidor de 2 barras (A vs B)              {"kicker","title","bars":[{"label","icon","value","t","color":"ink|acc"}],"pos"}
  ui_flow      flujo vertical de pasos                   {"kicker","title","steps":[{"icon","label","state":"no|normal|hot","stamp","t"}],"pos"}
  ui_iconrow   fila de iconos con etiqueta (1 = ficha)   {"items":[{"icon","label","t"}],"pos"}
  ui_tag       etiqueta de acción "Responde X"           {"lead","keyword","pos"}
  ui_cta       tarjeta de cierre con flecha              {"kicker","lead","keyword","sub","pos"}
  phone        mockup de teléfono + etiqueta             {"label","pos","tilt"}
  Iconos extra: scissors video send wand music layout expand captions scan brain play chat arrow_down gauge user globe mic
Comunes: "bg": blue|deep|bright|mono|flat|warm  (SOLO planos/degradados, nunca cuadrículas) · "in"/"out": iris wipe_l wipe_r wipe_u wipe_d diag blinds glitch fade
         "in_dur"/"out_dur" · "flash": true/false · "dur"

Uso:
  python make_cards.py cards.json --brand assets/brand.json --out-dir work/cards [--seed 3] [--only nombre] [--preview]
Deja libre la franja inferior (~22%): ahí van los subtítulos. No usa logos de terceros: solo texto.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from common import load_brand

W, H, FPS = 1080, 1920, 30
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)


# ---------------------------------------------------------------- utilidades
def rgb(hexc):
    h = hexc.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_cubic(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x, s=1.9):
    x = clamp(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


_fonts = {}


def _find_font(families, bold=True):
    for fam in families:
        try:
            out = subprocess.run(["fc-match", "-f", "%{family}|%{file}", f"{fam}:{'bold' if bold else 'regular'}"],
                                 capture_output=True, text=True).stdout
        except FileNotFoundError:
            return None
        got, _, path = out.partition("|")
        if fam.lower() in got.lower() and os.path.exists(path):
            return path
    return None


SANS_PREF = ["Space Grotesk", "Montserrat", "Poppins", "Inter", "DejaVu Sans"]
MONO_PREF = ["JetBrains Mono", "DejaVu Sans Mono"]


def font(size, mono=False):
    k = (size, mono)
    if k not in _fonts:
        f = _find_font(MONO_PREF if mono else SANS_PREF)
        _fonts[k] = ImageFont.truetype(f, size) if f else ImageFont.load_default()
    return _fonts[k]


def fit_font(draw, text, max_w, start, min_size=28):
    s = start
    while s > min_size and draw.textlength(text, font=font(s)) > max_w:
        s -= 2
    return font(s)


def sprite(w, h, fn, ss=3):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), ss)
    return im.resize((w, h), Image.LANCZOS)


def rrect(w, h, r, fill, outline=None, ow=0):
    def fn(d, k):
        d.rounded_rectangle([0, 0, w * k - 1, h * k - 1], r * k, fill=fill, outline=outline, width=ow * k)
    return sprite(w, h, fn)


def put(base, spr, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    s = spr
    w, h = s.size
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    if (nw, nh) != (w, h):
        s = s.resize((nw, nh), Image.LANCZOS)
    if abs(rot) > 0.01:
        s = s.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        a = s.getchannel("A").point(lambda v: int(v * alpha))
        s = s.copy()
        s.putalpha(a)
    x, y = int(cx - s.width / 2), int(cy - s.height / 2)
    if base.mode == "RGBA" and base.getpixel((0, 0))[3] < 255:  # lienzo transparente (stickers)
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        layer.paste(s, (x, y))
        base.alpha_composite(layer)
    else:
        base.paste(s, (x, y), s)


def text_sprite(text, size, color, heavy=False, max_w=None, mono=False):
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    f = fit_font(tmp, text, max_w, size) if max_w else font(size, mono)
    sw = max(1, size // 26) if heavy else 0
    bb = tmp.textbbox((0, 0), text, font=f, stroke_width=sw)
    w, h = bb[2] - bb[0] + 12, bb[3] - bb[1] + 12
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((6 - bb[0], 6 - bb[1]), text, font=f, fill=color, stroke_width=sw, stroke_fill=color)
    return im


def chip(text, size, fill, color, padx=44, pady=22, r=30, max_w=None, heavy=True):
    t = text_sprite(text, size, color, heavy=heavy, max_w=max_w)
    w, h = t.width + padx * 2, t.height + pady * 2
    base = rrect(w, h, min(r, h // 2), fill)
    base.paste(t, (padx, pady), t)
    return base


# ---------------------------------------------------------------- iconos vectoriales
def icon(kind, s, color, accent=(255, 255, 255)):
    def fn(d, k):
        S = s * k
        P = lambda pts: [(x * S, y * S) for x, y in pts]
        if kind == "bolt":
            d.polygon(P([(.56, .04), (.18, .56), (.46, .56), (.36, .96), (.82, .38), (.54, .38)]), fill=color)
        elif kind == "chart":
            for x0, top in ((.10, .60), (.40, .42), (.70, .22)):
                d.rounded_rectangle([x0 * S, top * S, (x0 + .2) * S, .90 * S], .04 * S, fill=color)
        elif kind == "shield":
            d.polygon(P([(.14, .16), (.50, .04), (.86, .16), (.86, .52), (.50, .96), (.14, .52)]), fill=color)
            d.line(P([(.32, .50), (.46, .65), (.70, .35)]), fill=accent, width=int(.09 * S), joint="curve")
        elif kind == "check":
            d.line(P([(.18, .54), (.42, .78), (.84, .24)]), fill=color, width=int(.14 * S), joint="curve")
        elif kind == "x":
            d.line(P([(.22, .22), (.78, .78)]), fill=color, width=int(.14 * S))
            d.line(P([(.78, .22), (.22, .78)]), fill=color, width=int(.14 * S))
        elif kind == "doc":
            d.rounded_rectangle([.20 * S, .08 * S, .80 * S, .92 * S], .08 * S, fill=color)
            for y in (.34, .52, .70):
                d.line(P([(.32, y), (.68, y)]), fill=(0, 0, 0, 0), width=int(.07 * S))
        elif kind == "search":
            d.ellipse([.10 * S, .10 * S, .62 * S, .62 * S], outline=color, width=int(.11 * S))
            d.line(P([(.54, .54), (.88, .88)]), fill=color, width=int(.13 * S))
        elif kind == "gear":
            c = .5 * S
            for k2 in range(8):
                a = k2 * math.pi / 4
                d.line([(c + math.cos(a) * .28 * S, c + math.sin(a) * .28 * S), (c + math.cos(a) * .46 * S, c + math.sin(a) * .46 * S)],
                       fill=color, width=int(.15 * S))
            d.ellipse([.20 * S, .20 * S, .80 * S, .80 * S], outline=color, width=int(.12 * S))
        elif kind == "neq":
            d.line(P([(.14, .36), (.86, .36)]), fill=color, width=int(.11 * S))
            d.line(P([(.14, .64), (.86, .64)]), fill=color, width=int(.11 * S))
            d.line(P([(.68, .14), (.32, .86)]), fill=color, width=int(.11 * S))
        elif kind == "heart":
            d.ellipse([.10 * S, .14 * S, .52 * S, .56 * S], fill=color)
            d.ellipse([.48 * S, .14 * S, .90 * S, .56 * S], fill=color)
            d.polygon(P([(.12, .46), (.88, .46), (.50, .92)]), fill=color)
        elif kind == "bulb":
            d.ellipse([.22 * S, .06 * S, .78 * S, .62 * S], fill=color)
            d.rounded_rectangle([.36 * S, .60 * S, .64 * S, .80 * S], .05 * S, fill=color)
            d.rounded_rectangle([.40 * S, .84 * S, .60 * S, .94 * S], .04 * S, fill=color)
        elif kind == "clock":
            d.ellipse([.06 * S, .06 * S, .94 * S, .94 * S], outline=color, width=int(.10 * S))
            d.line(P([(.5, .5), (.5, .24)]), fill=color, width=int(.09 * S))
            d.line(P([(.5, .5), (.70, .60)]), fill=color, width=int(.09 * S))
        elif kind == "rocket":
            d.polygon(P([(.5, .04), (.72, .32), (.68, .70), (.32, .70), (.28, .32)]), fill=color)
            d.polygon(P([(.28, .50), (.10, .78), (.32, .70)]), fill=color)
            d.polygon(P([(.72, .50), (.90, .78), (.68, .70)]), fill=color)
            d.ellipse([.40 * S, .30 * S, .60 * S, .50 * S], fill=(0, 0, 0, 0))
            d.polygon(P([(.40, .74), (.60, .74), (.50, .96)]), fill=color)
        elif kind == "star":
            d.polygon(P([(.5, 0), (.6, .4), (1, .5), (.6, .6), (.5, 1), (.4, .6), (0, .5), (.4, .4)]), fill=color)
    return sprite(s, s, fn)


# ---------------------------------------------------------------- fondos animados
class BG:
    """Fondos animados con la paleta de brand.json. SOLO planos o degradados: NUNCA cuadrículas, rayas ni patrones.
    Variantes: blue (degradado azul con brillo), deep (azul profundo -> negro), bright (degradado lineal azul),
    mono (negro casi plano con brillo azul suave), flat (color plano), warm (naranja, solo alertas)."""
    def __init__(self, brand, variant):
        self.v = {"orange": "warm", "duo": "bright", "solid": "flat"}.get(variant, variant)
        self.p = np.array(rgb(brand["primary_color"]), np.float32)
        self.deep = np.array(rgb(brand.get("deep_color", "#0F2147")), np.float32)
        self.warm = np.array(rgb(brand.get("warm_color", "#FE6605")), np.float32)
        self.black = np.array(rgb(brand.get("dark_color", "#000000")), np.float32) + 3
        self.flat = np.array(rgb(brand.get("flat_bg_color", brand.get("deep_color", "#0F2147"))), np.float32)

    def _glow(self, base, cx, cy, r, color, k):
        d = np.sqrt((XX - cx) ** 2 + (YY - cy) ** 2) / r
        base += (np.clip(1 - d, 0, 1) ** 2 * k)[..., None] * color

    def _linear(self, c1, c2, t, angle=0.6):
        m = (XX * math.cos(angle) * 0.4 + YY) / (H + W * 0.4) + 0.04 * math.sin(t * 1.1)
        k = np.clip(m, 0, 1)[..., None]
        return c1 * (1 - k) + c2 * k

    def frame(self, t):
        v = self.v
        if v == "flat":
            base = np.zeros((H, W, 3), np.float32) + self.flat
        elif v == "deep":
            base = self._linear(self.deep * 1.15, self.black, t)
            self._glow(base, 540 + 160 * math.sin(.7 * t), 520 + 90 * math.cos(.6 * t), 1000, self.p, .45)
        elif v == "mono":
            base = np.zeros((H, W, 3), np.float32) + np.array((12, 12, 14), np.float32)
            self._glow(base, 540, 900 + 60 * math.sin(t), 950, self.p, .22)
        elif v == "bright":
            base = self._linear(self.p * 0.95, self.deep * 0.9, t, angle=1.0)
        elif v == "warm":   # color cálido de alerta: solo si el mensaje pide un contraste (alerta, 'no hagas esto')
            base = self._linear(self.black, self.deep * 0.8, t)
            self._glow(base, 900 - 90 * math.sin(.8 * t), 420 + 70 * math.cos(.7 * t), 950, self.warm, .42)
        else:  # blue (por defecto)
            base = self._linear(self.deep * 0.7, self.black, t)
            self._glow(base, 150 + 140 * math.sin(.9 * t), 420 + 100 * math.cos(.7 * t), 950, self.p, .62)
            self._glow(base, 960 - 100 * math.cos(.8 * t), 1450 + 80 * math.sin(.6 * t), 820, self.deep * 1.6, .55)
        return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


# ---------------------------------------------------------------- transiciones (máscara de alpha)
def trans_alpha(kind, p):
    if p >= 0.999:
        return None
    p = clamp(p)
    f = 14.0
    if kind == "fade":
        a = np.full((H, W), p, np.float32)
    elif kind == "iris":
        R = math.hypot(W, H) * 0.62 * p
        a = (R - np.sqrt((XX - 540) ** 2 + (YY - 900) ** 2)) / f + .5
    elif kind == "wipe_l":
        a = (p * (W + 40) - XX) / f + .5
    elif kind == "wipe_r":
        a = (XX - (W - p * (W + 40))) / f + .5
    elif kind == "wipe_u":
        a = (YY - (H - p * (H + 40))) / f + .5
    elif kind == "wipe_d":
        a = (p * (H + 40) - YY) / f + .5
    elif kind == "diag":
        a = (p * (W + H + 60) - (XX + YY)) / f + .5
    elif kind == "blinds":
        band = 160.0
        a = (p * band * 1.05 - (YY % band)) / 10 + .5
    elif kind == "glitch":
        thr = np.random.RandomState(7).rand(H // 48 + 2).astype(np.float32)[(YY // 48).astype(np.int32)] * 0.7
        a = (p - thr) * 30 + .5
    else:
        a = np.full((H, W), p, np.float32)
    return (np.clip(a, 0, 1) * 255).astype(np.uint8)


def glitch_shift(arr, strength):
    if strength <= 0.02:
        return arr
    rs = np.random.RandomState(int(strength * 100))
    out = arr.copy()
    for y in range(0, H, 48):
        if rs.rand() < 0.5:
            out[y:y + 48] = np.roll(arr[y:y + 48], int(rs.randint(-70, 70) * strength), axis=1)
    return out


# ---------------------------------------------------------------- plantillas
def sparkles(im, t, n, color, seed=1, ymin=380, ymax=1400):
    rnd = np.random.RandomState(seed)
    for i in range(n):
        x = rnd.uniform(50, 150) if i % 2 == 0 else rnd.uniform(930, 1030)
        y = rnd.uniform(ymin, ymax)
        ph = rnd.uniform(0, 6.28)
        sz = int(rnd.uniform(28, 64))
        a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 5 + ph))
        put(im, icon("star", sz, color), x, y, 0.6 + 0.4 * a, a)


def title_chip(brand, text):
    return chip(text, 60, rgb(brand["accent_color"]), rgb(brand["on_accent_color"]), max_w=880)


def tpl_alert(spec, brand, bg):
    red = rgb(brand.get("warm_color", "#FE6605"))   # color de alerta
    title = title_chip(brand, spec["title"]) if spec.get("title") else None
    code = text_sprite(spec.get("code", "ERROR 503"), 104, red, heavy=True, max_w=720)
    sub = text_sprite(spec.get("sub", "Servicio no disponible"), 46, (160, 168, 190), max_w=720)
    card = rrect(820, 640, 46, (16, 19, 31), outline=(58, 66, 104), ow=4)
    bar = sprite(820, 640, lambda d, k: [d.ellipse([(46 + i * 52) * k, 40 * k, (46 + i * 52 + 26) * k, 66 * k], fill=c)
                                        for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63)))])
    card.paste(bar, (0, 0), bar)
    circle = sprite(240, 240, lambda d, k: d.ellipse([0, 0, 240 * k - 1, 240 * k - 1], fill=red))
    xicon = icon("x", 130, (255, 255, 255))
    glow = sprite(560, 560, lambda d, k: d.ellipse([0, 0, 560 * k - 1, 560 * k - 1], fill=red + (70,)))

    def frame(t):
        im = bg.frame(t)
        if title:
            put(im, title, W / 2, 330, ease_out_back((t - 0.05) / 0.35))
        s = ease_out_back(t / 0.42)
        dx = 16 * math.exp(-t * 4.5) * math.sin(t * 38) if t < 1.2 else 0
        cx, cy = W / 2 + dx, 930
        put(im, glow, cx, cy - 60, 1 + 0.10 * math.sin(t * 9), 0.55 + 0.35 * math.sin(t * 9))
        put(im, card, cx, cy, s)
        pulse = 1 + 0.06 * math.sin(t * 10)
        put(im, circle, cx, cy - 70, s * pulse)
        put(im, xicon, cx, cy - 70, s * pulse)
        put(im, code, cx, cy + 150, s)
        put(im, sub, cx, cy + 232, s)
        sparkles(im, t, 6, rgb(brand["accent_color"]), seed=3)
        return im
    return frame


def tpl_pillars(spec, brand, bg):
    items = spec.get("items") or [{"icon": "bolt", "text": "RENDIMIENTO", "t": 0.2}]
    title = title_chip(brand, spec["title"]) if spec.get("title") else None
    circ = sprite(150, 150, lambda d, k: d.ellipse([0, 0, 150 * k - 1, 150 * k - 1], fill=rgb(brand["accent_color"])))
    cards = []
    for it in items:
        c = rrect(920, 210, 44, (17, 21, 38), outline=rgb(brand["primary_color"]), ow=5)
        c.paste(circ, (40, 30), circ)
        ic = icon(it.get("icon", "check"), 88, (255, 255, 255))
        c.paste(ic, (71, 61), ic)
        t = text_sprite(it["text"].upper(), 64, (255, 255, 255), heavy=True, max_w=640)
        c.paste(t, (230, (210 - t.height) // 2), t)
        cards.append(c)
    n = len(cards)
    gap = 300 if n <= 3 else 250
    y0 = 830 - (n - 1) * gap / 2
    if title:
        y0 = max(y0, 520)

    def frame(t):
        im = bg.frame(t)
        if title:
            put(im, title, W / 2, 330, ease_out_back((t - 0.05) / 0.35))
        for i, (c, it) in enumerate(zip(cards, items)):
            p = (t - it.get("t", 0.2 * i)) / 0.5
            if p <= 0:
                continue
            x = W / 2 + (1 - ease_out_back(p, 1.4)) * 700
            put(im, c, x, y0 + i * gap, 1.0, clamp(p * 3))
        sparkles(im, t, 5, rgb(brand["accent2_color"]), seed=5)
        return im
    return frame


def tpl_partner(spec, brand, bg):
    a, b = spec.get("a", brand.get("company") or brand["name"]), spec.get("b", "Aliado")
    bcol = rgb(spec.get("b_color", brand["accent2_color"]))
    ttl = spec.get("title", "")
    title = title_chip(brand, ttl) if ttl else None
    ca = chip(a, 128, rgb(brand["primary_color"]), (255, 255, 255), padx=90, pady=40, r=60)
    cb = chip(b, 118, bcol, (255, 255, 255), padx=80, pady=40, r=60, max_w=820)
    sym = spec.get("symbol", "×")
    times = icon("neq", 190, rgb(brand["accent_color"])) if sym == "≠" else text_sprite(sym, 190, rgb(brand["accent_color"]), heavy=True)
    badge_text = spec.get("badge", "")
    btxt = text_sprite(badge_text or " ", 54, rgb(brand["on_accent_color"]), heavy=True, max_w=700)
    bchk = icon("check", 60, rgb(brand["on_accent_color"]))
    bw_, bh_ = btxt.width + bchk.width + 130, btxt.height + 52
    badge = rrect(bw_, bh_, bh_ // 2, rgb(brand["accent_color"]))
    badge.paste(bchk, (44, (bh_ - 60) // 2), bchk)
    badge.paste(btxt, (44 + 60 + 14, (bh_ - btxt.height) // 2), btxt)
    ta, tx, tb, tg = (spec.get(k, d) for k, d in (("t_a", 0.1), ("t_x", 0.5), ("t_b", 0.65), ("t_badge", 1.2)))

    def frame(t):
        im = bg.frame(t)
        if title:
            put(im, title, W / 2, 330, ease_out_back((t - 0.05) / 0.35))
        put(im, ca, W / 2 - (1 - ease_out_cubic((t - ta) / 0.45)) * 900, 700)
        put(im, times, W / 2, 900, ease_out_back((t - tx) / 0.35))
        put(im, cb, W / 2 + (1 - ease_out_cubic((t - tb) / 0.45)) * 900, 1100)
        if badge_text:
            put(im, badge, W / 2, 1330, ease_out_back((t - tg) / 0.4) * (1 + 0.025 * math.sin(t * 8)))
        sparkles(im, t, 9, (255, 255, 255), seed=7)
        return im
    return frame


def tpl_growth(spec, brand, bg):
    title = title_chip(brand, spec.get("title", "CRECE CON TU NEGOCIO"))
    label = chip(spec.get("label", "MÁS CRECIMIENTO"), 56, (255, 255, 255), rgb(brand["dark_color"]), padx=50, pady=24, r=60, max_w=880)
    fr = [0.25, 0.42, 0.58, 0.78, 1.0]
    bw, gap, x0, base_y, maxh = 118, 44, 130, 1190, 560
    bars = []
    for i, f in enumerate(fr):
        col = rgb(brand["accent_color"]) if i == len(fr) - 1 else rgb(brand["primary_color"])
        bars.append((rrect(bw, int(maxh * f) + 1, 26, col), f))

    def frame(t):
        im = bg.frame(t)
        put(im, title, W / 2, 330, ease_out_back((t - 0.05) / 0.35))
        d = ImageDraw.Draw(im)
        d.line([(100, base_y + 6), (980, base_y + 6)], fill=(70, 78, 110), width=5)
        tops = []
        for i, (spr, f) in enumerate(bars):
            p = ease_out_back((t - 0.2 - 0.13 * i) / 0.5, 1.2)
            hgt = max(1, int(spr.height * clamp(p, 0, 1.08)))
            if p > 0.02:
                s = spr.resize((bw, hgt), Image.LANCZOS)
                x = x0 + i * (bw + gap)
                im.paste(s, (x, base_y - hgt), s)
                tops.append((x + bw / 2, base_y - hgt - 40))
        if len(tops) == len(bars):
            q = clamp((t - 1.0) / 0.6)
            n = len(tops) - 1
            pts = [(tops[0][0] - 20, tops[0][1] - 10)] + tops[1:]
            upto = q * n
            seg = min(int(upto), n - 1)
            path = pts[:seg + 1] + [(pts[seg][0] + (pts[seg + 1][0] - pts[seg][0]) * (upto - seg),
                                     pts[seg][1] + (pts[seg + 1][1] - pts[seg][1]) * (upto - seg))]
            d.line(path, fill=rgb(brand["accent_color"]), width=14, joint="curve")
            ex, ey = path[-1]
            d.ellipse([ex - 16, ey - 16, ex + 16, ey + 16], fill=rgb(brand["accent_color"]))
        put(im, label, W / 2, 1330, ease_out_back((t - 1.4) / 0.4))
        sparkles(im, t, 5, rgb(brand["accent2_color"]), seed=9, ymin=420, ymax=900)
        return im
    return frame


def tpl_strike(spec, brand, bg):
    """Palabra en una placa con una señal de prohibido que cae con impacto."""
    red = rgb(brand.get("warm_color", "#FE6605"))
    text = spec.get("text", "PSICÓLOGA").upper()
    lead = spec.get("chip", "LA IA COMO")
    lead_c = chip(lead, 56, rgb(brand["accent_color"]), rgb(brand["on_accent_color"]), max_w=760)
    word = text_sprite(text, 150, (255, 255, 255), heavy=True, max_w=820)
    plate = rrect(word.width + 120, word.height + 90, 50, (18, 22, 40), outline=(90, 100, 150), ow=5)
    plate.paste(word, (60, 45), word)
    ring = sprite(560, 560, lambda d, k: (d.ellipse([20 * k, 20 * k, 540 * k, 540 * k], outline=red, width=44 * k),
                                          d.line([(120 * k, 120 * k), (440 * k, 440 * k)], fill=red, width=44 * k)))
    tx = spec.get("t_x", 0.9)

    def frame(t):
        im = bg.frame(t)
        shake = 0.0
        if 0 <= t - tx < 0.5:
            shake = 22 * math.exp(-(t - tx) * 7) * math.sin((t - tx) * 60)
        put(im, lead_c, W / 2 + shake, 520, ease_out_back((t - 0.05) / 0.35))
        p = ease_out_back((t - 0.2) / 0.45, 1.4)
        dim = 1.0 if t < tx else 0.55
        put(im, plate, W / 2 + shake, 900 + (1 - clamp(p)) * 320, clamp(p, 0.01, 1.05), dim * clamp(p * 3))
        if t >= tx:
            q = t - tx
            put(im, ring, W / 2 + shake, 900, 1.0 + 1.8 * (1 - ease_out_back(q / 0.28, 1.2)) + 0.0, clamp(q * 8))
            wave = sprite(700, 700, lambda d, k: d.ellipse([10 * k, 10 * k, 690 * k, 690 * k], outline=(255, 255, 255, 200), width=10 * k))
            put(im, wave, W / 2, 900, 0.6 + 1.6 * clamp(q / 0.6), clamp(1 - q / 0.6) * 0.8)
        sparkles(im, t, 6, (255, 255, 255), seed=11)
        return im
    return frame


def tpl_terminal(spec, brand, bg):
    lines = spec.get("lines") or [{"text": "resumir()", "t": 0.2, "result": "listo"}]
    win = rrect(940, 820, 46, (13, 16, 26), outline=(58, 66, 104), ow=4)
    dots = sprite(940, 820, lambda d, k: [d.ellipse([(46 + i * 52) * k, 44 * k, (46 + i * 52 + 26) * k, 70 * k], fill=c)
                                          for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63)))])
    win.paste(dots, (0, 0), dots)
    ttl = text_sprite(spec.get("title", "ia.sh"), 36, (120, 130, 170), mono=True)
    win.paste(ttl, (470 - ttl.width // 2, 40), ttl)
    chk = icon("check", 54, (39, 201, 63))
    fm = font(58, mono=True)
    acc, wht = rgb(brand["accent_color"]), (240, 244, 255)
    titlec = title_chip(brand, spec["title_chip"]) if spec.get("title_chip") else None
    cps = 15.0

    def frame(t):
        im = bg.frame(t)
        if titlec:
            put(im, titlec, W / 2, 330, ease_out_back((t - 0.05) / 0.35))
        s = ease_out_back((t - 0.02) / 0.4)
        put(im, win, W / 2, 900, s)
        if s < 0.9:
            return im
        d = ImageDraw.Draw(im)
        x0, y0 = W / 2 - 470 + 60, 900 - 410 + 150
        for i, ln in enumerate(lines):
            tl = ln.get("t", 0.2 + 0.9 * i)
            if t < tl:
                continue
            y = y0 + i * 190
            txt = ln["text"]
            n = min(len(txt), int((t - tl) * cps))
            d.text((x0, y), "›", font=fm, fill=acc)
            d.text((x0 + 56, y), txt[:n], font=fm, fill=wht)
            done = n >= len(txt)
            if not done or (t - tl) * cps < len(txt) + 1:
                if int(t * 3) % 2 == 0:
                    cx = x0 + 56 + d.textlength(txt[:n], font=fm)
                    d.rectangle([cx + 4, y + 6, cx + 26, y + 62], fill=wht)
            elif ln.get("result"):
                q = clamp((t - tl - len(txt) / cps - 0.1) / 0.3)
                if q > 0:
                    im.paste(chk, (int(x0 + 56), int(y + 78)), chk)
                    d.text((x0 + 56 + 70, y + 76), ln["result"], font=font(46, True), fill=(39, 201, 63))
        return im
    return frame


def tpl_orbit(spec, brand, bg):
    items = spec.get("items") or [{"text": "Pensar", "t": 0.2}, {"text": "Crear", "t": 0.6}]
    cx, cy = W / 2, 880
    pos = [(cx, cy - 400), (cx + 345, cy), (cx, cy + 400), (cx - 345, cy)][:len(items)]
    core = sprite(260, 260, lambda d, k: d.ellipse([0, 0, 260 * k - 1, 260 * k - 1], fill=rgb(brand["accent_color"])))
    ic = icon(spec.get("icon", "bulb"), 140, rgb(brand["on_accent_color"]))
    core.paste(ic, (60, 60), ic)
    ringspr = sprite(700, 700, lambda d, k: d.ellipse([6 * k, 6 * k, 694 * k, 694 * k], outline=rgb(brand["primary_color"]) + (255,), width=6 * k))
    chips = [chip(it["text"].upper(), 58, (17, 21, 38), (255, 255, 255), padx=40, pady=22, max_w=330) for it in items]
    outl = [rrect(c.width + 12, c.height + 12, (c.height + 12) // 2, rgb(brand["accent2_color"])) for c in chips]

    def frame(t):
        im = bg.frame(t)
        d = ImageDraw.Draw(im)
        put(im, ringspr, cx, cy, 1.0 + 0.04 * math.sin(t * 2), 0.5, rot=t * 14)
        put(im, ringspr, cx, cy, 0.62, 0.35, rot=-t * 22)
        for (px, py), it, c, o in zip(pos, items, chips, outl):
            p = (t - it.get("t", 0.3)) / 0.45
            if p <= 0:
                continue
            e = ease_out_cubic(p)
            d.line([(cx, cy), (cx + (px - cx) * e, cy + (py - cy) * e)], fill=rgb(brand["accent2_color"]), width=6)
            bob = 8 * math.sin(t * 3 + px)
            put(im, o, px, py + bob, ease_out_back(p, 1.6))
            put(im, c, px, py + bob, ease_out_back(p, 1.6))
        put(im, core, cx, cy, ease_out_back((t - 0.0) / 0.4) * (1 + 0.05 * math.sin(t * 6)))
        sparkles(im, t, 6, rgb(brand["accent2_color"]), seed=13)
        return im
    return frame


def tpl_meter(spec, brand, bg):
    bars = spec.get("bars") or [{"label": "PRODUCIR", "value": 1.0, "color": "primary", "t": 0.2},
                                {"label": "AVANZAR", "value": 0.3, "color": "accent", "t": 0.9}]
    title = title_chip(brand, spec["title"]) if spec.get("title") else None
    cap = chip(spec["caption"], 54, (255, 255, 255), rgb(brand["dark_color"]), padx=50, pady=24, r=60, max_w=880) if spec.get("caption") else None
    track = rrect(880, 128, 64, (20, 24, 42), outline=(58, 66, 104), ow=4)
    n = len(bars)
    y0 = 760 - (n - 1) * 150
    labels = [text_sprite(b["label"].upper(), 70, (255, 255, 255), heavy=True, max_w=800) for b in bars]

    def frame(t):
        im = bg.frame(t)
        if title:
            put(im, title, W / 2, 330, ease_out_back((t - 0.05) / 0.35))
        for i, (b, lab) in enumerate(zip(bars, labels)):
            y = y0 + i * 330
            tt = b.get("t", 0.2 + 0.6 * i)
            put(im, lab, W / 2 - 440 + lab.width / 2, y - 122, ease_out_back((t - tt) / 0.35), 1.0)
            put(im, track, W / 2, y, ease_out_back((t - tt) / 0.35))
            q = ease_out_cubic((t - tt - 0.15) / 0.9)
            wpx = int(872 * clamp(b.get("value", 0.5)) * q)
            if wpx > 30:
                col = rgb(brand["accent_color"]) if b.get("color") == "accent" else rgb(brand["primary_color"])
                fill = rrect(wpx, 120, 60, col)
                shine = rrect(wpx, 38, 19, (255, 255, 255, 60))
                fill.paste(shine, (0, 10), shine)
                im.paste(fill, (int(W / 2 - 436), int(y - 60)), fill)
                d = ImageDraw.Draw(im)
                ex = W / 2 - 436 + wpx
                d.ellipse([ex - 14, y - 14, ex + 14, y + 14], fill=(255, 255, 255))
        if cap:
            put(im, cap, W / 2, 1300, ease_out_back((t - 1.5) / 0.4))
        sparkles(im, t, 5, rgb(brand["accent2_color"]), seed=15)
        return im
    return frame


def tpl_slam(spec, brand, bg):
    text = spec.get("text", "TIEMPO").upper()
    word = text_sprite(text, 220, (255, 255, 255), heavy=True, max_w=940)
    glow = text_sprite(text, 220, rgb(brand["accent_color"]), heavy=True, max_w=940)
    sub = chip(spec["sub"], 54, rgb(brand["accent_color"]), rgb(brand["on_accent_color"]), max_w=860) if spec.get("sub") else None
    ring = sprite(760, 760, lambda d, k: d.ellipse([8 * k, 8 * k, 752 * k, 752 * k], outline=(255, 255, 255, 220), width=12 * k))

    def frame(t):
        im = bg.frame(t)
        p = clamp(t / 0.28)
        sc = 3.2 - 2.2 * ease_out_cubic(p)
        shake = 26 * math.exp(-max(0, t - 0.25) * 7) * math.sin(t * 55) if t > 0.25 else 0
        put(im, glow, W / 2 + 10 + shake, 900 + 10, sc * 1.02, clamp(p * 2) * 0.7)
        put(im, word, W / 2 + shake, 900, sc, clamp(p * 3))
        if t > 0.25:
            q = t - 0.25
            put(im, ring, W / 2, 900, 0.5 + 1.8 * clamp(q / 0.5), clamp(1 - q / 0.5))
        if sub:
            put(im, sub, W / 2, 1120, ease_out_back((t - 0.55) / 0.4))
        sparkles(im, t, 6, (255, 255, 255), seed=17)
        return im
    return frame


def tpl_sticker(spec, brand, bg):
    """Icono suelto sobre el video (fondo transparente)."""
    size = int(spec.get("size", 200))
    px, py = spec.get("pos", [0.84, 0.19])
    accent = rgb(brand["accent_color"])
    disc = sprite(size, size, lambda d, k: d.ellipse([0, 0, size * k - 1, size * k - 1], fill=accent))
    ic = icon(spec.get("icon", "star"), int(size * 0.56), rgb(brand["on_accent_color"]))
    disc.paste(ic, (int(size * 0.22), int(size * 0.22)), ic)
    ring = sprite(size * 2, size * 2, lambda d, k: d.ellipse([4 * k, 4 * k, size * 2 * k - 4 * k, size * 2 * k - 4 * k], outline=accent + (255,), width=8 * k))
    lab = chip(spec["label"].upper(), 44, (255, 255, 255), rgb(brand["dark_color"]), padx=34, pady=16, max_w=380) if spec.get("label") else None
    dur = float(spec.get("dur", 1.6))

    def frame(t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        s = ease_out_back(t / 0.35, 2.2)
        out = clamp((dur - t) / 0.25)
        wob = 10 * math.exp(-t * 3.5) * math.sin(t * 16)
        q = (t * 1.6) % 1.0
        put(im, ring, W * px, H * py, 0.5 + 0.7 * q, (1 - q) * 0.7 * out)
        put(im, disc, W * px, H * py + 6 * math.sin(t * 4), s * out, out, rot=wob)
        if lab:
            put(im, lab, W * px, H * py + size * 0.78, ease_out_back((t - 0.25) / 0.3) * out, out)
        return im
    return frame



def tpl_panel(spec, brand, bg):
    """Panel de cristal con 2-3 conceptos separados por símbolos (×, =, ≠, →), sobre el video (sin fondo)."""
    items = spec.get("items") or [{"icon": "x", "text": "A"}, {"icon": "check", "text": "B"}]
    syms = spec.get("symbols") or ["≠"] * (len(items) - 1)
    px, py = spec.get("pos", [0.5, 0.185])
    pw, ph = int(spec.get("width", 940)), int(spec.get("height", 300))
    dur = float(spec.get("dur", 2.4))
    acc, pri = rgb(brand["accent_color"]), rgb(brand["primary_color"])
    panel = rrect(pw, ph, 44, (10, 13, 24, 232), outline=acc + (255,), ow=3)
    glow = rrect(pw + 40, ph + 40, 60, acc + (70,))
    n = len(items)
    slot = pw / n
    icons = []
    for i, it in enumerate(items):
        disc = sprite(120, 120, lambda d, k, c=(acc if i % 2 == 0 else pri): d.ellipse([0, 0, 120 * k - 1, 120 * k - 1], fill=c))
        ic = icon(it.get("icon", "star"), 66, (255, 255, 255))
        disc.paste(ic, (27, 27), ic)
        lab = text_sprite(it["text"].upper(), 40, (255, 255, 255), heavy=True, max_w=int(slot - 60))
        icons.append((disc, lab))
    sym_sprites = [icon("neq", 80, acc) if sy == "≠" else text_sprite(sy, 96, acc, heavy=True) for sy in syms]

    def frame(t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        e = ease_out_back(t / 0.45, 1.5)
        out = clamp((dur - t) / 0.25)
        cy = H * py + (1 - clamp(e)) * -260
        sc = clamp(e, 0.01, 1.06) * out
        put(im, glow, W * px, cy, sc, 0.6 * out)
        put(im, panel, W * px, cy, sc, out)
        x0 = W * px - pw / 2
        for i, (disc, lab) in enumerate(icons):
            tt = 0.3 + 0.28 * i
            q = ease_out_back((t - tt) / 0.35, 2.0) * out
            cx = x0 + slot * (i + 0.5)
            put(im, disc, cx, cy - 36, q)
            put(im, lab, cx, cy + 78, q)
            if i < len(sym_sprites):
                put(im, sym_sprites[i], x0 + slot * (i + 1), cy - 30, ease_out_back((t - tt - 0.14) / 0.3, 2.4) * out)
        return im
    return frame

# ====================================================================================
#  KIT "UI" — tarjetas con borde grueso y sombra dura (look del video de referencia)
#  Todas son overlays SIN fondo: se pegan sobre el video en la zona libre (arriba o a los lados).
# ====================================================================================
INK = (8, 10, 18)
PAPER = (246, 248, 253)
GREY = (86, 92, 110)


def _cols(brand):
    return dict(acc=rgb(brand["accent_color"]), acc2=rgb(brand["accent2_color"]),
                deep=rgb(brand.get("deep_color", "#0F2147")), warm=rgb(brand.get("warm_color", "#FE6605")),
                ink=INK, paper=PAPER, white=(255, 255, 255))


def icon2(kind, s, color):
    """Iconos extra del kit UI (trazo limpio)."""
    def fn(d, k):
        S = s * k
        P = lambda pts: [(x * S, y * S) for x, y in pts]
        w = int(.09 * S)
        L = lambda pts, wd=w: d.line(P(pts), fill=color, width=wd, joint="curve")
        if kind == "scissors":
            L([(.30, .10), (.72, .64)]); L([(.70, .10), (.28, .64)])
            for cx in (.27, .73):
                d.ellipse([(cx - .15) * S, .60 * S, (cx + .15) * S, .90 * S], outline=color, width=int(.08 * S))
        elif kind == "video":
            d.rounded_rectangle([.06 * S, .24 * S, .62 * S, .76 * S], .09 * S, outline=color, width=w)
            d.polygon(P([(.68, .42), (.94, .26), (.94, .74), (.68, .58)]), fill=color)
        elif kind == "send":
            L([(.10, .48), (.90, .12), (.60, .90), (.46, .56), (.10, .48)], int(.07 * S)); L([(.46, .56), (.90, .12)], int(.06 * S))
        elif kind == "wand":
            L([(.16, .84), (.66, .34)], int(.11 * S))
            d.polygon(P([(.76, .08), (.82, .24), (.98, .30), (.82, .36), (.76, .52), (.70, .36), (.54, .30), (.70, .24)]), fill=color)
        elif kind == "music":
            L([(.40, .72), (.40, .20)], int(.07 * S)); L([(.80, .62), (.80, .10)], int(.07 * S))
            d.polygon(P([(.40, .20), (.80, .10), (.80, .24), (.40, .34)]), fill=color)
            d.ellipse([.16 * S, .60 * S, .42 * S, .84 * S], fill=color); d.ellipse([.56 * S, .52 * S, .82 * S, .76 * S], fill=color)
        elif kind == "layout":
            d.rounded_rectangle([.10 * S, .12 * S, .90 * S, .88 * S], .08 * S, outline=color, width=w)
            L([(.10, .38), (.90, .38)], int(.07 * S)); L([(.42, .38), (.42, .88)], int(.07 * S))
        elif kind == "expand":
            for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                cx, cy = .5 + sx * .36, .5 + sy * .36
                L([(cx - sx * .24, cy), (cx, cy), (cx, cy - sy * .24)], int(.08 * S))
        elif kind == "captions":
            d.rounded_rectangle([.06 * S, .20 * S, .94 * S, .80 * S], .12 * S, outline=color, width=w)
            L([(.22, .46), (.42, .46)], int(.07 * S)); L([(.52, .46), (.78, .46)], int(.07 * S)); L([(.22, .62), (.58, .62)], int(.07 * S))
        elif kind == "scan":
            for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                cx, cy = .5 + sx * .38, .5 + sy * .38
                L([(cx - sx * .22, cy), (cx, cy), (cx, cy - sy * .22)], int(.08 * S))
            d.ellipse([.36 * S, .36 * S, .64 * S, .64 * S], outline=color, width=int(.07 * S))
        elif kind == "brain":
            d.ellipse([.10 * S, .12 * S, .90 * S, .88 * S], outline=color, width=w)
            L([(.5, .20), (.5, .80)], int(.06 * S)); L([(.5, .38), (.30, .38)], int(.06 * S)); L([(.5, .62), (.70, .62)], int(.06 * S))
        elif kind == "play":
            d.polygon(P([(.30, .18), (.84, .50), (.30, .82)]), fill=color)
        elif kind == "chat":
            d.rounded_rectangle([.06 * S, .12 * S, .94 * S, .70 * S], .16 * S, fill=color)
            d.polygon(P([(.22, .66), (.22, .94), (.50, .66)]), fill=color)
        elif kind == "arrow_down":
            L([(.5, .08), (.5, .80)], int(.12 * S)); L([(.20, .56), (.5, .88), (.80, .56)], int(.12 * S))
        elif kind == "gauge":
            d.ellipse([.08 * S, .08 * S, .92 * S, .92 * S], outline=color, width=w)
            L([(.5, .5), (.74, .30)], int(.09 * S)); d.ellipse([.42 * S, .42 * S, .58 * S, .58 * S], fill=color)
        elif kind == "user":
            d.ellipse([.30 * S, .10 * S, .70 * S, .50 * S], fill=color)
            d.pieslice([.14 * S, .56 * S, .86 * S, 1.30 * S], 180, 360, fill=color)
        elif kind == "globe":
            d.ellipse([.08 * S, .08 * S, .92 * S, .92 * S], outline=color, width=int(.07 * S))
            d.ellipse([.32 * S, .08 * S, .68 * S, .92 * S], outline=color, width=int(.06 * S)); L([(.08, .5), (.92, .5)], int(.06 * S))
        elif kind == "mic":
            d.rounded_rectangle([.36 * S, .06 * S, .64 * S, .58 * S], .14 * S, fill=color)
            d.arc([.22 * S, .30 * S, .78 * S, .78 * S], 0, 180, fill=color, width=int(.07 * S)); L([(.5, .78), (.5, .94)], int(.07 * S))
    return sprite(s, s, fn)


_icon_base = icon


def icon(kind, s, color, accent=(255, 255, 255)):  # noqa: F811  (extiende el catálogo de iconos)
    if kind in ("scissors", "video", "send", "wand", "music", "layout", "expand", "captions", "scan", "brain", "play",
                "chat", "arrow_down", "gauge", "user", "globe", "mic"):
        return icon2(kind, s, color)
    return _icon_base(kind, s, color, accent)


def ui_card(w, h, fill=PAPER, border=INK, bw=5, r=22, off=11):
    """Tarjeta con borde grueso y sombra dura desplazada."""
    def fn(d, k):
        d.rounded_rectangle([off * k, off * k, (w + off) * k - 1, (h + off) * k - 1], r * k, fill=INK + (235,))
        d.rounded_rectangle([0, 0, w * k - 1, h * k - 1], r * k, fill=tuple(fill) + (255,), outline=tuple(border) + (255,), width=bw * k)
    return sprite(w + off, h + off, fn)


def outlined(text, size, fill, stroke_col, sw, max_w=None, mono=False):
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    f = fit_font(tmp, text, max_w, size) if max_w else font(size, mono)
    bb = tmp.textbbox((0, 0), text, font=f, stroke_width=sw)
    w, h = bb[2] - bb[0] + 2 * sw + 10, bb[3] - bb[1] + 2 * sw + 10
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((sw + 5 - bb[0], sw + 5 - bb[1]), text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke_col)
    return im


def pill(text, size, fill, color, border=None, padx=26, pady=12, r=10, mono=True, bw=0):
    t = text_sprite(text, size, color, heavy=False, mono=mono)
    w, h = t.width + padx * 2, t.height + pady * 2
    base = rrect(w, h, r, fill + (255,) if len(fill) == 3 else fill, outline=(border + (255,)) if border else None, ow=bw)
    base.paste(t, (padx, pady), t)
    return base


def _pop(t, t0, d=0.35, s=2.0):
    return ease_out_back((t - t0) / d, s)


def _out(t, dur, f=0.25):
    return clamp((dur - t) / f)


def _blank():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def tpl_kicker_slam(spec, brand, bg):
    """Palabra gigante con etiqueta mono encima ('VAMOS A CREAR UNA' / GUÍA). Sin fondo."""
    c = _cols(brand)
    size, dur = int(spec.get("size", 250)), float(spec.get("dur", 2.4))
    px, py = spec.get("pos", [0.5, 0.2])
    word = outlined(spec["text"].upper(), size, (255, 255, 255), INK, max(6, size // 22), max_w=int(spec.get("max_w", 980)))
    kick = pill(spec.get("kicker", "").upper(), 34, c["deep"], c["acc2"], border=c["acc"], bw=3) if spec.get("kicker") else None
    bar = rrect(max(80, word.width - 40), 16, 8, c["acc"] + (255,))

    def frame(t):
        im, o = _blank(), _out(t, dur)
        p = clamp(t / 0.22)
        sc = (1 + 0.9 * (1 - ease_out_cubic(p))) * o if p < 1 else 1 + 0.03 * math.sin(t * 6) * math.exp(-(t - 0.22) * 3)
        shake = 14 * math.exp(-max(0, t - 0.2) * 8) * math.sin(t * 60) if t > 0.2 else 0
        put(im, word, W * px + shake, H * py, sc * (0.4 + 0.6 * o), clamp(p * 3) * o)
        put(im, bar, W * px, H * py + word.height * 0.52, 1, clamp((t - 0.25) / 0.3) * o)
        if kick:
            put(im, kick, W * px, H * py - word.height * 0.58 - (1 - clamp(_pop(t, 0.05, 0.3))) * 40, clamp(_pop(t, 0.05, 0.3), 0.01, 1.05) * o, o)
        return im
    return frame


def tpl_toast(spec, brand, bg):
    """Notificaciones (mensajes directos) que bajan una tras otra. Úsalo solo con lo que el creador dice que le escriben."""
    c = _cols(brand)
    items = spec.get("items") or [{"user": "usuario***", "text": "¿cómo lo haces?"}]
    px, py = spec.get("pos", [0.5, 0.09])
    dur = float(spec.get("dur", 3.0))
    cw, ch = 960, 150
    sprites = []
    for it in items:
        card = rrect(cw, ch, 40, (252, 252, 255, 246), outline=(210, 214, 228, 255), ow=2)
        disc = sprite(84, 84, lambda d, k: d.ellipse([0, 0, 84 * k - 1, 84 * k - 1], fill=c["acc"]))
        ic = icon("chat", 46, (255, 255, 255))
        disc.paste(ic, (19, 21), ic)
        card.paste(disc, (34, 33), disc)
        u = text_sprite(it.get("user", "usuario***"), 34, INK, heavy=True, max_w=520)
        m = text_sprite(it.get("text", ""), 32, GREY, max_w=720)
        a = text_sprite("ahora", 26, (150, 156, 172))
        card.paste(u, (140, 28), u); card.paste(m, (140, 82), m); card.paste(a, (cw - a.width - 40, 30), a)
        if it.get("badge"):
            bd = sprite(46, 46, lambda d, k: d.ellipse([0, 0, 46 * k - 1, 46 * k - 1], fill=c["warm"]))
            bt = text_sprite(str(it["badge"]), 28, (255, 255, 255), heavy=True)
            bd.paste(bt, ((46 - bt.width) // 2, (46 - bt.height) // 2), bt)
            card.paste(bd, (cw - 62, 8), bd)
        sprites.append(card)
    times = [float(it.get("t", i * 1.1)) for i, it in enumerate(items)]
    ghost = rrect(cw, ch, 40, (240, 242, 250, 255))

    def frame(t):
        im = _blank()
        for i, sp in enumerate(sprites):
            t0 = times[i]
            t1 = times[i + 1] if i + 1 < len(times) else dur
            if t < t0 or t > t1 + 0.05:
                continue
            e = _pop(t, t0, 0.38, 1.6)
            y = H * py + (1 - clamp(e)) * -220
            leave = clamp((t1 - t) / 0.2) if i + 1 < len(times) else _out(t, dur)
            y -= (1 - leave) * 120
            put(im, ghost, W * px, y + 30, 0.90, 0.55 * leave)
            put(im, ghost, W * px, y + 16, 0.95, 0.8 * leave)
            put(im, sp, W * px, y, max(0.01, clamp(e, 0, 1.04)), leave)
        return im
    return frame


def tpl_ui_meter(spec, brand, bg):
    """Medidor de dos barras verticales (A vs B): una baja, otra sube. Sin fondo."""
    c = _cols(brand)
    px, py = spec.get("pos", [0.15, 0.36])
    dur = float(spec.get("dur", 3.2))
    cw, chh = 310, 440
    bars = spec.get("bars") or [{"label": "editar", "icon": "scissors", "value": 0.85, "t": 0.5, "color": "ink"},
                                {"label": "crear", "icon": "video", "value": 0.15, "t": 0.9, "color": "acc"}]
    card = ui_card(cw, chh)
    k1 = text_sprite(spec.get("kicker", "PARA").upper(), 24, GREY, mono=True)
    ti = text_sprite(spec.get("title", "CREADORES").upper(), 34, c["acc"], heavy=True, mono=True, max_w=210)
    card.paste(k1, (24, 18), k1); card.paste(ti, (24, 48), ti)
    gi = icon("gauge", 56, INK)
    card.paste(gi, (cw - 84, 22), gi)
    n = len(bars)
    tw, th, top = 96, 260, 112
    xs = [int(cw * (i + 1) / (n + 1)) for i in range(n)]
    for b, x in zip(bars, xs):
        ic = icon(b.get("icon", "star"), 38, INK)
        card.paste(ic, (x - 19, top + th + 14), ic)
        lb = text_sprite(b.get("label", ""), 26, INK, max_w=140)
        card.paste(lb, (x - lb.width // 2, top + th + 58), lb)

    def frame(t):
        im, o = _blank(), _out(t, dur)
        fr = card.copy()
        d = ImageDraw.Draw(fr)
        for b, x in zip(bars, xs):
            d.rounded_rectangle([x - tw // 2, top, x + tw // 2, top + th], 14, fill=(224, 228, 240), outline=INK, width=4)
            p = ease_out_cubic((t - float(b.get("t", 0.5))) / 0.8)
            hh = int((th - 8) * float(b.get("value", 0.5)) * p)
            if hh > 4:
                col = c["acc"] if b.get("color") == "acc" else INK
                d.rounded_rectangle([x - tw // 2 + 4, top + th - 4 - hh, x + tw // 2 - 4, top + th - 4], 10, fill=col)
        e = clamp(_pop(t, 0.0, 0.4, 1.8), 0.01, 1.05)
        put(im, fr, W * px, H * py, e * (0.5 + 0.5 * o), o)
        return im
    return frame


def tpl_ui_flow(spec, brand, bg):
    """Flujo vertical de pasos (uno 'no es esto', otro resaltado). Sin fondo."""
    c = _cols(brand)
    px, py = spec.get("pos", [0.15, 0.40])
    dur = float(spec.get("dur", 3.6))
    steps = spec.get("steps") or [{"icon": "video", "label": "grabar", "state": "no", "stamp": "NO ES ESTO", "t": 0.5},
                                  {"icon": "wand", "label": "editar", "state": "hot", "t": 1.0},
                                  {"icon": "send", "label": "publicar", "state": "normal", "t": 1.5}]
    cw = 300
    sh, gap, head = 112, 54, 100
    chh = head + len(steps) * sh + (len(steps) - 1) * gap + 40
    card = ui_card(cw, chh)
    k1 = text_sprite(spec.get("kicker", "LA GUÍA").upper(), 24, GREY, mono=True, max_w=250)
    ti = text_sprite(spec.get("title", "OPTIMIZA").upper(), 36, c["acc"], heavy=True, mono=True, max_w=250)
    card.paste(k1, (24, 18), k1); card.paste(ti, (24, 48), ti)
    tiles = []
    for s in steps:
        hot = s.get("state") == "hot"
        tile = rrect(cw - 56, sh, 16, (c["acc"] if hot else PAPER) + (255,), outline=INK + (255,), ow=4)
        col = (255, 255, 255) if hot else INK
        ic = icon(s.get("icon", "star"), 44, col)
        tile.paste(ic, ((cw - 56 - 44) // 2, 14), ic)
        lb = text_sprite(s.get("label", ""), 28, col, max_w=190)
        tile.paste(lb, ((cw - 56 - lb.width) // 2, 66), lb)
        stamp = None
        if s.get("stamp"):
            tt = text_sprite(s["stamp"].upper(), 26, c["warm"], heavy=True, mono=True)
            stamp = rrect(tt.width + 28, tt.height + 16, 6, (255, 255, 255, 255), outline=c["warm"] + (255,), ow=3)
            stamp.paste(tt, (14, 8), tt)
        tiles.append((tile, stamp))
    arrow = icon("arrow_down", 34, INK)
    y0 = -chh / 2 + head + sh / 2

    def frame(t):
        im, o = _blank(), _out(t, dur)
        e = clamp(_pop(t, 0.0, 0.4, 1.8), 0.01, 1.05)
        cx, cy = W * px, H * py
        put(im, card, cx, cy, e * (0.5 + 0.5 * o), o)
        for i, (tile, stamp) in enumerate(tiles):
            ty = cy + (y0 + i * (sh + gap)) * e
            q = clamp(_pop(t, float(steps[i].get("t", 0.5 + i * 0.5)), 0.35, 2.0), 0, 1.06) * o
            put(im, tile, cx - 5, ty, q, o)
            if i < len(tiles) - 1:
                put(im, arrow, cx - 5, ty + (sh + gap) / 2, clamp(_pop(t, float(steps[i].get("t", 0.5)) + 0.2, 0.3)) * o, o)
            if stamp is not None:
                sq = clamp(_pop(t, float(steps[i].get("t", 0.5)) + 0.3, 0.3, 2.6), 0, 1.1) * o
                put(im, stamp, cx - 5, ty + 6, sq, o, rot=-7)
        return im
    return frame


def tpl_ui_iconrow(spec, brand, bg):
    """Fila de iconos con etiqueta que van apareciendo (herramientas, pasos, plataformas). 1 icono = ficha suelta."""
    c = _cols(brand)
    items = spec.get("items") or [{"icon": "captions", "label": "subtítulos"}, {"icon": "scan", "label": "tracking"},
                                  {"icon": "music", "label": "sonido"}]
    px, py = spec.get("pos", [0.5, 0.12])
    dur = float(spec.get("dur", 3.0))
    n = len(items)
    tile = min(170, int(960 / n) - 18)
    cards = []
    for it in items:
        cd = ui_card(tile, tile, r=18, bw=4, off=8)
        ic = icon(it.get("icon", "star"), int(tile * 0.36), INK)
        cd.paste(ic, ((tile - ic.width) // 2, int(tile * 0.16)), ic)
        lb = text_sprite(it.get("label", ""), max(22, int(tile * 0.2)), INK, max_w=tile - 14)
        cd.paste(lb, ((tile - lb.width) // 2, int(tile * 0.62)), lb)
        cards.append(cd)
    gap = tile + 16

    def frame(t):
        im, o = _blank(), _out(t, dur)
        x0 = W * px - gap * (n - 1) / 2
        for i, cd in enumerate(cards):
            q = clamp(_pop(t, float(items[i].get("t", i * 0.22)), 0.33, 2.2), 0, 1.08) * o
            put(im, cd, x0 + i * gap, H * py + 5 * math.sin(t * 3 + i), q, o)
        return im
    return frame


def tpl_ui_tag(spec, brand, bg):
    """Etiqueta de acción: 'Comenta GUÍA' (palabra clave en caja clara). Sin fondo."""
    c = _cols(brand)
    px, py = spec.get("pos", [0.75, 0.115])
    dur = float(spec.get("dur", 3.0))
    lead = text_sprite(spec.get("lead", "Responde"), 44, (255, 255, 255), heavy=True)
    kw = text_sprite(spec.get("keyword", "GUÍA").upper(), 64, INK, heavy=True, max_w=560)
    box_w = kw.width + 30
    w, h = lead.width + box_w + 80, kw.height + 40
    base = ui_card(w, h, fill=c["acc"], r=16, bw=4, off=8)
    base.paste(lead, (28, (h - lead.height) // 2), lead)
    kb = rrect(box_w, kw.height + 10, 10, (255, 255, 255, 255), outline=INK + (255,), ow=3)
    kb.paste(kw, (15, 5), kw)
    base.paste(kb, (lead.width + 48, (h - kb.height) // 2), kb)

    def frame(t):
        im, o = _blank(), _out(t, dur)
        put(im, base, W * px, H * py + 6 * math.sin(t * 4), clamp(_pop(t, 0.0, 0.4, 2.2), 0.01, 1.08) * o, o, rot=-2 * math.sin(t * 3))
        return im
    return frame


def tpl_ui_cta(spec, brand, bg):
    """Tarjeta de cierre: etiqueta, 'Responde X', línea mono y flecha que rebota. Sin fondo."""
    c = _cols(brand)
    px, py = spec.get("pos", [0.5, 0.80])
    dur = float(spec.get("dur", 3.4))
    cw, chh = 860, 270
    card = ui_card(cw, chh, r=22, bw=5, off=11)
    k = text_sprite(spec.get("kicker", "LISTA DE ESPERA").upper(), 26, GREY, mono=True, max_w=700)
    card.paste(k, ((cw - k.width) // 2, 20), k)
    lead = text_sprite(spec.get("lead", "Responde"), 44, (255, 255, 255), heavy=True)
    kw = text_sprite(spec.get("keyword", "GUÍA").upper(), 80, (255, 255, 255), heavy=True, max_w=420)
    plate_w, plate_h = lead.width + kw.width + 90, kw.height + 36
    plate = rrect(plate_w, plate_h, 14, c["acc"] + (255,), outline=INK + (255,), ow=4)
    plate.paste(lead, (30, (plate_h - lead.height) // 2 + 6), lead)
    plate.paste(kw, (lead.width + 54, (plate_h - kw.height) // 2), kw)
    card.paste(plate, ((cw - plate_w) // 2, 62), plate)
    sub = text_sprite(spec.get("sub", "").upper(), 22, GREY, mono=True, max_w=760) if spec.get("sub") else None
    if sub:
        card.paste(sub, ((cw - sub.width) // 2, chh - 52), sub)
    arrow = icon("arrow_down", 64, INK)

    def frame(t):
        im, o = _blank(), _out(t, dur)
        put(im, card, W * px, H * py, clamp(_pop(t, 0.0, 0.45, 1.9), 0.01, 1.06) * o, o)
        put(im, arrow, W * px, H * py + chh / 2 + 56 + 12 * abs(math.sin(t * 4)), clamp(_pop(t, 0.5, 0.3)) * o, o)
        return im
    return frame


def tpl_phone(spec, brand, bg):
    """Mockup de teléfono con pantalla genérica (sin contenido de terceros) y etiqueta mono debajo."""
    c = _cols(brand)
    px, py = spec.get("pos", [0.14, 0.40])
    dur = float(spec.get("dur", 2.6))
    pw, ph = 190, 340
    tilt = float(spec.get("tilt", -4))

    def fn(d, k):
        d.rounded_rectangle([0, 0, pw * k - 1, ph * k - 1], 34 * k, fill=INK + (255,))
        d.rounded_rectangle([10 * k, 12 * k, (pw - 10) * k, (ph - 12) * k], 26 * k, fill=PAPER + (255,))
        d.rounded_rectangle([70 * k, 18 * k, 120 * k, 26 * k], 4 * k, fill=INK + (255,))
        d.rounded_rectangle([22 * k, 44 * k, (pw - 22) * k, 190 * k], 14 * k, fill=c["deep"] + (255,))
        d.polygon([(22 * k, 190 * k), ((pw - 22) * k, 120 * k), ((pw - 22) * k, 190 * k), (22 * k, 190 * k)], fill=c["acc"] + (255,))
        for i, wd in enumerate((120, 90, 106)):
            d.rounded_rectangle([22 * k, (208 + i * 24) * k, (22 + wd) * k, (216 + i * 24) * k], 4 * k, fill=(205, 210, 226, 255))
        d.ellipse([(pw / 2 - 26) * k, 94 * k, (pw / 2 + 26) * k, 146 * k], fill=(255, 255, 255, 235))
    body = sprite(pw, ph, fn)
    pl = icon("play", 28, INK)
    body.paste(pl, (pw // 2 - 12, 107), pl)
    lab = pill(spec.get("label", "REELS").upper(), 26, INK, (255, 255, 255), padx=20, pady=8, r=8)

    def frame(t):
        im, o = _blank(), _out(t, dur)
        e = clamp(_pop(t, 0.0, 0.42, 2.0), 0.01, 1.08)
        put(im, body, W * px, H * py + 8 * math.sin(t * 3), e * o, o, rot=tilt + 2 * math.sin(t * 2))
        put(im, lab, W * px, H * py + ph / 2 + 30, clamp(_pop(t, 0.25, 0.3)) * o, o)
        return im
    return frame


UI_TEMPLATES = {"kicker_slam": tpl_kicker_slam, "toast": tpl_toast, "ui_meter": tpl_ui_meter, "ui_flow": tpl_ui_flow,
                "ui_iconrow": tpl_ui_iconrow, "ui_tag": tpl_ui_tag, "ui_cta": tpl_ui_cta, "phone": tpl_phone}
OVERLAY_TPLS = {"sticker", "panel"} | set(UI_TEMPLATES)


TEMPLATES = {"alert": tpl_alert, "pillars": tpl_pillars, "partner": tpl_partner, "growth": tpl_growth,
             "strike": tpl_strike, "terminal": tpl_terminal, "orbit": tpl_orbit, "meter": tpl_meter,
             "slam": tpl_slam, "sticker": tpl_sticker, "panel": tpl_panel, **UI_TEMPLATES}
VARIANTS = ["blue", "deep", "bright", "flat"]   # "warm" (naranja) solo si lo pides con "bg": "warm"
INS = ["iris", "wipe_l", "glitch", "blinds", "wipe_u", "diag", "wipe_r"]
OUTS = ["wipe_d", "iris", "blinds", "glitch", "diag", "wipe_l", "wipe_u"]


# ---------------------------------------------------------------- render
def compose(rgba, t, dur, spec):
    arr = np.asarray(rgba, dtype=np.uint8)
    rgb_arr, alpha = arr[..., :3], arr[..., 3]
    if spec["template"] in OVERLAY_TPLS:
        return rgb_arr, alpha
    in_d, out_d = float(spec.get("in_dur", 0.38)), float(spec.get("out_dur", 0.32))
    kind, p = None, 1.0
    if t < in_d:
        kind, p = spec["in"], ease_out_cubic(t / in_d)
    elif t > dur - out_d:
        kind, p = spec["out"], ease_out_cubic((dur - t) / out_d)
    if kind:
        m = trans_alpha(kind, p)
        if m is not None:
            alpha = (alpha.astype(np.uint16) * m // 255).astype(np.uint8)
        if kind == "glitch":
            rgb_arr = glitch_shift(rgb_arr, 1 - p)
    if spec.get("flash", True) and t < 0.17:
        f = (1 - t / 0.17) * 0.85
        rgb_arr = (rgb_arr.astype(np.float32) * (1 - f) + 255 * f).astype(np.uint8)
    return rgb_arr, alpha


def render(frame_fn, spec, dur, out):
    n = int(round(dur * FPS))
    enc = lambda pix, path, crf: subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", pix, "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    pc, pm = enc("rgb24", out, 16), enc("gray", out.replace(".mp4", ".matte.mp4"), 10)
    for i in range(n):
        t = i / FPS
        rgb_arr, alpha = compose(frame_fn(t), t, dur, spec)
        pc.stdin.write(np.ascontiguousarray(rgb_arr).tobytes())
        pm.stdin.write(np.ascontiguousarray(alpha).tobytes())
    for p in (pc, pm):
        p.stdin.close()
        p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cards")
    ap.add_argument("--brand")
    ap.add_argument("--out-dir", default="work/cards")
    ap.add_argument("--seed", type=int, default=0, help="cambia diseño/transiciones automáticos entre videos")
    ap.add_argument("--only", help="nombre de una sola tarjeta")
    ap.add_argument("--preview", action="store_true", help="solo PNG del estado final (y a mitad) de cada tarjeta")
    args = ap.parse_args()
    brand = load_brand(args.brand)
    global SANS_PREF, MONO_PREF
    SANS_PREF = [brand.get("font") or SANS_PREF[0]] + SANS_PREF
    MONO_PREF = [brand.get("mono_font") or MONO_PREF[0]] + MONO_PREF
    os.makedirs(args.out_dir, exist_ok=True)
    specs = json.load(open(args.cards, encoding="utf-8"))
    bgs = {}
    for i, spec in enumerate(specs):
        name = spec.get("name", spec["template"])
        if args.only and name != args.only:
            continue
        if spec["template"] not in TEMPLATES:
            sys.exit(f"Plantilla desconocida: {spec['template']}  (usa {', '.join(TEMPLATES)})")
        k = i + args.seed
        spec.setdefault("bg", VARIANTS[k % len(VARIANTS)])
        spec.setdefault("in", INS[(k * 3 + 1) % len(INS)])
        spec.setdefault("out", OUTS[(k * 2 + 2) % len(OUTS)])
        bg = bgs.setdefault(spec["bg"], BG(brand, spec["bg"]))
        fn = TEMPLATES[spec["template"]](spec, brand, bg)
        dur = float(spec.get("dur", 2.6))
        if args.preview:
            for tag, tt in (("a", dur * 0.55), ("b", dur - 0.4)):
                im = fn(tt).convert("RGB") if spec["template"] not in OVERLAY_TPLS else Image.alpha_composite(
                    Image.new("RGBA", (W, H), (60, 60, 70, 255)), fn(tt)).convert("RGB")
                im.save(os.path.join(args.out_dir, f"{name}_{tag}.png"))
            print(f"preview: {name} ({spec['template']}, bg={spec['bg']}, in={spec['in']}, out={spec['out']})")
        else:
            out = os.path.join(args.out_dir, name + ".mp4")
            render(fn, spec, dur, out)
            print(f"OK: {out} ({dur:.1f}s, {spec['template']}, bg={spec['bg']}, in={spec['in']}, out={spec['out']})")


if __name__ == "__main__":
    main()
