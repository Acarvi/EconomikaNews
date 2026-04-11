# Task: Desacoplar el pipeline de generación de vídeo

**Épica:** Refactorización Arquitectónica
**Prioridad:** MEDIA
**Estado:** Pendiente

## Descripción
La clase `GENERATOR` es actualmente un bloque monolítico difícil de testear y propenso a fallos en cadena. Un error en un paso no crítico (como subtitulado) no debería invalidar todo el procesamiento anterior (descarga y conformado).

## Criterios de Aceptación
- [ ] Pipeline dividido en etapas atómicas e independientes.
- [ ] Implementación de persistencia intermedia entre etapas (si se desea poder reanudar desde un punto).
- [ ] Gestión de errores individualizada por etapa con política de reintentos.

## Tareas Técnicas
- [ ] Diseñar el objeto `VideoPipelineMetadata` para rastrear el progreso de un vídeo.
- [ ] Refactorizar el método `generate()` en una serie de llamadas a submódulos (`conform_stage`, `subtitles_stage`, `overlay_stage`).
- [ ] Implementar un manejador de excepciones que permita guardar el estado parcial del vídeo en caso de fallo.

## Logs / Contexto
Fallo observado durante el renderizado donde el fallo del subtitulador Gemini provocó la pérdida de todo el tiempo de procesamiento de conformado previo de audio y vídeo.
