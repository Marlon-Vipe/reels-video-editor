#!/usr/bin/env bash
# Verifica que el entorno tenga lo necesario para editar video. Uso: bash check_env.sh
ok=1
check() { if command -v "$1" >/dev/null 2>&1; then echo "✔ $1"; else echo "✘ $1  -> $2"; ok=0; fi; }
check ffmpeg  "instala ffmpeg (brew install ffmpeg | sudo apt install ffmpeg | winget install ffmpeg)"
check ffprobe "viene con ffmpeg"
check python3 "instala Python 3.9+"
if command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg -hide_banner -filters 2>/dev/null | grep -q " ass " && echo "✔ ffmpeg con libass (subtítulos animados)" || { echo "✘ ffmpeg sin libass -> instala una build completa (gyan.dev / evermeet / apt)"; ok=0; }
  ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libx264 && echo "✔ libx264" || { echo "✘ libx264"; ok=0; }
fi
python3 -c "import faster_whisper" 2>/dev/null && echo "✔ faster-whisper" || echo "○ faster-whisper no instalado -> pip install faster-whisper (necesario para transcribir/subtítulos)"
command -v fc-list >/dev/null 2>&1 && { fc-list : family | grep -qiE "space grotesk" && echo "✔ fuente Space Grotesk" || echo "○ Space Grotesk no instalada -> mkdir -p ~/.fonts && cp \"$(dirname \"$0\")/../assets/fonts/\"*.ttf ~/.fonts/ && fc-cache -f"; }
python3 -c "import scipy, numpy, PIL" 2>/dev/null && echo "✔ numpy/scipy/Pillow" || echo "✘ faltan numpy/scipy/Pillow -> pip install numpy scipy pillow"
command -v node >/dev/null 2>&1 && echo "○ node disponible (opcional: Remotion para animaciones avanzadas)" || echo "○ node no disponible (opcional)"
[ $ok -eq 1 ] && echo "Entorno mínimo OK" || echo "Faltan requisitos obligatorios"
