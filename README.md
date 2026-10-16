# reels-video-editor

Una skill para Claude que edita videos hablados a cámara: Reels, TikToks, Shorts y también videos de YouTube.

La armé para mis propios Reels porque editar cada video me tomaba horas: cortar silencios, poner subtítulos a mano, buscar efectos... Después de usarla un tiempo la limpié para que cualquiera la pueda adaptar a su marca, y la dejo aquí.

## Qué hace

Le pasas el video crudo y te devuelve un mp4 listo para subir. En el camino:

- Quita los silencios, las muletillas y las tomas repetidas, y mete un zoom leve en cada corte para que no se noten los saltos.
- Transcribe con faster-whisper y pone subtítulos palabra por palabra, con la palabra que estás diciendo resaltada.
- Arma un gancho al inicio que aparece justo cuando dices cada palabra, no antes.
- Agrega tarjetas animadas cuando mencionas algo que se puede mostrar: una comparación, una lista, un proceso, una cifra. Hay unas veinte plantillas y no repite diseño en el mismo video.
- Pone efectos de sonido, una música de fondo generada (sin problemas de copyright) y deja el audio a -14 LUFS, que es lo que esperan las plataformas.
- Antes de entregar revisa fotogramas sueltos para comprobar que nada tape la cara y que los subtítulos vayan sincronizados.

No es magia: a veces Whisper escribe mal un nombre o un corte queda raro, así que Claude te dice qué frases corrigió para que las confirmes.

## Cómo instalarla

En claude.ai: comprime la carpeta y súbela en Configuración → Capacidades → Skills.

En Claude Code: copia la carpeta a `~/.claude/skills/reels-video-editor/`.

Necesitas `ffmpeg` (con libass y libx264), Python 3.9 o superior y `pip install faster-whisper numpy scipy pillow`. Puedes correr `bash scripts/check_env.sh` para ver qué te falta.

## Ponerle tu marca

```bash
cp assets/brand.example.json assets/brand.json
```

Abre `brand.json` y cambia lo básico: tu nombre, a qué te dedicas, tu color principal y la frase del cierre ("Sígueme para más", o lo que uses). Si tienes empresa y quieres que aparezca cuando la mencionas en el video, llena también `company`, `company_keywords` y `url`. En `vocabulary` pon los nombres que la transcripción suele escribir mal (el tuyo, tu marca, términos de tu nicho).

Si no creas el archivo, Claude te pregunta esos datos la primera vez. Hay más detalle sobre colores y tipografías en [references/brand-guide.md](references/brand-guide.md).

## Usarla

Sube el video a Claude y pídele algo normal, por ejemplo: "edítame este Reel, quítale los silencios y ponle subtítulos". Tarda unos minutos porque renderiza en CPU.

## Qué hay en la carpeta

- `SKILL.md`: las instrucciones que lee Claude.
- `scripts/`: transcripción, cortes, subtítulos, tarjetas, audio y exportación.
- `references/`: reglas de edición, formatos, catálogo de animaciones y la guía de marca.
- `assets/`: la plantilla de marca y las fuentes.

## Licencia

El código es MIT. Las fuentes (Space Grotesk, JetBrains Mono, Inter y Montserrat) tienen licencia SIL Open Font License; los textos de licencia están en `assets/fonts/`.

Si la mejoras o encuentras un bug, abre un issue o un PR.

— Marlon Villalona
