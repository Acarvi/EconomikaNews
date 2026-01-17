# 🗞️ Economika Noticias

Sistema automatizado de creación y publicación de contenido para redes sociales con enfoque liberal-libertario.

## 🚀 Características Principales
- **Viral Scout**: Escaneo inteligente de tendencias en Twitter (X).
- **IA Content Engine**: Generación de titulares impactantes y captions detallados usando Google Gemini.
- **A/B Testing**: Publicación dual (Branded vs Raw) para maximizar el alcance.
- **Detección de Fuente**: Identificación automática de la fuente original de los medios.
- **Multi-plataforma**: Soporte para Instagram Reels, Stories y Facebook Reels.
- **Auto-Cleanup**: Sistema integrado para evitar la saturación de archivos locales.

## 📁 Estructura del Proyecto
- `main.py`: Interfaz gráfica y orquestador principal.
- `server.py`: Backend en la nube (Render) para publicación programada.
- `generator.py`: Motor de renderizado de video (MoviePy).
- `ai_handler.py`: Integración con la API de Google Gemini.
- `publisher.py`: Lógica de subida a redes sociales y hosting temporal (Catbox).
- `docs/`: Guías detalladas y documentación técnica.
- `tools/`: Scripts de utilidad y diagnóstico.
- `utils/`: Utilidades del sistema (Cleanup, etc).

## 🛠️ Requisitos Rápidos
1. **Python 3.10+**
2. **FFmpeg** instalado en el sistema.
3. **API Keys**: Google Gemini, Instagram Graph API.

Para más detalles, consulta [DEVELOPER.md](file:///d:/MEGA/Scripts/EconomikaNoticias/docs/DEVELOPER.md).
