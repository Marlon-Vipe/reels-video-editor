"""Utilidades compartidas por los scripts de la skill reels-video-editor."""
import json
import os
import re
import subprocess
import sys
import unicodedata

DEFAULT_BRAND = {
    # Valores neutros. Cada usuario los sobreescribe con su propio brand.json (ver assets/brand.example.json).
    "name": "Tu Nombre",
    "role": "Creador de contenido",
    "company": "",                # opcional: nombre de tu empresa/proyecto
    "company_keywords": [],       # palabras que, si se dicen en el video, activan el cierre de empresa
    "url": "",
    "cta": "",                    # frase del cierre de empresa
    "handle": "",                 # @usuario en redes (opcional)
    "personal_tag": "",           # línea 2 del cierre personal, p. ej. "Fitness y nutrición"
    "personal_cta": "Sígueme para más",
    "font": "Space Grotesk",      # cae a Montserrat > Poppins > Inter > Arial si no está instalada
    "mono_font": "JetBrains Mono",
    "primary_color": "#2563EB",   # placas, tarjetas, barras
    "accent_color": "#2563EB",    # hook, resaltados, chips
    "accent2_color": "#60A5FA",   # palabras clave sobre video (más claro = más legible)
    "dark_color": "#000000",
    "surface_color": "#131313",
    "deep_color": "#0B1B3F",      # tono profundo para degradados
    "warm_color": "#F97316",      # color de alerta: uso mínimo (un destello por video)
    "caption_active_color": "#4F8BFF",  # palabra activa del subtítulo
    "on_accent_color": "#FFFFFF",
    "text_color": "#FFFFFF",
    "logo": None,
    "vocabulary": "",             # nombres propios que la transcripción suele escribir mal
}


def load_brand(path=None):
    brand = dict(DEFAULT_BRAND)
    if path:
        with open(path, "r", encoding="utf-8") as f:
            brand.update({k: v for k, v in json.load(f).items() if v not in (None, "")})
    return brand


# ---------- colores y tiempos ASS ----------
def _rgb(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return h[0:2].upper(), h[2:4].upper(), h[4:6].upper()


def ass_style_color(hex_color, alpha=0):
    r, g, b = _rgb(hex_color)
    return f"&H{alpha:02X}{b}{g}{r}"


def ass_tag_color(hex_color):
    r, g, b = _rgb(hex_color)
    return f"&H{b}{g}{r}&"


def ass_time(sec):
    sec = max(0.0, float(sec))
    cs = int(round(sec * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def srt_time(sec):
    ms = int(round(max(0.0, sec) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ass_escape(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def norm_word(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]", "", w)


# ---------- fuentes ----------
def installed_fonts():
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return set()
    fams = set()
    for line in out.splitlines():
        for f in line.split(","):
            fams.add(f.strip().lower())
    return fams


def pick_font(preferred=None):
    have = installed_fonts()
    for f in ([preferred] if preferred else []) + ["Space Grotesk", "Montserrat", "Poppins", "Inter", "Arial", "Liberation Sans", "DejaVu Sans"]:
        if f and f.lower() in have:
            return f
    return preferred or "Arial"


# ---------- ffprobe ----------
def probe(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        sys.exit(f"ffprobe no pudo leer {path}:\n{r.stderr}")
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = [s for s in d["streams"] if s["codec_type"] == "audio"]
    if v is None:
        sys.exit("El archivo no tiene pista de video.")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    rot = rot or int(v.get("tags", {}).get("rotate", 0) or 0)
    if abs(rot) in (90, 270):  # ffmpeg autorota al decodificar: usar dimensiones ya rotadas
        w, h = h, w
    # r_frame_rate = tasa nominal; avg_frame_rate engaña en videos de celular con fps variable (VFR)
    num, den = (v.get("r_frame_rate") or v.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    dur = float(d["format"].get("duration") or v.get("duration") or 0)
    return {"width": w, "height": h, "fps": fps or 30.0, "duration": dur, "has_audio": bool(a)}


def parse_range_list(text):
    """'12.5-14, 40-41.2' -> [[12.5, 14.0], [40.0, 41.2]]"""
    out = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        a, b = part.split("-")
        out.append([float(a), float(b)])
    return out
