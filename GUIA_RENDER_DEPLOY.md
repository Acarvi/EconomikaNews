# Guía de Despliegue en Render

Este documento explica cómo actualizar y redesplegar el servidor `server.py` en Render.

---

## Requisitos Previos

- Cuenta en [Render](https://render.com/) (el tier gratuito es suficiente).
- Repositorio de Git conectado (GitHub/GitLab) con el código de `EconomikaNoticias`.

---

## Pasos para Redesplegar

### 1. Sube los cambios a tu repositorio

```bash
cd d:\MEGA\Scripts\EconomikaNoticias
git add .
git commit -m "feat: server-side scheduling queue"
git push origin main
```

### 2. Accede a tu Dashboard de Render

1. Ve a [dashboard.render.com](https://dashboard.render.com/).
2. Selecciona tu servicio (ej. `economika-server`).

### 3. Trigger Manual Deploy (Opcional)

Si Render no detecta automáticamente el push:
1. En la página del servicio, haz clic en **"Manual Deploy"** (arriba a la derecha).
2. Selecciona **"Deploy latest commit"**.

### 4. Verifica el Deploy

1. En la pestaña **"Logs"**, verás el proceso de construcción.
2. Busca el mensaje: `🚀 Scheduler started - Viral Scout will run every hour`.
3. Si ves errores de dependencias, revisa `requirements-server.txt`.

---

## Variables de Entorno Necesarias

Si has añadido nuevas funcionalidades que necesitan tokens, asegúrate de añadirlas en **Environment** dentro del Dashboard de Render:

| Variable | Descripción |
|----------|-------------|
| `IG_ACCESS_TOKEN` | Token de Instagram Graph API |
| `IG_USER_ID` | ID de usuario de Instagram |
| `FB_PAGE_ID` | ID de la página de Facebook |
| `GEMINI_API_KEY` | ⭐ **NUEVO** - API Key de Google Gemini para generación de contenido |

> [!IMPORTANT]
> El `GEMINI_API_KEY` es necesario para que el servidor genere automáticamente los titulares y captions.
> Lo puedes obtener gratis en [Google AI Studio](https://aistudio.google.com/).

> [!NOTE]
> Por seguridad, es mejor usar variables de entorno en el servidor en lugar de subir `config_api.json` al repositorio.

---

## Verificar que Funciona

Abre en el navegador:
```
https://tu-servicio.onrender.com/health
```

Debes ver:
```json
{"status": "ok", "timestamp": "2026-01-12T14:00:00"}
```

---

## Solución de Problemas

| Problema | Solución |
|----------|----------|
| El servicio deja de responder tras 15 min | Render duerme servicios gratuitos. El keep-alive ping debería evitarlo. |
| Error `ModuleNotFoundError` | Revisa que las dependencias estén en `requirements-server.txt`. |
| Error de token/permisos | Verifica las variables de entorno en el Dashboard de Render. |
