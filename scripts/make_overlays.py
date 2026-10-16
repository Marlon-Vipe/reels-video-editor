#!/usr/bin/env python3
"""Overlays animados en un .ass (se queman con export.py, encima de los subtítulos):
hook cinético, lower third, barra de progreso, callouts y cierre.

MARCA: por defecto el video es de MARCA PERSONAL: el lower third dice quién es el creador (brand.name/role)
y el cierre invita a seguirlo. Solo se activa el modo `company` (cierre empresa + cta + url) cuando en el video
se dice alguna de brand.company_keywords (autodetectado con --words) o se pide con --mode company.

Uso:
  python make_overlays.py --video work/cut.mp4 --brand assets/brand.json --words work/words_cut.json \
      --hook "¿La IA es tu psicóloga?" --hook-style auto --lower-third --progress --cta \
      --callouts work/callouts.json --out work/overlays.ass

Ganchos (--hook-style): plates (placas de color inclinadas que caen una a una), stack (palabras blancas y una
placa en la clave), glitch (separación RGB que tiembla). "auto" elige por --seed para que no se repitan.
--hook-emph "palabra" fuerza la palabra destacada.
Sincronía: con --words cada placa del gancho entra JUSTO cuando se dice su palabra (no antes); --hook-at para tiempos manuales,
--hook-times-out para guardar los tiempos y poner ahí los impactos de sonido.
"""
import argparse
import json
import re
import sys
import zlib

from common import (ass_escape, ass_style_color, ass_tag_color, ass_time, load_brand, norm_word, pick_font, probe)


def chunks_for(text, max_words=2, max_chars=13):
    words = text.split()
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or len(" ".join(cur + [w])) > max_chars):
            out.append(" ".join(cur))
            cur = []
        cur.append(w)
    if cur:
        out.append(" ".join(cur))
    return out


def _similar(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    import difflib
    return min(len(a), len(b)) >= 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def sync_hook_to_words(plates, words, window=25.0, max_skip=3):
    """Busca en la voz (words_cut.json) la frase del gancho y devuelve, para cada placa, el segundo en que se dice
    su primera palabra. Tolera palabras de relleno entre medio (hasta `max_skip`) y errores leves de transcripción.
    Devuelve None si el gancho no aparece dicho (≥ 60 % de sus palabras)."""
    plate_toks = [[norm_word(t) for t in p.split() if norm_word(t)] for p in plates]
    flat = [(pi, tok) for pi, toks in enumerate(plate_toks) for tok in toks]
    if not flat:
        return None
    cand = [(w["start"], norm_word(w["word"])) for w in words if w["start"] <= window]
    best = None
    for s0 in range(len(cand)):
        if not _similar(cand[s0][1], flat[0][1]) and not (len(flat) > 1 and _similar(cand[s0][1], flat[1][1])):
            continue
        j, hits = s0, {}
        for k, (pi, tok) in enumerate(flat):
            for jj in range(j, min(len(cand), j + max_skip + 1)):
                if _similar(cand[jj][1], tok):
                    hits[k] = cand[jj][0]
                    j = jj + 1
                    break
        score = len(hits)
        if best is None or score > best[0]:
            best = (score, hits)
    if not best or best[0] < max(1, 0.6 * len(flat)):
        return None
    hits = best[1]
    times = []
    for pi in range(len(plates)):
        ks = [k for k, (p, _) in enumerate(flat) if p == pi and k in hits]
        times.append(hits[ks[0]] if ks else None)
    for i, t in enumerate(times):          # placas sin coincidencia: entre sus vecinas
        if t is None:
            prev = next((times[q] for q in range(i - 1, -1, -1) if times[q] is not None), None)
            nxt = next((times[q] for q in range(i + 1, len(times)) if times[q] is not None), None)
            times[i] = (prev + nxt) / 2 if prev is not None and nxt is not None else (prev + 0.3 if prev is not None else max(0.0, nxt - 0.3))
    for i in range(1, len(times)):
        times[i] = max(times[i], times[i - 1] + 0.08)
    return times


def make_width_fn(family):
    """Devuelve f(texto, fs) -> ancho en px que ocupará `texto` en libass con la fuente `family` en negrita.
    libass interpreta Fontsize como alto de celda (ascenso+descenso), no como em: se calibra con las métricas reales."""
    try:
        import subprocess
        from PIL import ImageFont
        path = subprocess.run(["fc-match", "-f", "%{file}", f"{family}:bold"], capture_output=True, text=True).stdout
        base = ImageFont.truetype(path, 200)
        asc, desc = base.getmetrics()
        ratio = (asc + desc) / 200.0

        def width(txt, fs):
            em = fs / ratio
            return ImageFont.truetype(path, max(8, int(em))).getlength(txt) + len(txt) * 1.0
        return width
    except Exception:
        return lambda txt, f: len(txt) * f * 0.46


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video")
    ap.add_argument("--res")
    ap.add_argument("--duration", type=float)
    ap.add_argument("--brand")
    ap.add_argument("--font")
    ap.add_argument("--words", help="words_cut.json: sincroniza el gancho con la voz y detecta si se menciona la empresa")
    ap.add_argument("--mode", choices=["auto", "personal", "company"], default="auto")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--hook")
    ap.add_argument("--hook-style", choices=["auto", "plates", "stack", "glitch"], default="auto")
    ap.add_argument("--hook-emph")
    ap.add_argument("--chapters", help="chapters.json: [{start,end,num,label,color}] etiqueta de sección arriba")
    ap.add_argument("--hook-dur", type=float, default=3.0, help="duración MÍNIMA del gancho en pantalla")
    ap.add_argument("--no-hook-sync", action="store_true",
                    help="NO sincronizar el gancho con la voz (por defecto, si hay --words, cada placa entra justo cuando se dice su palabra)")
    ap.add_argument("--hook-lead", type=float, default=0.03, help="segundos antes del inicio de la palabra en que entra la placa (0.0-0.06)")
    ap.add_argument("--hook-hold", type=float, default=1.1, help="segundos que el gancho completo se queda después de la última palabra")
    ap.add_argument("--hook-words-per-plate", type=int, default=2, help="1 = una placa por palabra (más golpe); 2 = por defecto")
    ap.add_argument("--hook-at", help="tiempos manuales de entrada de cada placa, ej. '0.42,1.10,1.86' (si el gancho no es literal)")
    ap.add_argument("--hook-times-out", help="guarda en JSON los tiempos de cada placa (para poner el impacto de sonido justo ahí)")
    ap.add_argument("--no-flash", action="store_true")
    ap.add_argument("--lower-third", action="store_true")
    ap.add_argument("--lt-start", type=float, default=4.0)
    ap.add_argument("--lt-dur", type=float, default=3.8)
    ap.add_argument("--progress", action="store_true")
    ap.add_argument("--callouts")
    ap.add_argument("--cta", action="store_true")
    ap.add_argument("--cta-dur", type=float, default=3.5)
    ap.add_argument("--cta-tag", help="línea 2 del cierre personal (por defecto brand.personal_tag), p. ej. 'Fitness y nutrición'")
    ap.add_argument("--cta-line", help="línea 3 del cierre personal (por defecto brand.personal_cta), p. ej. 'Sígueme para más'")
    ap.add_argument("--hook-y", type=float)
    ap.add_argument("--lt-y", type=float)
    ap.add_argument("--callout-y", type=float)
    ap.add_argument("--cta-y", type=float)
    ap.add_argument("--out", default="work/overlays.ass")
    args = ap.parse_args()

    brand = load_brand(args.brand)
    if args.video:
        i = probe(args.video)
        W, H, dur = i["width"], i["height"], i["duration"]
    elif args.res and args.duration:
        W, H = (int(x) for x in args.res.lower().split("x"))
        dur = args.duration
    else:
        sys.exit("Indica --video, o bien --res y --duration.")

    # ---- modo de marca ----
    mode = args.mode
    if mode == "auto":
        mode = "personal"
        if args.words:
            ws = json.load(open(args.words, encoding="utf-8"))["words"]
            kws = brand.get("company_keywords") or ([brand["company"]] if brand.get("company") else [])
            kws = {norm_word(k) for k in kws if k}
            if kws and any(norm_word(w["word"]) in kws for w in ws):
                mode = "company"
    seed = args.seed if args.seed is not None else zlib.crc32((args.hook or "x").encode()) % 97
    style = args.hook_style if args.hook_style != "auto" else ["plates", "stack", "glitch"][seed % 3]

    portrait = H > W
    u = min(W, H) / 1080.0
    font = pick_font(args.font or brand.get("font"))
    C = {k: ass_tag_color(brand[k]) for k in ("accent_color", "primary_color", "text_color", "dark_color", "on_accent_color", "accent2_color")}
    acc, pri, wht, drk, onacc, acc2 = (C[k] for k in ("accent_color", "primary_color", "text_color", "dark_color", "on_accent_color", "accent2_color"))
    sz = lambda v: int(v * u)

    if portrait:
        y_bar, y_hook, y_lt, y_call_top, y_call_center, y_cta = 0.10, 0.135, 0.125, 0.135, 0.40, 0.125
        x_lt = 0.06
    else:
        y_bar, y_hook, y_lt, y_call_top, y_call_center, y_cta = 0.985, 0.10, 0.70, 0.16, 0.40, 0.30
        x_lt = 0.05
    y_hook = args.hook_y if args.hook_y is not None else y_hook
    y_lt = args.lt_y if args.lt_y is not None else y_lt
    y_call_top = args.callout_y if args.callout_y is not None else y_call_top
    y_cta = args.cta_y if args.cta_y is not None else y_cta

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Plate,{font},{sz(96)},&H00FFFFFF,&H00FFFFFF,{ass_style_color(brand['accent_color'])},&H99000000,-1,0,0,0,100,100,1,0,3,{sz(16)},{sz(8)},5,0,0,0,1
Style: Txt,{font},{sz(120)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,{sz(9)},{sz(5)},5,0,0,0,1
Style: Draw,{font},20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []

    def add(layer, start, end, style, text):
        end = min(end, dur)
        if end > start:
            ev.append(f"Dialogue: {layer},{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}")

    def rect(x, y, w, h, color, alpha="&H00&"):
        return f"{{\\an7\\pos({x},{y})\\p1\\bord0\\shad0\\1c{color}\\1a{alpha}}}m 0 0 l {w} 0 l {w} {h} l 0 {h}{{\\p0}}"

    cx = W // 2

    # ---------- flash + oscurecido del gancho ----------
    hook_end = 0.0

    # ---------- barra de progreso ----------
    if args.progress:
        bh = sz(12)
        y = int(H * y_bar) - (bh if not portrait else 0)
        add(1, 0, dur, "Draw", f"{{\\an7\\pos(0,{y})\\p1\\bord0\\shad0\\1c{wht}\\alpha&HC8&}}m 0 0 l {W} 0 l {W} {bh} l 0 {bh}{{\\p0}}")
        ms = int(dur * 1000)
        add(2, 0, dur, "Draw", f"{{\\an7\\pos(0,{y})\\p1\\bord0\\shad0\\1c{acc}\\clip(0,{y},0,{y + bh})\\t(0,{ms},\\clip(0,{y},{W},{y + bh}))}}"
                               f"m 0 0 l {W} 0 l {W} {bh} l 0 {bh}{{\\p0}}")

    # ---------- HOOK cinético ----------
    if args.hook:
        est_w = make_width_fn(font)                            # ancho real medido con la tipografía de marca (con respaldo aproximado)
        text = args.hook.upper()
        plates_txt = chunks_for(text, max_words=args.hook_words_per_plate, max_chars=14)
        avail = W * 0.92
        max_lines = 2 if portrait else 1
        fs, lines = sz(150 if portrait else 110), []
        while fs > sz(50):
            pad, gap = int(fs * 0.20), int(fs * 0.14)
            lines, cur, wsum = [], [], 0
            for ptxt in plates_txt:
                pw = est_w(ptxt, fs) + 2 * pad + gap
                if cur and wsum + pw > avail:
                    lines.append(cur)
                    cur, wsum = [], 0
                cur.append((ptxt, pw))
                wsum += pw
            lines.append(cur)
            if len(lines) <= max_lines and all(sum(pw for _, pw in ln) <= avail for ln in lines):
                break
            fs -= sz(4)
        pad, gap = int(fs * 0.20), int(fs * 0.14)
        line_h = int(fs * 1.62)
        y0 = int(H * y_hook) + fs // 2
        all_plates = [(ptxt, li, pi) for li, ln in enumerate(lines) for pi, (ptxt, _) in enumerate(ln)]
        n = len(all_plates)
        emph_i = None
        if args.hook_emph:
            for k, (ptxt, _, _) in enumerate(all_plates):
                if norm_word(args.hook_emph) in norm_word(ptxt):
                    emph_i = k
        if emph_i is None:
            emph_i = max(range(n), key=lambda k: max(len(w) for w in all_plates[k][0].split()))
        # ---- tiempos: cada placa entra JUSTO cuando se dice su primera palabra (no antes) ----
        plate_t = [0.10 + 0.27 * k for k in range(n)]
        sync_note = "escalonado fijo (sin --words)"
        if args.hook_at:
            manual = [float(v) for v in args.hook_at.split(",")]
            plate_t = [manual[min(k, len(manual) - 1)] for k in range(n)]
            sync_note = "manual (--hook-at)"
        elif args.words and not args.no_hook_sync:
            ws = json.load(open(args.words, encoding="utf-8"))["words"]
            found = sync_hook_to_words([p for p, _, _ in all_plates], ws)
            if found:
                plate_t = [max(0.0, t - args.hook_lead) for t in found]
                sync_note = "sincronizado con la voz"
            else:
                sync_note = "AVISO: no encontré el gancho literal en la voz; usa --hook-at o un gancho dicho tal cual"
        hook_start = plate_t[0]
        end_h = max(hook_start + args.hook_dur, plate_t[-1] + args.hook_hold)
        hook_info = {"start": round(hook_start, 3), "end": round(end_h, 3), "sync": sync_note,
                     "plates": [{"text": all_plates[k][0], "t": round(plate_t[k], 3)} for k in range(n)]}
        print("gancho:", sync_note, " | ", "  ".join(f"{p['text']}@{p['t']:.2f}s" for p in hook_info["plates"]))
        hook_end = end_h
        # flash blanco y oscurecido superior: arrancan con la PRIMERA palabra del gancho, no antes
        if not args.no_flash:
            add(9, hook_start, hook_start + 0.2, "Draw", f"{{\\an7\\pos(0,0)\\p1\\bord0\\shad0\\1c&HFFFFFF&\\t(0,200,\\1a&HFF&)}}m 0 0 l {W} 0 l {W} {H} l 0 {H}{{\\p0}}")
        dk = int((end_h - hook_start) * 1000)
        add(0, hook_start, end_h + 0.25, "Draw",
            f"{{\\an7\\pos(0,0)\\p1\\bord0\\shad0\\1c&H000000&\\1a&HFF&\\t(0,200,\\1a&HB0&)\\t({dk},{dk + 250},\\1a&HFF&)}}"
            f"m 0 0 l {W} 0 l {W} {int(H * 0.36)} l 0 {int(H * 0.36)}{{\\p0}}")
        if args.hook_times_out:
            json.dump(hook_info, open(args.hook_times_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        plate_cols = [(acc, onacc), (wht, drk), (pri, wht), (drk, acc)]
        rots = [-4, 3, -2.5, 3.5]
        row_x = {}
        for li, ln in enumerate(lines):
            total = sum(pw for _, pw in ln) - gap
            x = cx - total / 2
            for pi, (ptxt, pw) in enumerate(ln):
                row_x[(li, pi)] = x + (pw - gap) / 2
                x += pw
        for k, (ptxt, li, pi) in enumerate(all_plates):
            t0 = plate_t[k]
            y = y0 + li * line_h
            x = int(row_x[(li, pi)])
            size = int(fs * (1.10 if k == emph_i else 1.0))
            text_c = ass_escape(ptxt)
            dl = int((end_h - t0) * 1000)
            out = f"\\t({max(50, dl - 260)},{dl},\\alpha&HFF&\\fscx60\\fscy60)"
            if style == "plates":
                pc, tc = plate_cols[k % 4]
                rot = rots[k % 4]
                add(3, t0, end_h, "Plate", f"{{\\an5\\pos({x},{y})\\frz{rot}\\fs{size}\\bord{sz(44)}\\blur{sz(30)}\\3c{pc}\\1a&HFF&\\4a&HFF&\\alpha&H80&"
                                           f"\\fscx200\\fscy200\\t(0,110,\\fscx100\\fscy100){out}}}{text_c}")
                add(4, t0, end_h, "Plate", f"{{\\an5\\pos({x},{y})\\frz{rot}\\fs{size}\\bord{pad}\\shad{sz(9)}\\3c{pc}\\1c{tc}\\4c&H000000&"
                                           f"\\fscx230\\fscy230\\alpha&HFF&\\t(0,110,\\fscx100\\fscy100\\alpha&H00&)\\t(110,200,\\frz{rot * 0.5}){out}}}{text_c}")
            elif style == "stack":
                if k == emph_i:
                    add(4, t0, end_h, "Plate", f"{{\\an5\\pos({x},{y})\\frz-3\\fs{size}\\bord{pad}\\shad{sz(9)}\\3c{acc}\\1c{onacc}\\4c&H000000&"
                                               f"\\fscx260\\fscy260\\alpha&HFF&\\t(0,120,\\fscx100\\fscy100\\alpha&H00&){out}}}{text_c}")
                else:
                    add(4, t0, end_h, "Txt", f"{{\\an5\\pos({x},{y})\\fs{size}\\fscx250\\fscy250\\alpha&HFF&\\t(0,110,\\fscx100\\fscy100\\alpha&H00&)"
                                             f"\\t(110,190,\\fscx106\\fscy106)\\t(190,260,\\fscx100\\fscy100){out}}}{text_c}")
            else:  # glitch
                base = f"\\an5\\fs{size}\\bord{sz(6)}\\shad0"
                add(3, t0, end_h, "Txt", f"{{{base}\\1c&H0000FF&\\3c&H0000FF&\\alpha&H30&\\move({x - sz(22)},{y},{x - sz(5)},{y + 2},0,260){out}}}{text_c}")
                add(3, t0, end_h, "Txt", f"{{{base}\\1c&HFFFF00&\\3c&HFFFF00&\\alpha&H30&\\move({x + sz(22)},{y},{x + sz(5)},{y - 2},0,260){out}}}{text_c}")
                add(4, t0, end_h, "Txt", f"{{{base}\\pos({x},{y})\\1c&HFFFFFF&\\3c&H000000&\\bord{sz(8)}\\fscx130\\fscy130\\alpha&HFF&\\t(0,90,\\fscx100\\fscy100\\alpha&H00&){out}}}{text_c}")
                if k == emph_i:
                    add(5, t0 + 0.9, t0 + 0.96, "Txt", f"{{\\an5\\fs{size}\\pos({x + sz(30)},{y})\\1c{acc}\\3c{acc}\\alpha&H20&\\bord{sz(4)}}}{text_c}")
        # subrayado que barre bajo el gancho
        yl = y0 + (len(lines) - 1) * line_h + int(fs * 0.98)
        add(4, plate_t[-1] + 0.25, end_h, "Draw",
            f"{{\\an7\\pos({cx - sz(300)},{yl})\\p1\\bord0\\shad0\\1c{acc}\\clip({cx - sz(300)},{yl},{cx - sz(300)},{yl + sz(12)})"
            f"\\t(0,260,\\clip({cx - sz(300)},{yl},{cx + sz(300)},{yl + sz(12)}))}}m 0 0 l {sz(600)} 0 l {sz(600)} {sz(12)} l 0 {sz(12)}{{\\p0}}")

    # ---------- etiqueta de capítulo arriba (como los ejemplos: "01 · TÍTULO", color por sección) ----------
    if args.chapters:
        chs = json.load(open(args.chapters, encoding="utf-8"))
        first_ok = (hook_end + 0.15) if args.hook else 0.0
        for ch in chs:
            s0, e0 = max(ch["start"], first_ok), min(ch["end"], dur)
            if e0 - s0 < 0.8:
                continue
            col = ass_tag_color(ch.get("color", brand["accent_color"]))
            x0, y0c = int(W * 0.06), int(H * 0.04)
            dd = int((e0 - s0) * 1000)
            slide = f"\\move({x0 - sz(400)},{y0c},{x0},{y0c},0,300)"
            fade = f"\\t({dd - 220},{dd},\\alpha&HFF&)"
            add(5, s0, e0, "Txt", f"{{\\an7{slide}\\fs{sz(76)}\\bord{sz(5)}\\shad{sz(3)}\\1c{col}{fade}}}{ass_escape(ch.get('num', ''))}")
            add(5, s0 + 0.08, e0, "Txt", f"{{\\an7\\move({x0 + sz(112) - sz(400)},{y0c + sz(18)},{x0 + sz(112)},{y0c + sz(18)},0,340)\\fs{sz(46)}\\bord{sz(4)}\\shad{sz(3)}\\1c{wht}{fade}}}{ass_escape(ch.get('label', '').upper())}")

    # ---------- lower third (marca personal) ----------
    if args.lower_third:
        x0, y0 = int(W * x_lt), int(H * y_lt)
        s, e = args.lt_start, min(args.lt_start + args.lt_dur, dur)
        off = int(W * 0.8)
        nm, rl = ass_escape(brand["name"]).upper(), ass_escape(brand["role"])
        add(4, s, e, "Plate", f"{{\\an7\\move({x0 - off},{y0},{x0 + sz(14)},{y0},0,380)\\frz-1.5\\fs{sz(70)}\\bord{sz(16)}\\shad{sz(7)}\\3c{pri}\\1c{wht}\\4c&H000000&"
                              f"\\t({int((e - s) * 1000 - 250)},{int((e - s) * 1000)},\\alpha&HFF&)}}{nm}")
        add(4, s + 0.12, e, "Plate", f"{{\\an7\\move({x0 - off},{y0 + sz(118)},{x0 + sz(14)},{y0 + sz(118)},0,430)\\frz-1.5\\fs{sz(42)}\\bord{sz(12)}\\shad{sz(6)}\\3c{acc}\\1c{onacc}\\4c&H000000&"
                                     f"\\t({int((e - s) * 1000 - 250)},{int((e - s) * 1000)},\\alpha&HFF&)}}{rl}")
        add(3, s, e, "Draw", f"{{\\an7\\pos({x0 - sz(18)},{y0 - sz(4)})\\p1\\bord0\\shad0\\1c{acc}\\clip({x0 - sz(18)},{y0 - sz(4)},{x0 - sz(18)},{y0 + sz(190)})"
                             f"\\t(80,460,\\clip({x0 - sz(18)},{y0 - sz(4)},{x0 - sz(2)},{y0 + sz(190)}))}}m 0 0 l {sz(16)} 0 l {sz(16)} {sz(190)} l 0 {sz(190)}{{\\p0}}")

    # ---------- callouts ----------
    if args.callouts:
        cols = [(pri, wht), (acc, onacc), (wht, drk)]
        with open(args.callouts, encoding="utf-8") as f:
            for k, c in enumerate(json.load(f)):
                t, d = float(c["t"]), float(c.get("dur", 2.2))
                y = int(H * (y_call_center if c.get("pos") == "center" else y_call_top)) + sz(60)
                pc, tc = cols[k % 3]
                rot = -3 if k % 2 == 0 else 3
                tx = ass_escape(str(c["text"]).upper())
                dd = int(d * 1000)
                add(4, t, t + d, "Plate", f"{{\\an5\\pos({cx},{y})\\frz{rot}\\fs{sz(72)}\\bord{sz(18)}\\shad{sz(8)}\\3c{pc}\\1c{tc}\\4c&H000000&"
                                          f"\\fscx60\\fscy60\\alpha&HFF&\\t(0,140,\\fscx116\\fscy116\\alpha&H00&)\\t(140,240,\\fscx100\\fscy100)"
                                          f"\\t({dd - 200},{dd},\\alpha&HFF&\\fscx60\\fscy60)}}{tx}")

    # ---------- cierre ----------
    if args.cta:
        s = max(0.0, dur - args.cta_dur)
        y = int(H * y_cta) + sz(40)
        dd = int((dur - s) * 1000)
        pop = "\\fscx60\\fscy60\\alpha&HFF&\\t(0,170,\\fscx110\\fscy110\\alpha&H00&)\\t(170,270,\\fscx100\\fscy100)"
        if mode == "company" and brand.get("company"):
            add(5, s, dur, "Plate", f"{{\\an5\\pos({cx},{y})\\frz-2\\fs{sz(118)}\\bord{sz(22)}\\shad{sz(9)}\\3c{pri}\\1c{wht}\\4c&H000000&{pop}}}{ass_escape(brand['company'].upper())}")
            if brand.get('cta'):
                add(5, s + 0.25, dur, "Plate", f"{{\\an5\\pos({cx},{y + sz(150)})\\frz1.5\\fs{sz(46)}\\bord{sz(14)}\\shad{sz(6)}\\3c{wht}\\1c{drk}\\4c&H000000&{pop}}}{ass_escape(brand['cta'])}")
            if brand.get("url"):
                add(5, s + 0.5, dur, "Plate", f"{{\\an5\\pos({cx},{y + sz(262)})\\fs{sz(52)}\\bord{sz(14)}\\shad{sz(6)}\\3c{acc}\\1c{onacc}\\4c&H000000&{pop}}}{ass_escape(brand['url'])}")
        else:  # marca personal: nombre + etiqueta + invitación a seguir
            add(5, s, dur, "Plate", f"{{\\an5\\pos({cx},{y})\\frz-2\\fs{sz(84)}\\bord{sz(20)}\\shad{sz(9)}\\3c{pri}\\1c{wht}\\4c&H000000&{pop}}}{ass_escape(brand['name'].upper())}")
            tag = args.cta_tag or brand.get('personal_tag') or brand.get('handle') or brand.get('role', '')
            if tag:
                add(5, s + 0.2, dur, "Plate", f"{{\\an5\\pos({cx},{y + sz(140)})\\frz1.5\\fs{sz(46)}\\bord{sz(14)}\\shad{sz(6)}\\3c{wht}\\1c{drk}\\4c&H000000&{pop}}}{ass_escape(tag)}")
            add(5, s + 0.45, dur, "Plate", f"{{\\an5\\pos({cx},{y + sz(258)})\\fs{sz(50)}\\bord{sz(16)}\\shad{sz(7)}\\3c{acc}\\1c{onacc}\\4c&H000000&{pop}}}{ass_escape((args.cta_line or brand.get('personal_cta') or 'Sígueme para más').upper())}")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(ev) + "\n")
    print(f"OK: {args.out}  ({W}x{H}, {dur:.1f}s, modo={mode}, gancho={style if args.hook else '-'}, {len(ev)} eventos, fuente={font})")


if __name__ == "__main__":
    main()
