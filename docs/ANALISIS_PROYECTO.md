# Análisis Integral: Economika Noticias v2.0

## 1. Visión General del Sistema
El proyecto ha evolucionado de un script local a una arquitectura híbrida **Nube-Local** sofisticada.
- **Nube (Render)**: `server.py` actúa como "Cerebro". Ejecuta `ViralScout` 24/7, detecta contenido viral, y alinea la cola de publicación.
- **Local (PC)**: `main.py` actúa como "Fábrica". Descarga, renderiza vídeos pesados (ffmpeg), permite curación manual humana (Tkinter), y sube el contenido final.

## 2. Puntos Fuertes Actuales
- **Eficiencia de Costes**: Uso de Gemini Flash Lite (muy barato) y Render Free Tier.
- **Calidad de Contenido**: El sistema de filtro doble (Pre-IA + Curación Manual) asegura que no se publique basura.
- **Viralidad**: El algoritmo matemático en `viral_scout.py` (Ratio Likes/Followers) es sólido para detectar anomalías positivas.
- **Estabilidad**: El refactor reciente a `lifespan` en FastAPI y el uso de un planificador robusto (`apscheduler`).

## 3. Puntos Débiles y Riesgos
- **Dependencia de Cookies**: `viral_scout.py` depende de cookies de Twitter (`x.com_cookies.txt`). Si caducan, el escaneo se detiene.
- **Cuello de Botella Local**: La renderización depende de tu PC. Si tu PC está apagado, no se generan *nuevos* vídeos (aunque el server sí puede publicar los ya programados).
- **Gestión de Archivos**: Aunque existe `utils/cleanup.py`, el crecimiento de la carpeta `output/` y `downloads/` puede ser rápido si se procesan muchos vídeos.

## 4. Análisis de "Jon" y Nuevas Fuentes
La incorporación de perfiles técnicos como **@Jongonzlz** (Jon González) eleva el nivel editorial.
- **Valor**: Gráficos de pensiones y datos macroeconómicos detallados.
- **Desafío**: Estos tuits suelen ser imágenes estáticas.
- **Solución**: El sistema ya soporta `Image -> Video` (Pan/Zoom effect), pero convendría mejorar la plantilla para gráficos financieros (evitar recortes drásticos en formato 9:16).

## 5. Hoja de Ruta Sugerida (Roadmap)

### Fase 1: Consolidación (Actual)
- [x] Refactor Server (Hecho).
- [ ] Ampliar fuentes España (En proceso).
- [ ] Asegurar limpieza automática (`cleanup.py`).

### Fase 2: Versión USA ("The Wolf")
- **Objetivo**: Mercado americano, alta frecuencia.
- **Cambios Necesarios**:
  - **Detector de Tickers ($)**: Escanear `$SPY`, `$NVDA`.
  - **Estilo Visual**: Overlay tipo Bloomberg Terminal (fuente monoespaciada, colores neón).
  - **Fuente de Datos**: Pivotar de "Influencers" a "Data Feeds" (@unusual_whales, @FirstSquawk).

### Fase 3: Automatización Total (Cloud Rendering)
- Mover la generación de vídeo a la nube (ej. usando `MoviePy` en un worker de Render de pago o una Cloud Function). Esto eliminaría la necesidad de tener tu PC encendido para crear contenido.

## 6. Auditoría de Limpieza
El sistema cuenta con `utils/cleanup.py`.
- **Estado**: Funcional.
- **Recomendación**: Se recomienda invocar `cleanup_old_files` al inicio de `main.py` para mantener el disco limpio de archivos temporales antiguos.
