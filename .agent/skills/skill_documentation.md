# Skill: Documentación Viva y Memoria Técnica

Este documento establece las reglas para mantener la memoria del proyecto EconomikaNoticias, evitando la pérdida de contexto en tareas de larga duración.

## Componentes de la Memoria

1. **Memory Log (`memory_log.md`):**
   - Debe actualizarse al final de cada sesión significativa.
   - Debe registrar: decisiones de diseño, "gotchas" técnicos (ej. errores de encoding en Windows) y deudas técnicas.
2. **Docstrings de Tests:**
   - Los tests no solo prueban código, documentan intención de negocio.
   - Cada test en `tests/` debe tener un docstring detallado que explique el **PORQUÉ** del comportamiento esperado.

## Mantenimiento
- Al heredar un repositorio o retomar una tarea, la primera acción debe ser leer el `memory_log.md` y los skills en `.agent/skills/`.
- La documentación debe ser tratada como código: precisa, sin redundancias y versionada.
