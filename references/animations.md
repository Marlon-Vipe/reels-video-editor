# Animaciones y gráficos en pantalla

Hay dos niveles. Empieza siempre por el Nivel 1: funciona con solo ffmpeg, es rápido y suficiente para el 90% de los videos.

## Nivel 1 — ffmpeg + subtítulos ASS (por defecto)
Todo se genera como texto/vectores ASS y se quema con `export.py`. Sin dependencias extra.

| Elemento | Script | Animación | Cuándo usarlo |
|---|---|---|---|
| Subtítulos de palabra activa | `make_captions.py --style reels` | pop-in del grupo (escala 86→100%), palabra activa en color de acento y +18% de tamaño | Todo Reel/TikTok/Short |
| Subtítulos de lectura | `make_captions.py --style youtube` | fundido suave | YouTube |
| Palabras clave | `--emphasis "gratis,rápido,clave"` | color secundario fijo | 1 por grupo como máximo |
| Hook | `make_overlays.py --hook "..."` | etiqueta con pop (60→108→100%) y fundido de salida | Primeros 2.5–3 s |
| Lower third | `--lower-third` | nombre y cargo entran deslizando desde la izquierda | Primeros 4 s |
| Barra de progreso | `--progress` | se llena de izquierda a derecha durante todo el video | Reels/TikTok (retención) |
| Callouts | `--callouts callouts.json` | pop con rebote | Ideas clave: cifras, nombres de herramientas, beneficios |
| CTA de marca | `--cta` | nombre + nicho + invitación a seguir (o empresa + frase + URL), entrada escalonada | Cierre (máx. 1 por video) |
| Zoom (punch-in) | `render_cut.py --punch` | alterna 100% / 110% en cada corte | Todo video con cortes |

### Tarjetas animadas (cutaways) — `make_cards.py`
Motion graphics de 1080×1920 con fondo animado, transiciones de entrada/salida y transparencia animada (`<name>.mp4` + `<name>.matte.mp4`), que `export.py --broll clip@segundo` coloca sobre el video mientras la voz sigue.

| Plantilla | Para | Campos |
|---|---|---|
| `alert` | problema, caída, error | `title`, `code`, `sub` |
| `pillars` | lista de 1–4 conceptos que entran uno a uno | `title`, `items:[{icon,text,t}]` |
| `partner` | A × B o A ≠ B (contraste/alianza) | `a`,`b`,`b_color`,`symbol`,`badge`,`t_a`,`t_x`,`t_b`,`t_badge` |
| `growth` | barras que suben + flecha | `title`, `label` |
| `strike` | palabra con señal de "no" que cae | `chip`, `text`, `t_x` |
| `terminal` | ventana que escribe comandos | `lines:[{text,t,result}]` |
| `orbit` | concepto central con palabras alrededor | `icon`, `items:[{text,t}]` |
| `meter` | barras de medidor (versus) | `bars:[{label,value,color,t}]`, `caption` |
| `slam` | una palabra gigante con impacto | `text`, `sub` |
| `sticker` | icono + etiqueta sobre el video (sin fondo) | `icon`, `label`, `pos` |
| `panel` | panel de cristal "A ≠ B" sobre el video | `items:[{icon,text}]`, `symbols`, `pos` |

Comunes: `bg` (blue = color primario, deep, bright, mono, flat; `warm` = color de alerta, solo si el mensaje pide contraste). **Fondos SOLO planos o degradados: nunca cuadrículas, rayas ni patrones**, `in`/`out` (iris, wipe_l/r/u/d, diag, blinds, glitch, fade), `in_dur`, `out_dur`, `flash`, `dur`. Iconos: bolt chart shield check x doc search gear neq star heart bulb clock rocket.
```json
[{"template":"slam","name":"tiempo","dur":2.2,"text":"Tiempo"},
 {"template":"terminal","name":"cmd","dur":3.9,"lines":[{"text":"resumir()","t":0.2,"result":"listo"}]},
 {"template":"panel","name":"pn","dur":2.6,"items":[{"icon":"bulb","text":"Mi opinión"},{"icon":"star","text":"Tu realidad"}],"symbols":["≠"]}]
```
**Variedad:** nunca dos tarjetas iguales seguidas; `--seed` cambia fondos y transiciones automáticos entre videos. Para una plantilla nueva, agrega una función `tpl_*` y regístrala en `TEMPLATES`. También puedes pasar a `--broll` clips reales (1080×1920).

### Kit "UI" — look del video de referencia (tarjetas con borde grueso y sombra dura, sin fondo)
Overlays que se pegan **sobre la cara/zona libre** (no tapan el video entero): papel claro, borde casi negro, sombra dura, etiquetas en JetBrains Mono, acento del color primario. Salen de `make_cards.py` igual que las demás (`export.py --broll nombre@segundo`).

| Plantilla | Para | Campos |
|---|---|---|
| `kicker_slam` | palabra clave gigante con etiqueta ("VAMOS A CREAR UNA" / GUÍA) | `kicker`, `text`, `pos`, `size` |
| `toast` | notificaciones/DMs que bajan (solo si el creador dice que le escriben eso) | `items:[{user,text,t,badge}]`, `pos` |
| `ui_meter` | A vs B con dos barras (p. ej. editar vs crear) | `kicker`, `title`, `bars:[{label,icon,value,t,color}]`, `pos` |
| `ui_flow` | pasos verticales, uno resaltado y otro con sello "NO ES ESTO" | `kicker`, `title`, `steps:[{icon,label,state,stamp,t}]`, `pos` |
| `ui_iconrow` | fila de herramientas/pasos que aparecen; con 1 ítem = ficha suelta | `items:[{icon,label,t}]`, `pos` |
| `ui_tag` | etiqueta de acción "Comenta X" | `lead`, `keyword`, `pos` |
| `ui_cta` | tarjeta de cierre + flecha que rebota | `kicker`, `lead`, `keyword`, `sub`, `pos` |
| `phone` | mockup de teléfono genérico + etiqueta (REELS, CARRUSELES…) | `label`, `pos`, `tilt` |

Iconos extra: `scissors video send wand music layout expand captions scan brain play chat arrow_down gauge user globe mic`. `pos` = `[fx, fy]` (fracción del ancho/alto, centro del elemento). Posiciones de referencia en vertical con cara centrada: lado izquierdo `[0.15, 0.36-0.40]`, fila superior `[0.5, 0.12]`, etiqueta arriba-derecha `[0.75, 0.115]`, cierre `[0.5, 0.80]`.
Reglas del kit: nunca logos de terceros (usa `chat`, `globe`…); nada de datos inventados (el `toast` solo repite lo que el creador dijo que le preguntan, con usuarios enmascarados `jo***`); el `warm_color` solo en el sello de "no".

### Sincronía de los golpes con la voz
El gancho y cualquier palabra-golpe aparecen **en el instante en que se dice la palabra, nunca antes**: si el texto llega antes que la voz, se pierde la sorpresa. `make_overlays.py --words` sincroniza el gancho solo (placa por placa); para tarjetas usa `find_words.py` y resta el momento de impacto de la plantilla (slam 0.25 s, kicker_slam 0.20 s, strike/partner `t_x`).

### Hook y letras de arriba — `make_overlays.py`
Placas de color con resplandor, inclinadas, que caen con impacto (`plates`), palabras blancas con una placa en la clave (`stack`) o separación RGB (`glitch`); más etiqueta de capítulo, lower third y cierre con el mismo lenguaje de placas.

### callouts.json
```json
[
  {"t": 3.0,  "dur": 2.0, "text": "gratis",       "pos": "center"},
  {"t": 12.4, "dur": 2.2, "text": "ahorra horas"}
]
```
`t` está en segundos **del video ya cortado** (usa `words_cut.json` para ubicar la palabra: su `start` es el tiempo correcto). `pos`: `top` (por defecto) o `center`. Evita que se solapen con el lower third (primeros 4 s) y con el CTA (últimos 3.5 s).

### Personalizar
- Colores y fuente: `assets/brand.json` (los tres scripts lo leen con `--brand`).
- Tamaños, posiciones y tiempos: sección "posiciones" y estilos de `make_overlays.py`, y el diccionario `STYLES` de `make_captions.py`.
- Nuevo elemento: agrega un `Dialogue` ASS. Etiquetas útiles: `\pos(x,y)` posición, `\move(x1,y1,x2,y2,t1,t2)` desplazamiento, `\fad(in,out)` fundido, `\t(t1,t2,\fscx..\fscy..)` animación de escala, `\c&HBBGGRR&` color (ojo: orden BGR), `\p1` dibujo vectorial, `\clip` recorte (animable con `\t`).
- Capas (`Layer`): mayor número = más arriba. Subtítulos 0; barra 1–2; hook y lower third 3; callouts 4; CTA 5.

### Límites del Nivel 1 (dilo si el usuario pide algo así)
Sin gráficas animadas de datos, sin capturas de pantalla animadas con zoom, sin transiciones complejas, sin B-roll generado. Para eso, ver Nivel 2 o pide al usuario los recursos (capturas, clips).

## Nivel 2 — Remotion (motion graphics avanzados, opcional)
Úsalo solo si el usuario lo pide o el video lo necesita de verdad (gráficas animadas, mockups de pantalla, títulos cinematográficos) **y** el entorno tiene Node.js, un navegador Chromium y acceso a npm. Remotion permite componer el video con React: el video base entra como `<OffthreadVideo>` y encima van componentes animados.

Estructura recomendada del proyecto (`npx create-video@latest`):
```
src/
  Root.tsx                 # composiciones: Reel (1080x1920) y YouTube (1920x1080)
  compositions/Main.tsx    # <OffthreadVideo src={cut.mp4}/> + capas
  components/
    Captions.tsx           # lee words_cut.json, agrupa 3 palabras, resalta la activa
    LowerThird.tsx         # nombre + cargo (spring desde la izquierda)
    Callout.tsx            # texto con spring de escala
    ProgressBar.tsx        # interpolate(frame, [0, dur], [0, 100])
    CtaBrand.tsx           # tarjeta final de marca
    AnimatedChart.tsx      # gráficas que se dibujan (barras/líneas)
```
Pautas:
- Usa `words_cut.json` como fuente de subtítulos y tiempos (mismo formato que en el Nivel 1) y el `cut.mp4` de `render_cut.py` como video base: así cortes, zoom y audio ya están resueltos y Remotion solo añade gráficos.
- Animación con `spring()` y `interpolate()`; duraciones cortas (6–12 fotogramas de entrada), rebotes suaves (`damping` alto) para verse profesional y no "caricaturesco".
- Renderiza con `npx remotion render <Composición> out.mp4` y pasa el resultado por `export.py` (sin `--ass`) para agregar música/logo y normalizar el volumen.
- La API de Remotion evoluciona: consulta su documentación actual antes de escribir código.
- En entornos sin acceso a npm o a Chromium (por ejemplo, un sandbox de chat), no lo intentes: usa el Nivel 1 y entrégale al usuario el proyecto solo si lo pide.

## Buenas prácticas de motion
- **Una idea por elemento**, y que dure lo justo para leerse (≈ 0.3 s por palabra + 0.5 s).
- **Movimiento con propósito**: entra rápido (≤ 0.3 s), sale más rápido; nada se mueve mientras se lee.
- **Jerarquía**: subtítulos (siempre) > callout (ocasional) > hook/lower third/CTA (puntuales). Nunca dos textos grandes a la vez.
- **Coherencia de marca**: mismas curvas, colores y fuente en todos los videos.
