# Economika Cloud Server - Render Deployment

## Quick Start

### 1. Sube a GitHub
```bash
git init
git add server.py viral_scout.py cookie_utils.py scraper.py accounts.json Dockerfile requirements-server.txt
git commit -m "Economika cloud server"
git remote add origin https://github.com/TU_USUARIO/economika-server.git
git push -u origin main
```

### 2. Crea cuenta en Render
1. Ve a [render.com](https://render.com)
2. Regístrate con GitHub
3. Click "New +" → "Web Service"
4. Conecta tu repo de GitHub

### 3. Configura el servicio
- **Name**: `economika-server`
- **Region**: Frankfurt (más cerca de España)
- **Branch**: `main`
- **Runtime**: Docker
- **Instance Type**: Free

### 4. Variables de entorno (Environment)
Añade estas variables en Render:
```
TWITTER_COOKIES=<contenido de x.com_cookies.txt codificado en base64>
```

### 5. Deploy
Click "Create Web Service" y espera ~2-3 minutos.

---

## Mantener activo (IMPORTANTE)

Render apaga servicios gratuitos tras 15 min de inactividad.

### Solución: cron-job.org (gratis)

1. Ve a [cron-job.org](https://cron-job.org)
2. Crea cuenta gratis
3. Añade nuevo cronjob:
   - **URL**: `https://economika-server.onrender.com/health`
   - **Schedule**: Every 10 minutes
   - **Request Method**: GET

---

## Endpoints disponibles

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Info del servidor |
| GET | `/health` | Keep-alive (para cron) |
| GET | `/pending` | Tweets virales pendientes |
| POST | `/scan` | Forzar escaneo manual |
| POST | `/pending/{id}/mark-processed` | Marcar como procesado |
| DELETE | `/pending` | Limpiar cola |

---

## Conectar desde tu app local

Añadiré un botón en la GUI para sincronizar con el servidor cloud.
Tu URL será: `https://economika-server.onrender.com`
