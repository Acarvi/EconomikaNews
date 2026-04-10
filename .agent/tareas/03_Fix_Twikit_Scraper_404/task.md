# Task: Fallo total de Twikit Scraper (Error 404 KEY_BYTE indices)

**Épica:** Ingesta de Datos (Scraping)
**Prioridad:** ALTA
**Estado:** Pendiente

## Descripción
El scraper de X (Twitter) basado en Twikit no puede obtener los datos de los perfiles solicitados (ej. @wallstwolverine). Esto se debe a cambios en la estructura interna de la API no oficial de X que la versión instalada de Twikit no soporta.

## Criterios de Aceptación
- [ ] Actualizar Twikit a la versión más reciente y verificar compatibilidad.
- [ ] Implementar un mecanismo de reintento con rotación de User-Agents o sesiones.
- [ ] Definir un fallback (ej. RSS o scraping simplificado vía Nitter) para evitar el bloqueo total de la obtención de noticias.

## Tareas Técnicas
- [ ] Actualizar `requirements.txt` con la última versión de Twikit.
- [ ] Revisar `core/viral_scout.py` para depurar el punto exacto donde fallan los índices.
- [ ] Implementar logs detallados de la respuesta HTTP antes del fallo de parseo.

## Logs / Contexto
```text
Fallo total buscando a @wallstwolverine: Couldn't get KEY_BYTE indices | status: 404
```
**Causa Proporcional:** Cambios en el frontend/API no oficial de X que rompen el mapeado de Twikit.
