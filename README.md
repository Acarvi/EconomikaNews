# Twitter to Instagram Reel Generator

Convierte tuits (de X/Twitter) en Reels listos para Instagram automáticamente.

## Uso

```bash
python main.py <url_del_tuit>
```

O con el archivo `.bat`:

```bash
run.bat https://x.com/usuario/status/123456789
```

## Qué hace

1. **Extrae** el contenido del tuit (texto, autor, media)
2. **Descarga** el video o imagen
3. **Genera** un titular viral y caption para Instagram
4. **Crea** un video vertical 1080x1920 con:
   - Fondo desenfocado
   - Imagen/video centrado
   - Texto superpuesto

## Output

Los archivos generados se guardan en:
- `output/<tweet_id>_reel.mp4` - El video listo para subir
- `output/<tweet_id>_caption.md` - El caption de Instagram

## Requisitos

```bash
pip install -r requirements.txt
```

Dependencias:
- `yt-dlp` - Descarga de media
- `moviepy` - Edición de video
- `Pillow` - Procesamiento de imágenes
- `requests` - Descargas HTTP
