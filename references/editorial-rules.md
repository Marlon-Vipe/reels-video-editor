# Reglas editoriales (el "criterio" de la edición)

Las herramientas cortan; el criterio decide qué cortar y cuánto. Aplica esto en el paso de revisión editorial, antes de generar la EDL.

## 1. Qué eliminar (en este orden de prioridad)
1. **Silencios y pausas muertas** → lo hace `build_edl.py` con el preset.
2. **Tomas repetidas / falsos comienzos**: cuando el creador repite una frase, conserva la **última** toma completa (suele ser la mejor) y elimina las anteriores con `--cut-words`.
3. **Muletillas aisladas** (eh, mmm, um) → `--cut-fillers`. No elimines "o sea", "bueno", "entonces" automáticamente: forman parte de su voz; quita solo las que se repiten en exceso.
4. **Introducciones lentas** ("Hola, en este video les voy a hablar de..."): en Reels/Shorts arranca directo en la promesa. En YouTube, la intro puede quedarse si dura < 8 s y ya promete algo.
5. **Divagaciones** que no aportan al objetivo del video: propónlas al usuario si son > 10 s; no borres contenido sustancial sin avisar.

**Nunca** cambies el significado: al cortar entre frases, lee el resultado en `transcript.txt` y confirma que la idea sigue siendo coherente y que no se altera una negación, una cifra o una condición.

## 2. Ritmo de silencios (por qué importan los números)
Cortar demasiado apretado suena robótico y cansa; cortar poco se siente lento. El oído necesita un respiro breve entre ideas.

| Formato | Pausa que se recorta | Respiro que queda | Segmento medio esperado |
|---|---|---|---|
| Reels / TikTok / Shorts | > 0.28 s | ~0.14 s | 1.5–4 s |
| YouTube | > 0.50 s | ~0.30 s | 3–8 s |

- **Protege las pausas dramáticas** (antes de un dato clave o de un remate) con `--keep inicio-fin`; deja 0.4–0.7 s.
- Si el resultado suena a "ametralladora" (segmentos < 1 s de media), sube `--min-silence` o los `--pad-*`.
- Si hay música o ruido de fondo en el original, el detector no verá "silencio": sube `--noise` (p. ej. -28) o pide un audio limpio.

## 3. Gancho (hook) — los primeros 3 segundos
- Reels/Shorts: la audiencia decide en ~1–3 s. El primer fotograma debe mostrar rostro + texto de hook y el primer audio debe ser la promesa, no un saludo.
- Hook en pantalla: promesa concreta, ≤ 7 palabras, en MAYÚSCULAS (etiqueta de color), visible 2.5–3 s.
- Si la frase más fuerte del video está más adelante, **propónsela al usuario** como cold open (mover esa frase al inicio) — no lo hagas sin confirmar, porque cambia la narrativa.
- YouTube: promesa en los primeros 10–15 s; evita intros de marca largas (> 3 s).

## 4. Cambio visual constante (retención)
La atención cae cuando la imagen no cambia. Un "cambio" puede ser un corte con zoom, un callout, un B-roll, un cambio de encuadre.
- Reels/Shorts: algo cambia cada **2–4 s**. YouTube: cada **5–8 s**.
- **Punch-in alterno**: `render_cut.py --punch` alterna 100% y ~110% (Reels) o ~105% (YouTube) en cada corte, lo que disimula los saltos y da dinamismo sin distraer. Más de ~115% se ve pixelado y agresivo.
- Callouts: 1 cada ~8–12 s en Reels, solo para ideas clave (cifras, nombres de herramientas, beneficios). Más que eso compite con los subtítulos.
- Un mismo elemento (hook, lower third, callout) nunca debe tapar la cara ni los subtítulos.

## 5. Subtítulos
- Mucha gente ve los videos sociales sin sonido (en el transporte, en el trabajo): los subtítulos no son opcionales.
- Reels/TikTok/Shorts: 2–3 palabras por vez, MAYÚSCULAS, palabra activa resaltada, zona segura (ver `formats.md`).
- YouTube: líneas de hasta ~7 palabras, sin resaltado, y exporta también `.srt` para subirlo (accesibilidad y búsqueda).
- **Revisa la ortografía**: Whisper falla en nombres propios y anglicismos. Contrasta con `vocabulary` y corrige `words_cut.json` antes de generar los subtítulos si hace falta.
- `--emphasis` resalta palabras clave (una por grupo como máximo, para que el énfasis conserve su efecto).

## 6. Audio
- **Voz primero**: normaliza a **-14 LUFS**, pico real ≤ -1.5 dBTP (`export.py` lo hace con `loudnorm`). Es un nivel de referencia habitual en las plataformas (YouTube, por ejemplo, normaliza cerca de ahí), así que el video no se percibe ni bajo ni saturado.
- **Música**: solo si el usuario la proporciona o confirma que tiene derechos; no descargues ni sugieras pistas con copyright. Sin letra, a -22/-26 dB bajo la voz, con ducking (baja sola cuando hablas) y fundido de salida. En videos explicativos densos, mejor sin música.
- **Efectos de sonido** (whoosh en transiciones, "pop" en callouts): opcionales y sutiles; solo si el usuario tiene una librería propia.
- Cada corte lleva un micro-fundido de 15 ms (ya incluido) para evitar clics.

## 7. YouTube: extras que suben el rendimiento
- **Capítulos**: al menos 3, el primero en 0:00, cada uno ≥ 10 s, con títulos que prometen algo. Calcúlalos con `words_cut.json` (tiempos ya en la línea de tiempo final).
- **Título**: 3 opciones ≤ 60 caracteres, con la palabra clave al inicio, sin mentir.
- **Miniatura**: sugiere 1–2 conceptos (rostro con expresión clara + 3-4 palabras + contraste con el color de marca).
- **Descripción**: 2 líneas de gancho, capítulos, enlace a tu web y redes.
- **Pantalla final** (últimos 5–20 s): deja espacio libre para las tarjetas de video sugerido.

## 8. Lista de verificación antes de entregar
- [ ] El primer segundo ya "dice" algo (rostro + hook / promesa).
- [ ] Duración final acorde al formato (Reel 20–60 s; Short ≤ 60 s como referencia; YouTube según el tema).
- [ ] Sin cortes que cambien el sentido; sin palabras cortadas al inicio o final de una frase.
- [ ] Subtítulos legibles, sin errores de nombres propios, dentro de la zona segura.
- [ ] Nada tapa la cara; ningún overlay choca con otro.
- [ ] Un solo CTA de marca, breve, y solo si aporta.
- [ ] Volumen consistente; música (si hay) no compite con la voz.
