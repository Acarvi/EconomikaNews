# Skill: Ejecución de Tests Anti-Regresión

Este documento define el protocolo para la ejecución de pruebas en el ecosistema EconomikaNoticias. El objetivo es garantizar la estabilidad funcional y prevenir amnesias técnicas.

## Protocolo de Ejecución

1. **Uso de Pytest:** Se debe utilizar siempre `pytest -v`.
   - Los nombres de los tests deben ser descriptivos (ej. `test_subtitler_force_spanish_translation`) para servir como recordatorio funcional.
2. **Ciclo de Desarrollo:**
   - Antes de iniciar una tarea, revisar si existen tests relacionados.
   - Antes de considerar una tarea como lista para revisión, **TODOS** los tests en la carpeta `tests/` deben estar en verde.
3. **Manejo de Fallos:**
   - Si un test falla, se debe corregir la regresión antes de continuar con nuevas funcionalidades, a menos que el test mismo esté obsoleto por un cambio de diseño aprobado.

## Recordatorio de Comandos
```powershell
# Ejecutar todos los tests con verbosidad alta
pytest -v

# Ejecutar un archivo específico
pytest tests/test_funcionalidades_core.py -v
```
