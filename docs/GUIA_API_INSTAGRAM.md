# 🛠️ Guía: Cómo configurar la API de Instagram (Business)

Has tenido un error `190: Invalid OAuth access token` porque actualmente estás usando un token de la **"Instagram Basic Display API"** (que empieza por `IGAA...`). 

Esa API es **SOLO DE LECTURA** y no permite publicar Reels. Para publicar, necesitas usar la **"Instagram Graph API"** (la versión para empresas/creadores).

Sigue estos pasos para conseguir el token correcto:

### 1. Requisitos Previos
*   Tu cuenta de Instagram debe ser de tipo **Empresa** o **Creador** (Cámbialo en la App de IG: Configuración > Tipo de cuenta).
*   Debes tener una **Página de Facebook** vinculada a esa cuenta de Instagram.

### 2. Crear la App en Meta for Developers
1.  Ve a [Meta for Developers](https://developers.facebook.com/) y entra en "Mis aplicaciones".
2.  Pulsa **"Crear aplicación"**.
3.  Selecciona el tipo: **"Otros"** -> **"Siguiente"**.
4.  Selecciona **"Empresa"** (o "Business"). Esto es fundamental para que aparezca la API de Instagram Graph.
5.  Dale un nombre (ej: "Economika Publisher").

### 3. Configurar el Producto
1.  En el panel de la aplicación, busca **"API de Instagram Graph"** y pulsa "Configurar".
2.  Añade también el producto **"Inicio de sesión con Facebook"**.

### 4. Obtener el Token de Acceso (Forma rápida)
Para probarlo hoy mismo sin programar el login:
1.  Ve a la herramienta [Explorador de la Graph API](https://developers.facebook.com/tools/explorer/).
2.  En **"Aplicación de Meta"**, elige tu nueva App ("Economika Publisher").
3.  En **"Usuario o página"**, elige **"Obtener token de acceso a la página"**.
4.  Selecciona tu página de Facebook vinculada.
5.  **IMPORTANTE:** Asegúrate de que en "Permissions" estén marcados estos 3:
    *   `instagram_basic`
    *   `instagram_content_publish`
    *   `pages_show_list`
    *   `pages_read_engagement`
6.  Pulsa "Generate Access Token".

### 5. Configurar el Script
Copia el Token que empieza por `EAA...` y pégalo en tu archivo `config_api.json`:

```json
{
    "access_token": "TU_NUEVO_TOKEN_EAA...",
    "ig_user_of_id": "TU_ID_DIFERENTE_SI_HA_CAMBIADO"
}
```

> [!TIP]
> Si el token que obtienes es corto (dura 1-2 horas), puedes usar el "Access Token Tool" de Meta para extenderlo a un **Long-Lived Token** (60 días).

**¿Cómo saber si el nuevo token es correcto?**
Cualquier token que empiece por `IGAA` **FALLARÁ**. El correcto debe empezar por `EAA`. 
