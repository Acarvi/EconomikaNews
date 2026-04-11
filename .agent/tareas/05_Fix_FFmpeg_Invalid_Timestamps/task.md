# Task: Advertencias de Timestamps corruptos en FFmpeg

**Épica:** Calidad de Salida de Vídeo
**Prioridad:** ALTA
**Estado:** Pendiente

## Descripción
FFmpeg reporta numerosos fallos de timestamps en los vídeos descargados de X. Aunque el renderizado a veces termina, esto puede provocar frames "congelados", desincronización de audio o fallos de exportación en reproductores móviles.

## Criterios de Aceptación
- [ ] Los vídeos descargados deben ser "normalizados" antes de entrar en el pipeline de edición.
- [ ] Eliminación de las advertencias de `Invalid timestamps` en los logs mediante corrección de metadatos.
- [ ] Asegurar que el framerate sea constante (CFR) a 30fps sin saltos.

## Tareas Técnicas
- [ ] Modificar los comandos de FFmpeg en el generador de vídeo para incluir: `-async 1 -vsync 1`.
- [ ] Implementar un paso de "Conforming" inicial: `ffmpeg -i incoming.mp4 -filter:v "fps=30" -af "aresample=async=1" clean.mp4`.
- [ ] Verificar la integridad del stream de audio después de la corrección.

## Logs / Contexto
```text
[mov,mp4,m4a,3gp,3g2,mj2 @ 000001d48dea4700] Invalid timestamps stream=0, pts=274800900
```
**Causa:** Datos inconsistentes en los contenedores MP4 descargados de redes sociales.
