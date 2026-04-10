# Task: Error de Conexión (WinError 10061) con CentralAIService

**Épica:** Estabilidad de Integración
**Prioridad:** ALTA
**Estado:** Pendiente

## Descripción
El generador de vídeos de `EconomikaNoticias` falla al intentar comunicarse con el servicio de análisis de `CentralAIService` en el puerto 8080. El error indica una negación activa de conexión, lo que sugiere que el servicio no está levantado o es inalcanzable.

## Criterios de Aceptación
- [ ] Implementar un mecanismo de "Pre-flight check" que verifique la disponibilidad del endpoint `/health` de CentralAIService antes de iniciar el procesamiento batch.
- [ ] Si el servicio no está disponible, el sistema debe intentar levantarlo automáticamente (si es local) o emitir una alerta clara y detener el proceso de forma segura.
- [ ] El error no debe suceder de forma inesperada en mitad de un renderizado costoso.

## Tareas Técnicas
- [ ] Crear un decorador o función utilitaria en `core/generator.py` para verificar salud de servicios externos.
- [ ] Configurar variables de puerto y host para que sean consistentes entre repositorios.
- [ ] Probar el escenario de "Service Down" y verificar la gestión de la excepción.

## Logs / Contexto
```text
Max retries exceeded with url: /v1/analyzer/draft... [WinError 10061] No connection could be made because the target machine actively refused it.
```
**Causa probable:** `CentralAIService` (FastAPI) no está corriendo o el puerto 8080 está bloqueado/no bindeado correctamente.
