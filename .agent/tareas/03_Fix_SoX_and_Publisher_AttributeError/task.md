# Task 03: Fix SoX and Publisher AttributeError (Emergency)

**Épica:** Estabilidad de Integración y Fallbacks
**Prioridad:** CRÍTICA (Bloqueante)
**Estado:** In Progress

## Descripción
1. El sistema de subtitulado falla violentamente en entornos Windows sin SoX instalado al intentar el fallback a Whisper local. Se requiere una gestión de excepciones robusta.
2. El módulo `core.publisher` genera un `AttributeError` porque el `main.py` intenta llamar a `publish_video`, un atributo inexistente tras refactorizaciones previas. Se debe delegar la responsabilidad al `CentralPublishingHub`.

## Criterios de Aceptación
- [ ] `core/subtitler.py` captura excepciones de dependencias de sistema y continúa el renderizado sin subtítulos.
- [ ] `core/publisher.py` implementa `publish_video` y `schedule_publication` comunicándose vía POST HTTP con el Hub.
- [ ] Cobertura del 100% de la nueva lógica mediante tests funcionales.
- [ ] El sistema no crashea ante fallos de red con el Hub.

## Tareas Técnicas
- [ ] Refactorización de `core/subtitler.py`.
- [ ] Refactorización de `core/publisher.py`.
- [ ] Creación de tests funcionales en `tests/test_emergency_fix.py`.

## Logs / Contexto
- `AttributeError: module 'core.publisher' has no attribute 'publish_video'`
- `[WARN] Whisper failed: No such file or directory: 'sox'`
