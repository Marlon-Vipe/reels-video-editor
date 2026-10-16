#!/usr/bin/env python3
"""Corrige el TEXTO de words.json conservando los tiempos reales de la voz.

Uso:
  python fix_words.py work/words.json edits.json --out work/words.json

edits.json (los índices son los de transcript_indexed.txt, del original):
  [
    {"i": 20, "j": 20, "text": "TuMarca"},                 # reemplaza la palabra 20
    {"i": 5,  "j": 7,  "text": "dueños de negocio"},   # reemplaza el rango 5-7 (3 palabras -> 3 palabras)
    {"i": 33, "j": 34, "text": ""},                     # elimina las palabras 33 y 34
    {"i": 0,  "j": -1, "text": "Se"},                   # inserta ANTES de la palabra 0 (j = i-1)
    {"i": 0,  "j": 0,  "text": "Se cayó", "t0": 0.0}   # "t0"/"t1" opcionales: fuerzan inicio/fin del intervalo
  ]
Las palabras nuevas se reparten el intervalo de las reemplazadas según su número de sílabas.
"""
import argparse
import json
import re


def syl(w):
    return max(1, len(re.findall(r"[aeiouáéíóúü]+", re.sub(r"[^\wáéíóúüñ]", "", w.lower()))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("words")
    ap.add_argument("edits")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    data = json.load(open(args.words, encoding="utf-8"))
    words = data["words"]
    edits = sorted(json.load(open(args.edits, encoding="utf-8")), key=lambda e: e["i"], reverse=True)
    for e in edits:
        i, j, new = e["i"], e["j"], e["text"].split()
        if j < i:  # inserción antes de la palabra i
            t1 = words[i]["start"]
            t0 = words[i - 1]["end"] if i > 0 else max(0.0, t1 - 0.2)
            t0 = min(t0, t1 - 0.1 * len(new))
        else:
            t0, t1 = words[i]["start"], words[j]["end"]
        t0 = e.get("t0", t0)  # opcional: forzar el inicio (p. ej. una palabra que el modelo se comió)
        t1 = e.get("t1", t1)
        w = [syl(x) for x in new]
        span, tt, s = (t1 - t0), sum(w) or 1, t0
        rep = []
        for tok, x in zip(new, w):
            en = s + span * x / tt
            rep.append({"word": tok, "start": round(s, 3), "end": round(max(s + 0.06, en - 0.02), 3)})
            s = en
        words[i:(j + 1) if j >= i else i] = rep
    data["words"] = words
    json.dump(data, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"OK: {len(words)} palabras -> {args.out}")


if __name__ == "__main__":
    main()
