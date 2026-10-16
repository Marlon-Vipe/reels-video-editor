# Formatos, zonas seguras y exportación

Los límites de duración y las especificaciones de cada plataforma cambian con frecuencia. Si el usuario menciona un límite concreto o vas a afirmar un límite actual, verifícalo con una búsqueda web antes de decirlo.

## Presets de la skill

| | Reel / TikTok / Short | YouTube (horizontal) |
|---|---|---|
| Relación de aspecto | 9:16 → 1080×1920 | 16:9 → 1920×1080 (4K si el original lo permite: usa `--aspect keep`) |
| `build_edl.py --preset` | `reels` | `youtube` |
| `render_cut.py --aspect --punch` | `9:16 --punch 1.10` | `16:9 --punch 1.05` |
| `make_captions.py --style` | `reels` | `youtube` (+ `--srt`) |
| Overlays típicos | hook, lower third, barra de progreso, callouts, CTA | lower third, callouts, CTA (sin barra o muy fina) |
| Duración de referencia | 20–60 s (más corto suele retener mejor) | según el tema; 8–20 min para tutoriales |
| Cuadros por segundo | los del original (30 o 60) | los del original |
| Códec | H.264, yuv420p, AAC 192 kbps, `+faststart` (lo hace `export.py`) | igual; CRF 18 (calidad alta) |
| Sonoridad | -14 LUFS, pico ≤ -1.5 dBTP | -14 LUFS, pico ≤ -1.5 dBTP |

Vista previa rápida (para iterar antes del render final): `render_cut.py ... --preset ultrafast --crf 28`.

## Zonas seguras en vertical (1080×1920)
Las apps colocan su interfaz encima del video. Mantén el contenido importante dentro de estas zonas:
- **Arriba**: ~10% (≈ 190 px) reservado a la barra superior de la app. La barra de progreso de la skill se sitúa en el 10% y el hook justo debajo.
- **Abajo**: ~20% (≈ 380 px) reservado a usuario, descripción, audio y botones. Por eso los subtítulos van en ~65-70% de la altura (`margin_v=560`), nunca pegados al borde.
- **Derecha**: ~12% (≈ 130 px) para los botones de like/comentar/compartir. No pongas logo ni texto en el borde derecho.
- **Centro-izquierda**: buena zona para lower thirds y etiquetas.

## Rostro en primer plano (selfie vertical)
Es el encuadre más habitual en Reels: cabeza y hombros llenan el cuadro; frente y pelo ocupan ~15–35% de la altura, los ojos ~45% y la boca ~65–70%. Consecuencias:
- Subtítulos: base al ~80% (`make_captions.py --baseline 0.80`), sobre el pecho/camisa, no sobre la boca.
- Hook, lower third, callouts y CTA: en el ~11–13% superior (`--hook-y/--lt-y/--callout-y/--cta-y`), sobre el fondo o el pelo, nunca sobre los ojos.
- Zoom: usa `--punch 1.08` como máximo; con el rostro tan cerca, más zoom corta la frente o la barba.

## Horizontal a vertical (reencuadre)
Si el original es 16:9 y el destino es 9:16, se recorta el centro del encuadre (≈ 31% del ancho útil). Antes de renderizar:
1. Extrae 3 fotogramas (`contact_sheet.py --at ...`) y comprueba dónde está la cara.
2. Ajusta `--focus-x` (0 = izquierda, 0.5 = centro, 1 = derecha) para que la cara quede centrada.
3. Un original 1080p recortado a 9:16 queda a ~608×1080 y se amplía a 1080×1920: se ve blando. Si es posible, graba en vertical o en 4K; si no, avisa al usuario y limita el zoom (`--punch 1.05`).

Si el original ya es vertical, `--aspect 9:16` no recorta de más; solo aplica el zoom alterno.

## Qué entregar según el destino
- **Reel/TikTok/Short**: `.mp4` final en 9:16. Opcional: versión sin subtítulos quemados (`export.py` sin `--ass` de subtítulos) para plataformas con subtítulos nativos.
- **YouTube**: `.mp4` final 16:9 + `.srt` + texto de capítulos, 3 títulos y descripción.
- **Clips de un video largo**: un `.mp4` por clip, cada uno con su propio hook.

## Rendimiento y tiempos
- El render es el paso más lento (≈ 0.5–1× tiempo real en CPU para 1080p). Para videos de más de ~5 min, lanza el render en segundo plano y consulta el avance:
  `nohup python3 render_cut.py ... > render.log 2>&1 &` y luego `tail -c 300 render.log`.
- La transcripción con `medium` en CPU tarda ~1–2× la duración del audio; con GPU y `large-v3` es mucho más rápida. Para pruebas, `--model small`.
