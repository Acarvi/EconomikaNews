# Task: 09_Centralized_API_Key_Management

**Epic:** Seguridad
**Goal:** Mover llaves a un Vault centralizado en el futuro.

## Contexto
Actualmente, las API Keys se gestionan a través de archivos `.env` locales. Aunque hemos implementado un sistema de auditoría y redacción (Sanitizer) para evitar la exposición accidental, el almacenamiento en texto plano sigue siendo un riesgo.

## Objetivos
- [ ] Investigar soluciones de Vault (HashiCorp Vault, AWS Secrets Manager, GitHub Secrets, etc.).
- [ ] Implementar un proveedor de secretos centralizado que inyecte las llaves en tiempo de ejecución.
- [ ] Eliminar la dependencia de archivos `.env` persistentes en disco.

## Acceptance Criteria
- La aplicación no debe requerir un archivo `.env` para obtener llaves sensibles.
- El acceso al Vault debe estar securizado mediante identidades de máquina o roles de IAM.
- El sistema Anti-Exposición actual debe seguir funcionando como última línea de defensa.
