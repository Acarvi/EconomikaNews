# Task: Selector de Entornos (Launcher)

**Épica:** UX y Orquestación
**Prioridad:** CRÍTICA
**Estado:** In Progress

## Descripción
Implementar un launcher interactivo que permita seleccionar el entorno de ejecución (`main`, `development`, `implementación`). El modo `implementación` debe sincronizar automáticamente las ramas más recientes de todos los microservicios involucrados.

## Criterios de Aceptación
- [ ] Menú CLI al arrancar la aplicación.
- [ ] Detección automática de la rama feature/fix más reciente en los 3 repositorios.
- [ ] Sincronización (checkout) automática de ramas.
- [ ] Inyección de variables de entorno según el modo seleccionado.
- [ ] Auto-arranque de microservicios (`CentralAIService`, `CentralPublishingHub`) en segundo plano.

## Tareas Técnicas
- [ ] Crear `launcher.py` con menú interactivo.
- [ ] Implementar `utils/git_env_manager.py` para la lógica de Git.
- [ ] Modificar `economika_noticias.bat` para apuntar al launcher.
- [ ] Añadir validación de ramas y unit tests.

## Logs / Contexto
- `CentralAIService` está en `d:\Scripts\CentralAIService`
- `CentralPublishingHub` está en `d:\Scripts\CentralPublishingHub`
- `EconomikaNoticias` está en `d:\Scripts\EconomikaNoticias`
