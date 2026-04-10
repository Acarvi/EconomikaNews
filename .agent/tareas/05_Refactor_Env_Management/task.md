# Task: Estandarizar la carga de Variables de Entorno

**Épica:** Refactorización Arquitectónica
**Prioridad:** MEDIA
**Estado:** Pendiente

## Descripción
Existe una inconsistencia en cómo se cargan las variables de entorno entre los diferentes módulos. `ai_handler.py` usa una implementación manual frágil, mientras que otros servicios usan librerías estándar. Esto genera errores de carga dependiendo del directorio de ejecución.

## Criterios de Aceptación
- [ ] Carga centralizada y robusta de `.env` usando `python-dotenv` en todo el proyecto.
- [ ] Eliminación del código duplicado y manual de `load_env_file()`.
- [ ] Validación de variables obligatorias al arranque de la aplicación.

## Tareas Técnicas
- [ ] Instalar `python-dotenv`.
- [ ] Crear un módulo `core/config.py` o similar que centralice `load_dotenv()` y exponga las variables ya validadas.
- [ ] Actualizar todos los imports de variables de entorno para usar el nuevo módulo centralizado.

## Logs / Contexto
Actual inconsistencia entre `core/ai_handler.py` (custom loader) y `CentralAIService` (dotenv), causando que el generador ignore variables del `.env` principal si no se ejecuta desde el root exacto.
