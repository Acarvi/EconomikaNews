# Guía de Integración con YouTube Shorts

Este documento explica cómo añadir la funcionalidad de subir vídeos a YouTube Shorts.

---

## Resumen

YouTube Shorts son vídeos verticales de menos de 60 segundos. Usaremos la **YouTube Data API v3** para subir vídeos de forma programática.

---

## Paso 1: Preparar la Cuenta de YouTube

Para que el canal sea independiente pero esté ligado a tu cuenta principal:

1. Inicia sesión en YouTube con tu cuenta principal **"ECONÓMIKA"**.
2. Ve a [Configuración de YouTube](https://www.youtube.com/account).
3. Haz clic en **"Añadir o gestionar canales"**.
4. Haz clic en **"Crear un canal"**.
5. Ponle el nombre: **"ECONÓMIKA NOTICIAS"**. Esto crea una **Cuenta de Marca (Brand Account)**.
   - *Nota: Esto permite que varias personas gestionen el canal sin compartir la contraseña de tu cuenta personal.*

---

## Paso 2: Crear Proyecto en Google Cloud

1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un nuevo proyecto (ej. `economika-shorts`).
3. En el menú de navegación, ve a **APIs & Services** → **Library**.
4. Busca **YouTube Data API v3** y actívala.

---

## Paso 3: Configurar Pantalla de Consentimiento (OAuth Consent Screen)

1. Ve a **APIs & Services** → **OAuth consent screen**.
2. Selecciona **External** y haz clic en **Create**.
3. Rellena los datos básicos (App name: `Economika Noticias`, etc.).
4. **IMPORTANTE (Testing Mode):** En la sección **Test users**, haz clic en **+ ADD USERS**.
5. Añade el correo de tu cuenta de Google principal (el que usas para "ECONÓMIKA"). 
   - *Sin esto, Google bloqueará el acceso con el Error 403: access_denied.*
6. Guarda y continúa hasta el final.

---

## Paso 4: Configurar Credenciales OAuth 2.0

1. Ve a **APIs & Services** → **Credentials**.
2. Haz clic en **Create Credentials** → **OAuth client ID**.
3. Selecciona **Desktop app** como tipo de aplicación.
4. Descarga el archivo JSON de credenciales y guárdalo como `client_secrets.json` en la carpeta del proyecto.

---

## Paso 3: Instalar Dependencias

```bash
pip install google-api-python-client google-auth-oauthlib
```

Añade a `requirements.txt`:
```
google-api-python-client
google-auth-oauthlib
```

---

## Paso 4: Crear el Script de Subida

Crea un nuevo archivo `youtube_uploader.py`:

```python
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
CLIENT_SECRETS_FILE = 'client_secrets.json'
CREDENTIALS_FILE = 'youtube_token.pickle'

def get_authenticated_service():
    credentials = None
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'rb') as f:
            credentials = pickle.load(f)
    
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            credentials = flow.run_local_server(port=8080)
        
        with open(CREDENTIALS_FILE, 'wb') as f:
            pickle.dump(credentials, f)
    
    return build('youtube', 'v3', credentials=credentials)

def upload_short(video_path: str, title: str, description: str) -> str:
    """
    Sube un vídeo a YouTube como Short.
    Returns: Video ID if successful.
    """
    youtube = get_authenticated_service()
    
    body = {
        'snippet': {
            'title': title[:100],  # Max 100 chars for Shorts
            'description': description,
            'tags': ['shorts', 'economika', 'noticias'],
            'categoryId': '25'  # News & Politics
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }
    
    media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
    
    request = youtube.videos().insert(
        part='snippet,status',
        body=body,
        media_body=media
    )
    
    response = request.execute()
    video_id = response.get('id')
    print(f"[SUCCESS] YouTube Short uploaded: https://youtube.com/shorts/{video_id}")
    return video_id
```

---

## Paso 5: Primera Autenticación

La primera vez que ejecutes el script, se abrirá un navegador para que autorices la app:

```bash
python youtube_uploader.py
```

Se guardará un archivo `youtube_token.pickle` que permitirá subidas automáticas en el futuro.

---

## Paso 6: Integrar en el Flujo de Publicación

Modifica `publisher.py` para llamar a `upload_short` desde `schedule_batch`:

```python
from youtube_uploader import upload_short

# Dentro de schedule_batch, después de subir a Instagram:
try:
    upload_short(post['reel_path'], post.get('shorts_title', 'Economika Noticias'), post['caption'])
except Exception as e:
    print(f"[WARNING] YouTube upload failed: {e}")
```

---

## Limitaciones Importantes

| Límite | Valor |
|--------|-------|
| Cuota diaria | 10,000 unidades (aprox. 6 uploads/día en tier gratuito) |
| Duración máx. Short | 60 segundos |
| Ratio de aspecto | 9:16 (vertical) |

> [!CAUTION]
> YouTube tiene cuotas muy estrictas. Si subes más de 6-8 vídeos al día, necesitarás solicitar un aumento de cuota a Google.

---

## Próximos Pasos

1. Crear el archivo `youtube_uploader.py` en el proyecto.
2. Obtener las credenciales OAuth de Google Cloud.
3. Ejecutar el script una vez manualmente para autorizar.
4. Integrar la llamada en el flujo de publicación.
