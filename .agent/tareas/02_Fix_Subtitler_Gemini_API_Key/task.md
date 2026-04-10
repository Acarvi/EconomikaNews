# Task: Caída del Traductor de Subtítulos por API Key vacía

**Épica:** Robustez del Pipeline de IA
**Prioridad:** ALTA
**Estado:** Pendiente

## Descripción
El proceso de subtitulado falla estrepitosamente cuando la variable `GEMINI_API_KEY` existe en el entorno pero está vacía. El cargador actual no maneja correctamente los strings vacíos como valores inválidos, saltándose los fallbacks de seguridad.

## Criterios de Aceptación
- [ ] El sistema debe validar que la API Key no solo exista, sino que tenga un formato válido de Google AI antes de instanciar el cliente.
- [ ] Implementar un fallback automático a Whisper local (si está disponible) en caso de fallo de red o API Key inválida.
- [ ] No permitir el avance del renderizado si el paso de subtitulado es crítico y no hay motores disponibles.

## Tareas Técnicas
- [ ] Sustituir `load_env_file()` custom por la librería estándar `python-dotenv`.
- [ ] Refactorizar `core/subtitler.py` para validar explícitamente la API Key: `if not key or len(key) < 10: raise ValueError`.
- [ ] Asegurar que `ai_handler.py` maneje errores de carga de entorno de forma centralizada.

## Logs / Contexto
```text
[GENERATOR] Subtitles failed: Missing key inputs argument!
```
**Causa raíz:** En `core/subtitler.py`, `genai.Client(api_key=GEMINI_API_KEY)` recibe un string vacío porque `.env` tiene `GEMINI_API_KEY=` sin valor.
