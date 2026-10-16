#!/usr/bin/env python3
"""Dice EN QUÉ SEGUNDO se dice una palabra o frase (en words_cut.json), para anclar golpes visuales y sonidos a la voz.

Uso:
  python find_words.py work/words_cut.json "acción" "todo listo" "nunca"
Salida por cada frase: todas las apariciones con inicio/fin de la primera palabra y de la frase completa.
Regla: las palabras-golpe (hook, slam, kicker_slam, sello de strike, símbolo de partner, impacto de sonido)
entran JUSTO en el `inicio` (±0.03 s), nunca antes. Para una tarjeta cuyo golpe ocurre a `t_reveal` segundos
de empezar: --broll tarjeta.mp4@(inicio - t_reveal).
"""
import json
import sys

from common import norm_word
from make_overlays import _similar


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    words = json.load(open(sys.argv[1], encoding="utf-8"))["words"]
    toks = [norm_word(w["word"]) for w in words]
    for phrase in sys.argv[2:]:
        q = [norm_word(t) for t in phrase.split() if norm_word(t)]
        hits = []
        for i in range(len(toks) - len(q) + 1):
            if all(_similar(toks[i + k], q[k]) for k in range(len(q))):
                hits.append((words[i]["start"], words[i + len(q) - 1]["end"], " ".join(w["word"] for w in words[i:i + len(q)])))
        if not hits:
            print(f"'{phrase}': no aparece (revisa la ortografía o usa una palabra más corta)")
        for a, b, txt in hits:
            print(f"'{phrase}': inicio {a:.2f}s  fin {b:.2f}s  ->  {txt}")


if __name__ == "__main__":
    main()
