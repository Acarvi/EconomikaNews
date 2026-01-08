# 🚀 Guía: Activando el Nivel de Pago (Pay-as-you-go) de Gemini API

Si estás recibiendo el error **429 (Quota Exceeded)** con frecuencia, es porque has alcanzado el límite de la versión gratuita (15 peticiones por minuto). Pasar al nivel de pago elimina estas esperas y te da prioridad total.

---

## 🏎️ Comparativa de Límites (Diciembre 2025/Enero 2026)

| Característica | Nivel Gratuito (Default) | Nivel de Pago (Plan Flexible) |
| :--- | :--- | :--- |
| **Velocidad (RPM)** | 10 a 15 peticiones / min | **2,000 peticiones / min** |
| **Volumen (TPM)** | 1M de tokens / min | **4M de tokens / min** |
| **Límite Diario** | 250 a 1,000 consultas / día | **Ilimitado** (pagas lo que usas) |
| **Privacidad** | Google *puede* usar tus datos para entrenar | **Tus datos NO se usan para entrenar** |
| **Costo Mínimo** | $0.00 | $0.00 (solo pagas si superas la capa gratis) |

> [!NOTE]
> **Sobre tu suscripción "Gemini Advanced/Pro":** La suscripción de $20/mes que pagas para usar el chat de Gemini en la web **ES DISTINTA** de la API. Esa suscripción no sube los límites de tu llave de API. La API se factura aparte por uso (aunque como viste, para tu volumen el costo será de céntimos).

---

## 🛠️ Pasos para activar el Pago (Setup)

### 1. Vincular Facturación en Google AI Studio
1. Entra en tu panel de **[Google AI Studio - Billing](https://aistudio.google.com/app/billing)**.
2. Identifica tu proyecto actual (donde creaste tu API Key).
3. Haz clic en el botón **"Set up billing"** o **"Upgrade to pay-as-you-go"**.
4. Te redirigirá a la Consola de Google Cloud.

### 2. Configurar el Método de Pago
1. En Google Cloud, selecciona o crea una **Cuenta de Facturación (Billing Account)**.
2. Introduce una tarjeta de crédito/débito. 
3. **Truco:** Si eres nuevo en Google Cloud, suelen regalar **$300 en créditos**, por lo que tus primeros meses de API serán gratis aunque tengas activado el pago.

### 3. Verificar en AI Studio
1. Una vez vinculada la tarjeta, vuelve a [AI Studio](https://aistudio.google.com/app/apikey).
2. Deberías ver que tu proyecto ya no tiene la etiqueta "Free Tier" y ahora indica que es un plan basado en uso.
3. El script de Python detectará automáticamente que ya no tiene límites y dejará de dar el error 429.

---

## 📈 Estimación de Costos para "Economika"

| Item | Uso (Aprox) | Costo Gemini 1.5 Flash |
| :--- | :--- | :--- |
| **1 Tuit (Texto + Video)** | 10,000 tokens | $0.00075 |
| **10 Tuits al día** | 100,000 tokens | $0.0075 |
| **Total al Mes** | **3M tokens** | **$0.22 (menos de 1 Euro)** |

> [!IMPORTANT]
> **Recomendación:** Activa la facturación. El costo es tan bajo que es prácticamente gratis para tu flujo de trabajo, y la ganancia en velocidad y estabilidad es total.

---

## 🔗 Enlaces Útiles
- **[Panel de Consola Google Cloud](https://console.cloud.google.com/billing)** (Para ver tus facturas).
- **[Calculadora de Precios Oficial](https://ai.google.dev/pricing)**.
- **[Límites de Cuota por Modelo](https://ai.google.dev/gemini-api/docs/quota)**.
