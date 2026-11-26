# Desplazamiento de Feynman

Proyecto Python para estudiar el desplazamiento de Feynman.

## Animación

Instala el proyecto en un entorno virtual y ejecuta la animación:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python feyn1.py
```

El vídeo se guarda como `feyn1.mp4` en el directorio actual. Para exportar a GIF,
cambia `outfile` en `feyn1.py` a `Path(__file__).stem + '.gif'`; déjalo como
cadena vacía para mostrar la animación en pantalla. La exportación MP4 requiere
FFmpeg instalado y disponible en `PATH`.
