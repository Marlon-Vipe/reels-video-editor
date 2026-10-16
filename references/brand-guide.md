# Guía de marca: cómo adaptar la skill a tu marca

Léelo cuando configures la skill por primera vez y cuando decidas estilo visual, tono de los textos en pantalla o cuándo mencionar tu empresa.

## 1. Configura tu `brand.json`
Copia `assets/brand.example.json` a `assets/brand.json` y rellena:

| Campo | Para qué sirve |
|---|---|
| `name`, `role` | Lower third ("TU NOMBRE · Tu cargo") y cierre personal |
| `handle` | Tu @ en redes (se usa en el cierre si no hay `personal_tag`) |
| `personal_tag`, `personal_cta` | Líneas 2 y 3 del cierre personal ("Fitness y nutrición" · "Sígueme para más") |
| `company`, `company_keywords`, `cta`, `url` | Cierre de empresa. Opcional: déjalo vacío si solo haces marca personal |
| `font`, `mono_font` | Tipografía principal y de etiquetas. Pon los `.ttf` en `assets/fonts/` |
| `*_color` | Tu paleta (ver sección 3) |
| `logo` | Ruta a un PNG transparente (opcional, `export.py --logo`) |
| `vocabulary` | Nombres propios y términos de tu nicho que la transcripción escribe mal |

## 2. Marca personal vs. empresa
- **Marca personal (por defecto):** el video promueve a la persona. Lower third con `name` + `role`, cierre con nombre + `personal_tag` + `personal_cta`. La empresa no se promociona.
- **Modo empresa:** se activa solo si en el video se dice alguna palabra de `company_keywords` (o con `make_overlays.py --mode company`). Cierre: `company` · `cta` · `url`. Uno solo por video y solo con lo que se dijo en el audio.
- **Transparencia:** si hay patrocinios, afiliados o el creador recomienda algo que vende su propia empresa, avísalo en pantalla o en la descripción.

## 3. Paleta
- Un color **primario** que manda (placas, tarjetas, barras, hook) + blanco y negro para todo lo demás. Menos colores = más premium.
- `accent2_color` y `caption_active_color`: versiones **más claras** del primario. Los colores saturados pierden contraste sobre video oscuro; la palabra activa del subtítulo debe leerse al primer vistazo.
- `deep_color`: versión muy oscura del primario, para degradados de fondo.
- `warm_color`: color de alerta (naranja/rojo). **Un solo destello por video** (sello "NO ES ESTO", advertencia).
- Si tienes web, toma los colores de sus variables CSS en lugar de estimarlos a ojo.
- **Fondos:** solo color plano o degradado. Nunca cuadrículas, rayas, puntos ni patrones: abaratan el look.

## 4. Tipografía
- Por defecto: Space Grotesk (títulos, subtítulos, tarjetas), JetBrains Mono (etiquetas/kickers), Inter y Montserrat como respaldo. Todas con licencia SIL OFL (ver `assets/fonts/OFL-*.txt`).
- Para usar otra: copia sus `.ttf` a `assets/fonts/`, pon su nombre exacto en `font`/`mono_font` y pasa `--fonts-dir assets/fonts` a `export.py`. Comprueba la licencia antes de redistribuirla.

## 5. Voz y tono en pantalla
- Natural, directo, sin humo. Hook ≤ 7 palabras; callouts ≤ 3 palabras.
- **Nunca inventes** datos, cifras ni capacidades que el creador no dijo. Todo lo que aparece en pantalla sale del audio.
- Nombres propios bien escritos: contrasta siempre la transcripción con `vocabulary`.
- Nunca uses logos de terceros: nombres en texto o iconos genéricos.

## 6. Tipos de contenido y estructura
| Tipo | Duración | Estructura | Notas de edición |
|---|---|---|---|
| Tip / herramienta | 20–45 s | Hook (0-3 s) → problema → solución/demo → cierre | Ritmo rápido, zoom en cada corte, callout en la herramienta y el beneficio |
| Noticia / opinión | 30–60 s | Hook con la noticia → por qué importa → opinión → pregunta a la audiencia | Callout con la cifra o el nombre clave |
| Caso / producto propio | 30–75 s | Problema del cliente → qué se hizo → resultado | Marca visible, cierre de empresa |
| Historia personal | 30–60 s | Momento de tensión → qué pasó → lección | Menos tarjetas, más espacio a la cara y a las pausas |
| Clip desde un video largo | 30–60 s | Momento autocontenido con hook propio | `build_edl.py --trim` + hook nuevo en pantalla |
