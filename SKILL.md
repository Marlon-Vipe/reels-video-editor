---
name: reels-video-editor
description: Edita videos verticales de talking-head (Reels, TikTok, Shorts; también YouTube) con acabado premium y la marca de cualquier creador. Quita silencios, muletillas y tomas repetidas, alterna zoom en los cortes, pone subtítulos palabra por palabra sincronizados con la voz, hook cinético, tarjetas y motion graphics, transiciones, efectos de sonido y música original, y exporta a -14 LUFS. Úsala cuando el usuario quiera editar, cortar, subtitular o "dejar listo para publicar" un video hablado a cámara, aunque no diga "Reel".
---

# Editor de Reels premium (talking-head)

Convierte un video crudo de alguien hablando a cámara en un Reel con ritmo, gancho fuerte, subtítulos que siguen la voz, infografías animadas y sonido, listo para publicar. Los scripts cortan, dibujan y renderizan; **el criterio editorial lo pones tú** leyendo la transcripción y viendo los fotogramas.

## Antes de empezar: la marca
- Toda la identidad visual sale de **`assets/brand.json`**. Si no existe, cópialo de `assets/brand.example.json` y **pregunta al usuario** (una sola vez, en un mensaje): nombre y cargo para el lower third, su nicho o @ para el cierre, color principal de marca (o su web para sacarlo de ahí) y, si quiere, empresa y URL. Con lo que no responda, usa los valores neutros del ejemplo y dilo en la entrega.
- Pasa siempre `--brand $K/assets/brand.json` a los scripts que lo aceptan.
- **Marca personal por defecto:** lower third con `name` + `role`, cierre con nombre + `personal_tag` + `personal_cta`. El cierre de empresa (`company` · `cta` · `url`) solo se activa si el video dice alguna palabra de `company_keywords` o si el usuario lo pide (`--mode company`).
- **Un color primario manda**; blanco y negro hacen el resto. `warm_color` (alerta) solo como destello mínimo. **Fondos SOLO planos o degradados: nunca cuadrículas, rayas ni patrones.**
- Detalle completo y cómo elegir la paleta en `references/brand-guide.md`.

## Archivos
- `scripts/`: `check_env.sh`, `transcribe.py` (faster-whisper), `transcribe_sherpa.py` + `transcribe_whisper_sherpa.py` + `fix_words.py` (respaldo sin Hugging Face), `align_text.py` (respaldo si el usuario da el texto), `build_edl.py`, `render_cut.py`, `make_captions.py`, `make_overlays.py`, `make_cards.py`, `make_sfx.py`, `make_music.py`, `export.py`, `contact_sheet.py`, `find_words.py` (en qué segundo se dice una palabra)
- `assets/brand.example.json` (plantilla de marca) y `assets/fonts/` (Space Grotesk, JetBrains Mono, Montserrat, Inter; licencia SIL OFL)
- `references/`: `editorial-rules.md` (léelo antes del paso 3), `brand-guide.md`, `formats.md`, `animations.md` (catálogo de plantillas, incluido el kit UI)

`K` = carpeta de esta skill, `S=$K/scripts`, trabajo en `work/`. Entregables en la carpeta de salida del entorno (p. ej. `/mnt/user-data/outputs/` o `./output/`). Filtra la salida de ffmpeg con `2>&1 | tail -c 200`.

## Estilo objetivo
1. **Subtítulos** pequeños-medianos, MAYÚSCULAS con espaciado de letras, 2 líneas, sombra marcada, **palabra activa en el color de acento** que salta con la voz (`--style ui`, base ~0.88–0.90 de la altura).
2. **Palabra "slam" con etiqueta mono** encima ("VAMOS A CREAR UNA" / GUÍA) para el concepto central.
3. **Tarjetas UI sobre el video** (papel claro, borde casi negro, sombra dura, etiquetas mono, acento del color primario): medidor A-vs-B, flujo con sello "NO ES ESTO", fila de iconos que aparecen al nombrarlos, mockup de teléfono, ficha suelta, notificaciones, etiqueta **"Comenta X"** y **tarjeta de cierre con flecha**. Van en la zona libre (arriba o a los lados), nunca sobre la cara.
4. **Tarjetas a pantalla completa** con motion graphics (alert, strike, partner, growth, slam, terminal, orbit, meter, pillars) para ideas clave, **nunca el mismo diseño dos veces**.
5. **Etiqueta de capítulo** arriba ("01 · TÍTULO") y un tono distinto por sección en el resaltado (variaciones del primario; `warm_color` solo para el capítulo de advertencia).
6. Hook cinético con placas de color, barra de progreso, cierre con acción concreta. Nunca logos de terceros: nombres en texto o iconos genéricos.

## Flujo

### 0. Entorno
`bash $S/check_env.sh`. Instala las fuentes: `mkdir -p ~/.fonts && cp $K/assets/fonts/*.ttf ~/.fonts/ && fc-cache -f` (y `--fonts-dir $K/assets/fonts` en `export.py`). `pip install faster-whisper numpy scipy pillow` según falte.
**Red restringida:** si Hugging Face está bloqueado, prueba GitHub Releases (`curl -sI`) antes de rendirte; no intentes saltarte una política de red.

### 1. Inspeccionar y ubicar la cara
`ffprobe` y `contact_sheet.py --every 3`. **Mira dónde está la cara** antes de fijar posiciones. Selfie de cerca (la cara llena la pantalla): techo libre solo arriba (~0–20 %) → hook, iconos, etiquetas y stickers van ahí (`--hook-y 0.11`, tarjetas `pos` y≈0.165, **debajo de la barra de progreso** que está en y=0.10); subtítulos `--baseline 0.895`. Cuerpo entero: hay zonas laterales para `ui_meter`/`ui_flow`/`phone` (`pos` x≈0.15). Los videos de celular son de fps variable: `render_cut.py` ya fuerza fps constantes.

### 2. Transcribir con tiempos por palabra reales (en este orden)
1. `python3 $S/transcribe.py video.mp4 --out-dir work --lang es --model medium --prompt "<vocabulary de brand.json>"` (faster-whisper). Cambia `--lang` al idioma del video.
2. Si Hugging Face está bloqueado: `pip install sherpa-onnx --break-system-packages` y `python3 $S/transcribe_sherpa.py video.mp4 --out-dir work` (modelo CTC desde GitHub Releases; **tiempos reales**, texto tosco). Luego una **segunda hipótesis de texto**: `python3 $S/transcribe_whisper_sherpa.py work/audio.wav`. Reconcilia frase por frase en `edits.json` y aplica `python3 $S/fix_words.py work/words.json edits.json --out work/words.json` (conserva los tiempos). Corrige acentos, nombres propios y marcas.
3. Si no hay forma de descargar modelos: pide al usuario el texto (guion o subtítulos automáticos) y alinéalo con `python3 $S/align_text.py video.mp4 --text-file texto.txt --out-dir work --debug-plot qa/align.png` (error típico 60–150 ms; **mira el PNG**).
Para decidir entre dos versiones de una frase compara sílabas contra el tiempo real; **marca en tu entrega lo que quedó incierto**. **Nunca repartas tiempos "a ojo"**. Verifica la sincronía con una gráfica de energía + marcas de palabra (las marcas deben caer en los picos de voz).

### 3. Revisión editorial
Lee `references/editorial-rules.md` y el transcript. Decide: cortes de contenido (`--cut-words`), pausas a proteger (`--keep`), **hook** (≤ 7 palabras, sale de lo que el creador dice, p. ej. su propia pregunta de apertura), palabras clave (`--emphasis`), **capítulos** (3–4 con título de 2–3 palabras y color) y **momentos para tarjetas** (7b). Ningún corte puede cambiar el sentido.

### 4. Cortar y construir la EDL
```bash
python3 $S/build_edl.py video.mp4 --words work/words.json --preset reels --noise -30 --zoom-cuts 3.2 --out-dir work [--cut-words 41-47] [--keep 30.1-31.0] [--cut-fillers] [--trim 120-175]
```
Si casi no hay pausas (hablante fluido) no fuerces el corte: `--zoom-cuts 3–4` parte en frases para alternar zoom **sin quitar contenido** (avisa que casi no se quitó nada).

### 5. Render del corte
```bash
python3 $S/render_cut.py work/edl.json --aspect 9:16 --punch 1.10 --face-y 0.52 --start-zoomed --out work/cut.mp4 2>&1 | tail -c 200
```
(~2.5 min por 55 s en CPU; lanza los pasos 7b/7c en paralelo mientras corre.)

### 6. Subtítulos (colores por capítulo)
```bash
python3 $S/make_captions.py work/words_cut.json --style ui --video work/cut.mp4 --brand $K/assets/brand.json \
  --baseline 0.895 --chapters work/chapters.json --emphasis "clave1,clave2" --out work/captions.ass
```
Estilos: `ui` (look premium por defecto), `reels` (más grande, 3 palabras), `youtube` (`--srt`). `chapters.json`: `[{"start":0,"end":18.9,"num":"01","label":"El problema","color":"#4F8BFF","color2":"#9DBBFF"}, ...]` (usa tonos de tu paleta).

### 7. Hook, etiquetas y cierre
```bash
python3 $S/make_overlays.py --video work/cut.mp4 --brand $K/assets/brand.json --words work/words_cut.json \
  --hook "¿Sabías esto?" --hook-style plates --hook-y 0.11 --lower-third --lt-start 4.6 --lt-y 0.125 \
  --progress --cta --cta-y 0.125 [--cta-tag "..." --cta-line "..."] --chapters work/chapters.json \
  --hook-times-out work/hook.json --out work/overlays.ass
```
**El gancho NO sale de una vez: cada placa entra JUSTO cuando se dice su palabra** (si aparece antes, mata el efecto). Con `--words` es automático: busca la frase del gancho en la voz y ancla cada placa al inicio de su palabra (`--hook-lead 0.03`); el gancho completo se queda `--hook-hold 1.1` s tras la última. Por eso **el gancho debe ser una frase dicha tal cual** (o casi): si no la encuentra, el script avisa y debes darle tiempos con `--hook-at "t1,t2,t3"` sacados de `find_words.py`. `--hook-words-per-plate 1` = una placa por palabra (más golpe cuando se habla pausado). Guarda `--hook-times-out` y pon los **impactos de sonido en esos mismos segundos**. Hook ≤ 2 líneas. Si el tema no encaja con `personal_tag`/`personal_cta`, cámbialos con `--cta-tag`/`--cta-line` **y avisa al usuario**.

### 7b. Tarjetas, stickers y paneles (variedad obligatoria)
Cada vez que el creador nombra un concepto visualizable, dibújalo. Reglas:
- **Nunca repitas diseño** en un video. Pantalla completa (`alert`, `pillars`, `partner`, `growth`, `strike`, `terminal`, `orbit`, `meter`, `slam`) ≤ ~30 % del video, 2–4 s cada una; overlays sin fondo (`sticker`, `panel` y el **kit UI**: `kicker_slam`, `toast`, `ui_meter`, `ui_flow`, `ui_iconrow`, `ui_tag`, `ui_cta`, `phone`) para acompañar sin tapar la cara. Catálogo y campos en `references/animations.md`.
- Elige por lo que se dice: problema → `alert`/`strike`; lista nombrada → `ui_iconrow` (un icono por palabra, `t` anclado a cuándo la dice) / `pillars`; contraste → `partner` ("A ≠ B") / `ui_meter`; proceso → `ui_flow`; palabra clave → `slam`/`kicker_slam`; crecimiento → `growth`; llamada a la acción → `ui_tag` / `ui_cta`.
- Fondos (planos o degradados): `blue` (= color primario), `deep`, `bright`, `mono`, `flat` (y `warm` solo para alerta). Alterna transiciones (`iris`, `wipe_*`, `diag`, `blinds`, `glitch`; `--seed`). Deja libre el 22 % inferior (subtítulos) y no pongas nada sobre la frase más emocional.
- **Golpes en la palabra, no antes:** las tarjetas informativas pueden entrar ~0.3 s antes de nombrar el concepto, pero todo **golpe** (`slam`, `kicker_slam`, el sello de `strike`, el símbolo de `partner`, un sticker de una palabra) impacta **exactamente** cuando se dice la palabra. Saca el segundo con `python3 $S/find_words.py work/words_cut.json "palabra"` y coloca la tarjeta en `inicio − momento_de_impacto` (slam 0.25 s, kicker_slam 0.20 s, strike/partner `t_x`). El impacto de sonido va en el mismo `inicio`.
- **Nada inventado:** una tarjeta solo dibuja lo que el creador dijo; `toast` (DMs) solo si cuenta que le escriben eso, con usuarios enmascarados.
```bash
python3 $S/make_cards.py work/cards.json --brand $K/assets/brand.json --out-dir work/cards --seed 2 [--only nombre] [--preview]
```
Usa `--preview` para ver PNG antes de renderizar; renderiza en paralelo con `--only`.

### 7c. Audio
`make_sfx.py --out-dir work/sfx`, `make_music.py --style pulse --dur <s> --out work/music.wav` (generada, sin derechos de autor). **Impacto** en cada placa del hook (tiempos de `hook.json`) y en cada `slam`/sello; **riser** ~1.4 s que termina en impacto; **whoosh** al entrar cada tarjeta/lower third; **pop** en cada ficha de `ui_iconrow` y en stickers; **ding/sparkle** al cierre; ticks mientras escribe una `terminal`. SFX entre -7 y -18 dB, música a -24 dB con ducking. Si el usuario trae su propia música, úsala solo si confirma que tiene derechos. Genera el comando de `export.py` desde un script Python que lea tu plan.

### 8. Exportar
```bash
python3 $S/export.py work/cut.mp4 --ass work/captions.ass work/overlays.ass --grade --crf 22 --fonts-dir $K/assets/fonts \
  --broll work/cards/x.mp4@9.0 ... --sfx work/sfx/impact.wav@<t de hook.json>@-7 ... --music work/music.wav --music-db -24 --out <salida>/reel.mp4
```
Los tiempos de `--broll`/`--sfx` son segundos del video **ya cortado**. Subtítulos y overlays se queman sobre las tarjetas. Normaliza a -14 LUFS (dos pasadas). Lánzalo en segundo plano y espera.

### 9. Control de calidad (obligatorio)
`contact_sheet.py final.mp4 --at ...` en 20+ momentos. Comprueba: **el gancho no aparece antes de que se diga su palabra** (fotograma 0.1 s antes = sin placa; 0.1 s después = placa) y no tapa los ojos; los golpes caen en su palabra; subtítulos dentro de la zona segura y sincronizados; tarjetas distintas entre sí; iconos/etiquetas **debajo de la barra de progreso**, sin chocar con lower third ni capítulo; modo de marca correcto; colores = `brand.json`; ningún fondo con cuadrícula o patrón; `ffmpeg -i final.mp4 -af ebur128=peak=true -f null -` → ≈ -14 LUFS y pico ≤ -1.4 dBTP. Corrige y re-exporta (máx. 2–3 iteraciones).

### 10. Entregar
Entrega el mp4 (si hay límite de tamaño, recodifica con `-crf 28 -maxrate 2.8M`). Resumen breve: duración antes → después, qué cortaste, qué tarjetas/efectos y dónde, **frases corregidas sin poder escuchar el audio (que el usuario las confirme)**, qué no pudiste verificar, valores de marca que pusiste por defecto, 2 hooks alternativos y texto para el post. YouTube: 3 títulos, capítulos y descripción.

## Problemas frecuentes
| Síntoma | Causa | Solución |
|---|---|---|
| Subtítulos desfasados | tiempos estimados o texto distinto al audio | tiempos reales (CTC) + `fix_words.py`; revisa la gráfica de energía |
| Faltan palabras en subtítulos | palabras en pausas recortadas | ya se conservan; revisa `edits.json` |
| ffmpeg "Killed" al renderizar | memoria | `render_cut.py` ya va por segmentos; baja `--preset` |
| Hook se sale del borde | hook demasiado largo | ≤ 4–5 palabras |
| El gancho sale antes de decirlo | gancho que no se dice literal | pasa `--words`; frase dicha tal cual o `--hook-at` con `find_words.py` |
| Hook tapa la cara | posición | `--hook-y`, 2 líneas máx., hook corto |
| Iconos chocan con la barra | `pos` y < 0.14 | usa y≈0.165 |
| Tarjetas parecen todas iguales | plantilla/fondo repetidos | cambia `template`, `bg`, `in`/`out`, `--seed` |
| Sale el cierre de empresa en un video personal | una palabra de `company_keywords` se dijo de pasada | `--mode personal` |
| Colores o nombre por defecto ("Tu Nombre") | falta `assets/brand.json` o no se pasó `--brand` | crea el archivo desde el ejemplo y pásalo |
| Fuente distinta a la de marca | no instalada | copia `assets/fonts/*.ttf` a `~/.fonts`, `fc-cache -f` y `--fonts-dir` |
| Hugging Face bloqueado | política de red | sherpa CTC + Whisper por GitHub Releases, o `align_text.py` |
| Casi no hay pausas | hablante fluido | `--zoom-cuts 3.2`, no forzar `--noise` |
| Volumen -15 en lugar de -14 | loudnorm de una pasada | `export.py` ya hace dos pasadas |
