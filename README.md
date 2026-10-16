# 🎬 Reels Video Editor — Skill para Claude

Skill para que Claude edite videos hablados a cámara (Reels, TikTok, Shorts y YouTube) con acabado premium y **tu propia marca**.

Le das un video crudo y te devuelve un `.mp4` listo para publicar:

- ✂️ **Cortes inteligentes**: quita silencios, muletillas y tomas repetidas sin cambiar el sentido, con zoom alterno en cada corte.
- 💬 **Subtítulos palabra por palabra** sincronizados con la voz real (faster-whisper), con la palabra activa resaltada.
- ⚡ **Hook cinético**: cada placa entra justo cuando se dice su palabra.
- 🧩 **Motion graphics**: más de 20 plantillas (alertas, comparativas, flujos, filas de iconos, mockup de teléfono, terminal, CTA con flecha…) con transiciones variadas.
- 🔊 **Sonido**: impactos, whooshes, pops, risers y música original generada (sin copyright), con ducking.
- 🎚️ **Exportación profesional**: H.264, -14 LUFS en dos pasadas, pico ≤ -1.5 dBTP.
- ✅ **Control de calidad** automático con hojas de contacto antes de entregar.

## Instalación

1. Descarga este repositorio (o el `.zip`).
2. En Claude: **Configuración → Capacidades → Skills → Subir skill** y sube la carpeta comprimida.
   En Claude Code: copia la carpeta a `~/.claude/skills/reels-video-editor/`.

Requisitos del entorno: `ffmpeg` (con libass y libx264), Python 3.9+, `numpy`, `scipy`, `pillow`, `faster-whisper`. Ejecuta `bash scripts/check_env.sh` para comprobarlo.

## Adáptala a tu marca (2 minutos)

```bash
cp assets/brand.example.json assets/brand.json
```

Edita `assets/brand.json`:

| Campo | Ejemplo |
|---|---|
| `name` / `role` | `"Ana Pérez"` / `"Coach de fitness"` |
| `personal_tag` / `personal_cta` | `"Fitness y nutrición"` / `"Sígueme para más"` |
| `primary_color` | El color principal de tu marca, p. ej. `"#E11D48"` |
| `accent2_color` / `caption_active_color` | Versiones más claras del primario (para que se lean sobre video) |
| `company` / `company_keywords` / `url` | Opcional: cierre de empresa cuando el video la menciona |
| `vocabulary` | Nombres propios que la transcripción suele escribir mal |

Si no creas el archivo, Claude te preguntará estos datos la primera vez. Guía completa en [`references/brand-guide.md`](references/brand-guide.md).

## Uso

Sube tu video a Claude y pide algo como:

> "Edítame este Reel: quita los silencios, ponle subtítulos y que se vea premium."

## Estructura

```
reels-video-editor/
├── SKILL.md                 # instrucciones que lee Claude
├── assets/
│   ├── brand.example.json   # plantilla de marca
│   └── fonts/               # Space Grotesk, JetBrains Mono, Inter, Montserrat (SIL OFL)
├── references/              # reglas editoriales, formatos, catálogo de animaciones, guía de marca
└── scripts/                 # transcripción, cortes, subtítulos, tarjetas, audio y exportación
```

## Licencia

Código bajo licencia MIT (ver `LICENSE`). Las fuentes incluidas se distribuyen bajo SIL Open Font License 1.1 (ver `assets/fonts/OFL-*.txt`).

Creada por [Marlon Villalona](https://github.com/). Contribuciones bienvenidas.
