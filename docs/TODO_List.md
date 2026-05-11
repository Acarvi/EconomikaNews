# Economika - Future Backlog (TODO List)

This document tracks upcoming tasks for the Economika Noticias project. Lógica de implementación individual por ticket.

---

## 🚀 Infraestructura & Integración

### Auto-Arranque del Hub
- **Descripción**: Implementar lógica para "despertar" el servidor FastAPI del `CentralPublishingHub` directamente desde la GUI de Economika al iniciar la aplicación.
- **Prioridad**: MEDIA

---

## 🧠 IA & Visión (Multimodal)

### IA Anti-Banners (Recorte Automático)
- **Descripción**: Implementar lógica multimodal para detectar el final de los vídeos y calcular el `outro_crop_timestamp`.
- **Objetivo**: Recortar carátulas finales de cuentas de terceros y banners de "follow" innecesarios de forma automática.
- **Prioridad**: ALTA

---

## ⚡ Rendimiento & UX

### Optimización de Hilos (Backgrounding)
- **Descripción**: Mover el proceso de scouting (Viral Scout) y la subida de vídeos pesados a hilos de fondo.
- **Objetivo**: Evitar el congelamiento de la GUI durante las operaciones de red intensivas.
- **Prioridad**: MEDIA
