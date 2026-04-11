# Skill: Protocolo de Testing y Anti-Regresión

Para garantizar que el sistema mantenga su integridad funcional a largo plazo, este skill define el estándar de validación.

## Ejecución de Tests
1. **Uso de Pytest:** Ejecuta siempre `pytest -v`.
   - La verbosidad alta permite que los nombres de los tests funcionen como un **recordatorio funcional** de las reglas de negocio que el sistema está protegiendo.
2. **Criterio de Aceptación:**
   - Una tarea **NUNCA** se considera "lista para revisión" si existe un solo test fallando en la carpeta `tests/`.
   - Si una nueva funcionalidad rompe un test antiguo, la prioridad absoluta es resolver la regresión antes de continuar.

## Recordatorio de Comandos
```powershell
# Ejecución estándar con nombres de tests visibles
pytest -v
```
