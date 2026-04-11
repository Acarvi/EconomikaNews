# Skill: Living Documentation y Memoria Técnica

Las IAs y los humanos pierden contexto en proyectos largos. Este skill asegura que la "intención" del sistema permanezca intacta.

## Memoria del Proyecto
1. **Memory Log (`memory_log.md`):**
   - Actualizar al final de cada sesión significativa.
   - Registrar decisiones críticas, "gotchas" técnicos (ej. parches de bibliotecas) y deuda técnica acumulada.
2. **Tests como Documentación:**
   - Los docstrings de los tests en `tests/` deben redactarse como **Living Documentation**.
   - No deben describir *qué* hace el código (eso lo hace el código), sino la **intención de negocio** y el comportamiento crítico esperado.

## Mantenimiento
- Trata la documentación con el mismo rigor que el código fuente.
- Antes de empezar, lee siempre los últimos cambios en `memory_log.md`.
