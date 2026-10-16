#!/usr/bin/env python3
"""Genera subtítulos animados (.ass) a partir de words_cut.json, y opcionalmente .srt.

Estilos:
  reels   : 1080x1920, 3 palabras por vez, MAYÚSCULAS, palabra activa resaltada + pop-in
  youtube : 1920x1080, líneas de hasta ~7 palabras, sin resaltado (lectura cómoda)
  minimal : como youtube pero más discreto (tamaño menor)

Uso:
  python make_captions.py work/words_cut.json --style reels --brand assets/brand.json \
      --emphasis "gratis,rápido,clave" --out work/captions.ass
  python make_captions.py work/words_cut.json --style youtube --out work/captions.ass --srt work/captions.srt
"""
import argparse
import json
import re
import sys

from common import (ass_escape, ass_style_color, ass_tag_color, ass_time, load_brand, norm_word,
                    pick_font, probe, srt_time)

STYLES = {
    #            resolución     tamaño  palabras  margenV  borde sombra resalta  mayús  escala-activa  máx-car
    "reels":   dict(res=(1080, 1920), size=92, words=3, margin_v=560, outline=8, shadow=3, hl=True, upper=True, scale=118, chars=18),
    # "ui": look del video de referencia (tarjetas UI): más pequeño, espaciado de letras, 4 palabras, sombra marcada
    "ui":      dict(res=(1080, 1920), size=64, words=4, margin_v=380, outline=6, shadow=4, hl=True, upper=True, scale=112, chars=24, spacing=2.5),
    "youtube": dict(res=(1920, 1080), size=58, words=7, margin_v=78, outline=4, shadow=2, hl=False, upper=False, scale=100, chars=38),
    "minimal": dict(res=(1920, 1080), size=46, words=8, margin_v=70, outline=3, shadow=1, hl=False, upper=False, scale=100, chars=44),
}


def clean(token, upper):
    t = token.strip()
    t = re.sub(r"[.,;:…]+$", "", t)       # quita puntuación final; conserva ? y !
    t = t.replace("¿", "").replace("¡", "") if upper else t
    return t.upper() if upper else t


def group_words(words, max_words, max_chars, max_gap=0.45):
    groups, cur = [], []
    for w in words:
        if cur:
            gap = w["start"] - cur[-1]["end"]
            chars = sum(len(x["word"]) + 1 for x in cur) + len(w["word"])
            prev = cur[-1]["word"].strip()
            end_sentence = bool(re.search(r"[.!?…]$", prev))
            end_clause = bool(re.search(r"[,;:]$", prev)) and len(cur) >= 2
            if len(cur) >= max_words or chars > max_chars or gap > max_gap or end_sentence or end_clause:
                groups.append(cur)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def build_ass(words, style_name, brand, res, font, emphasis, position, highlight, baseline=None, chapters=None):
    st = STYLES[style_name]
    W, H = res
    k = H / st["res"][1] if st["res"][1] > st["res"][0] else W / st["res"][0]
    size = int(st["size"] * k)
    margin_v = int(st["margin_v"] * k) if position == "lower" else int(H * 0.5 - size)
    if baseline:  # fracción de la altura donde queda la base del texto (0.80 = al 80% desde arriba)
        margin_v = int(H * (1 - baseline))
    outline, shadow = st["outline"] * k, st["shadow"] * k
    align = 2
    mlr = int(W * 0.08)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{ass_style_color(brand['text_color'])},{ass_style_color(brand['text_color'])},{ass_style_color('#000000')},{ass_style_color('#000000', 0x70)},-1,0,0,0,100,100,{st.get('spacing', 0) * k:.1f},0,1,{outline:.1f},{shadow:.1f},{align},{mlr},{mlr},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    acc = ass_tag_color(brand.get("caption_active_color") or brand["accent_color"])
    acc2 = ass_tag_color(brand["accent2_color"])
    emph = {norm_word(e) for e in emphasis}
    upper = st["upper"]
    groups = group_words(words, st["words"], st["chars"])
    events = []

    def chap_colors(t):
        for ch in chapters or []:
            if ch["start"] <= t < ch["end"]:
                return (ass_tag_color(ch["color"]) if ch.get("color") else acc,
                        ass_tag_color(ch["color2"]) if ch.get("color2") else acc2)
        return acc, acc2

    for gi, g in enumerate(groups):
        acc_g, acc2_g = chap_colors(g[0]["start"])
        toks = [ass_escape(clean(w["word"], upper)) for w in g]
        nxt_start = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else None

        def word_markup(j, active):
            t = toks[j]
            is_emph = norm_word(g[j]["word"]) in emph
            if active and highlight:
                tag = f"{{\\c{acc_g}\\fscx{st['scale']}\\fscy{st['scale']}}}"
            elif is_emph:
                tag = f"{{\\c{acc2_g}}}"
            else:
                return t
            return f"{tag}{t}{{\\r}}"

        if highlight:
            for i, w in enumerate(g):
                start = w["start"]
                if i + 1 < len(g):
                    end = g[i + 1]["start"]
                else:
                    end = w["end"] + 0.15
                    if nxt_start is not None:
                        end = min(end, nxt_start)
                end = max(end, start + 0.06)
                text = " ".join(word_markup(j, j == i) for j in range(len(g)))
                if i == 0:
                    text = "{\\fad(40,0)\\fscx86\\fscy86\\t(0,110,\\fscx100\\fscy100)}" + text
                events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{text}")
        else:
            start = g[0]["start"]
            end = g[-1]["end"] + 0.2
            if nxt_start is not None:
                end = min(end, nxt_start)
            text = " ".join(word_markup(j, False) for j in range(len(g)))
            events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{{\\fad(60,60)}}{text}")
    return header + "\n".join(events) + "\n"


def build_srt(words, max_words=9, max_chars=64):
    groups = group_words(words, max_words, max_chars, max_gap=0.6)
    out = []
    for i, g in enumerate(groups, 1):
        text = " ".join(w["word"].strip() for w in g)
        end = g[-1]["end"] + 0.1
        if i < len(groups):
            end = min(end, groups[i][0]["start"] - 0.01)
        out.append(f"{i}\n{srt_time(g[0]['start'])} --> {srt_time(max(end, g[0]['start'] + 0.2))}\n{text}\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("words", help="words_cut.json")
    ap.add_argument("--style", choices=STYLES.keys(), default="reels")
    ap.add_argument("--brand", help="ruta a brand.json")
    ap.add_argument("--video", help="video (para detectar la resolución real)")
    ap.add_argument("--res", help="WxH, p. ej. 1080x1920 (si no hay --video)")
    ap.add_argument("--font")
    ap.add_argument("--emphasis", default="", help="palabras clave a resaltar siempre, separadas por coma")
    ap.add_argument("--position", choices=["lower", "center"], default="lower")
    ap.add_argument("--baseline", type=float, help="posición vertical de la base del texto como fracción de la altura "
                    "(p. ej. 0.80). Úsalo si el rostro está muy cerca de la cámara y los subtítulos tapan la boca")
    ap.add_argument("--chapters", help="chapters.json: [{start,end,color,color2}] cambia el color del resaltado por sección")
    ap.add_argument("--no-highlight", action="store_true", help="desactiva el resaltado palabra por palabra")
    ap.add_argument("--out", default="work/captions.ass")
    ap.add_argument("--srt", help="también escribe un .srt (útil para subir a YouTube)")
    args = ap.parse_args()

    brand = load_brand(args.brand)
    with open(args.words, encoding="utf-8") as f:
        words = json.load(f)["words"]
    if not words:
        sys.exit("words_cut.json no tiene palabras.")

    if args.video:
        i = probe(args.video)
        res = (i["width"], i["height"])
    elif args.res:
        res = tuple(int(x) for x in args.res.lower().split("x"))
    else:
        res = STYLES[args.style]["res"]

    font = pick_font(args.font or brand.get("font"))
    emphasis = [e.strip() for e in args.emphasis.split(",") if e.strip()]
    highlight = STYLES[args.style]["hl"] and not args.no_highlight
    ass = build_ass(words, args.style, brand, res, font, emphasis, args.position, highlight, args.baseline,
                    json.load(open(args.chapters, encoding="utf-8")) if args.chapters else None)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(ass)
    print(f"OK: {args.out}  (estilo={args.style}, {res[0]}x{res[1]}, fuente={font}, {len(words)} palabras)")
    if args.srt:
        with open(args.srt, "w", encoding="utf-8") as f:
            f.write(build_srt(words))
        print(f"OK: {args.srt}")


if __name__ == "__main__":
    main()
