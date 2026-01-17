# 🛠️ DEVELOPER.md - Documentación Técnica

## Arquitectura del Sistema
El proyecto sigue una arquitectura Híbrida Cloud-Local:

1. **Local (Windows)**:
   - `main.py`: GUI (Tkinter) para revisión manual.
   - `generator.py`: Renderizado pesado usando MoviePy/FFmpeg.
   - `Viral Scout`: Escaneo de tendencias via Twikit.
2. **Cloud (Render)**:
   - `server.py`: Servidor FastAPI que mantiene la cola de publicación.
   - Publica automáticamente cuando llega la hora programada (`target_time`).

## Variables de Entorno (Environment Variables)
Configuración necesaria tanto en local (`.env` o variables de sistema) como en Render:

| Variable | Descripción |
|----------|-------------|
| `GEMINI_API_KEY` | Key de Google AI Studio. |
| `IG_ACCESS_TOKEN` | Token de larga duración de Facebook Graph API. |
| `IG_USER_ID` | ID de la cuenta de Instagram Business. |
| `FB_PAGE_ID` | ID de la página de Facebook. |
| `ECONOMIKA_SERVER_URL` | URL de tu instancia en Render (ej: `https://economika.onrender.com`). |

## Base de Datos (Persistencia)
- `scheduled_posts.json`: Almacena la cola en el servidor (persistencia efímera en Render free tier).
- `history.json`: (Opcional en Viral Scout) para evitar duplicados.

## Mantenimiento
El sistema `utils/cleanup.py` se ejecuta automáticamente al abrir la app y:
- Borra carpetas de `output/` con más de **7 días** de antigüedad.
- Elimina archivos temporales de `MoviePy` que no se cerraron correctamente.
