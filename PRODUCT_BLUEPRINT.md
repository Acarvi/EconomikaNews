# Economica News — Product Blueprint & MVP Roadmap

## 0. Estado del proyecto

El proyecto anterior fue reseteado de forma deliberada.

La implementación antigua queda archivada en:

```txt
_archive/
```

Este documento define el nuevo producto desde cero. Debe ser la referencia principal para Codex, ingeniería y futuras decisiones de arquitectura.

---

# 1. Nombre del producto

Nombre de producto:

```txt
Economica News
```

Idioma inicial:

```txt
Español
```

Expansión futura:

```txt
Soporte multidioma para nuevas cuentas/marcas.
```

---

# 2. Visión del producto

Economica News es una fábrica semi-automática de contenido político/económico para redes sociales.

El sistema debe detectar publicaciones virales de cuentas seleccionadas en X/Twitter, transformarlas automáticamente en piezas verticales con estética de breaking news y permitir que el usuario apruebe o rechace antes de publicar.

Objetivo principal:

```txt
Convertir contenido viral de X en Reels/Shorts profesionales, con mínima intervención humana.
```

No es un editor de vídeo manual.

No es un dashboard genérico de redes.

No es un simple scraper.

Es una cadena de producción editorial:

```txt
Descubrir → puntuar → generar → revisar → programar → publicar
```

---

# 3. Usuario principal

Usuario inicial:

```txt
Owner/editor de una página grande de Instagram y YouTube sobre economía/política.
```

Necesidad:

```txt
Producir mucho contenido vertical profesional sin tener que editar vídeos largos manualmente.
```

Contexto:

- Ya existe audiencia.
- El cuello de botella es producción.
- El usuario quiere revisar y aprobar, no editar manualmente.
- El producto debe ahorrar tiempo, no crear más trabajo.

---

# 4. Flujo MVP confirmado

Flujo principal:

```txt
1. La app escanea cuentas X configuradas.
2. Detecta publicaciones virales dentro de un intervalo de tiempo.
3. Calcula puntuación de viralidad.
4. Muestra candidatos en dashboard/grid.
5. Genera automáticamente una pieza vertical branded.
6. El usuario revisa preview.
7. El usuario aprueba/rechaza.
8. Lo aprobado entra en cola programada.
9. Se publica en Instagram Reels y YouTube Shorts.
```

Modo de automatización:

```txt
Semi-automático.
```

El sistema genera la pieza completa, pero el usuario decide si se publica.

---

# 5. Requisito crítico del MVP

Sin discovery automático de X no hay MVP.

El usuario no considera suficiente un MVP basado solo en URLs manuales.

Motivo:

```txt
El valor diferencial del producto es detectar automáticamente qué está funcionando en X entre cuentas seleccionadas.
```

Implicación técnica:

```txt
La prioridad número uno del proyecto es resolver el ingestion/discovery de X.
```

Render, captions, publishing y cola son importantes, pero dependen de que haya candidatos.

---

# 6. Fuente principal de contenido

Fuente principal:

```txt
X/Twitter
```

Contenido objetivo:

```txt
Publicaciones de cuentas seleccionadas asociadas con derecha española, liberalismo, economía, política y actualidad.
```

Tipos de publicaciones soportadas en MVP:

```txt
1. Vídeos de X.
2. Imágenes de X.
```

Tipos futuros:

```txt
3. Texto puro como screenshot.
4. Threads.
5. Quotes/replies.
```

Decisión MVP:

```txt
Empezar con vídeos e imágenes.
```

Aunque se acepta que cualquier tweet podría convertirse en contenido, para reducir complejidad inicial el MVP prioriza tweets con media.

---

# 7. Configuración de cuentas objetivo

Para MVP:

```txt
Archivo config editable.
```

Ejemplo futuro:

```txt
config/accounts.yaml
```

Formato sugerido:

```yaml
accounts:
  - handle: wallstwolverine
    category: politica
    weight: 1.0
    followers_hint: null

  - handle: juanrallo
    category: economia
    weight: 1.2
    followers_hint: null
```

Razón:

- Más simple que UI de gestión.
- Fácil de versionar sin secretos.
- Suficiente para MVP.

Futuro:

```txt
Pantalla para añadir/quitar cuentas desde la app.
```

---

# 8. Discovery de X

## 8.1 Requisito funcional

El sistema debe escanear las últimas publicaciones de cuentas configuradas durante un rango temporal.

Rango inicial:

```txt
Últimas 24 horas.
```

Futuro:

```txt
Rango configurable: 1h, 3h, 6h, 12h, 24h, 48h.
```

## 8.2 Comportamiento deseado

Idealmente el sistema debe poder funcionar como flujo continuo:

```txt
- Escanea periódicamente.
- Mantiene candidatos en cola.
- Cuando el usuario abre la app, ve candidatos ya preparados.
```

Para MVP técnico inicial, aceptable:

```txt
- Botón manual “Scan now”.
- Escanea últimas 24 horas.
- Muestra candidatos.
```

Pero el diseño debe permitir scheduler posterior.

## 8.3 Restricción técnica

Twikit/Nitter/snscrape no deben ser asumidos como solución estable.

La solución debe investigarse e implementarse con prioridad, considerando:

```txt
A) Browser scraping con sesión real logueada.
B) Extracción DOM visible.
C) API oficial si algún día es viable.
D) Scraper externo solo si coste y estabilidad compensan.
```

El usuario prefiere no pagar por scraping/API.

Si se demuestra imposible sin pagar, debe documentarse con pruebas.

---

# 9. Scoring de viralidad

El score no puede medir engagement bruto sin contexto.

Un tweet con 10.000 likes de una cuenta de 1M seguidores no equivale a un tweet con 2.000 likes de una cuenta de 20k seguidores.

## 9.1 Inputs deseados

```txt
- likes
- reposts/retweets
- replies
- views, si están disponibles
- followers aproximados
- antigüedad del tweet
- tipo de media
```

## 9.2 Fórmula inicial sugerida

```txt
raw_engagement = likes + (reposts * 4) + (replies * 2)

relative_engagement = raw_engagement / sqrt(max(followers, 1000))

age_hours = max(hours_since_posted, 1)

velocity = relative_engagement / sqrt(age_hours)

score = velocity
```

Si hay views:

```txt
view_rate = raw_engagement / max(views, 1)
score = velocity * (1 + view_rate)
```

## 9.3 Normalización

El score debe ser comparable entre cuentas grandes y pequeñas.

Debe permitir detectar:

```txt
- posts virales absolutos;
- posts anormalmente virales para una cuenta concreta;
- posts que están creciendo rápido.
```

## 9.4 Ranking

Para MVP:

```txt
Mostrar todos los candidatos encontrados en el rango, ordenados por score.
```

No limitar artificialmente a top 10/20 si el escaneo ya es pequeño.

La UI puede destacar:

```txt
Top 10 recomendados.
```

---

# 10. Dashboard MVP

Interfaz MVP:

```txt
Dashboard/grid local.
```

El usuario prefiere que funcione bien por encima de una tecnología concreta.

Recomendación técnica:

```txt
Web local con FastAPI + frontend simple.
```

Razón:

- Mejor para grid/dashboard que Tkinter.
- Más fácil mostrar previews, tarjetas, filtros y estados.
- Puede seguir siendo local.
- Escalable hacia futuro.

Alternativa aceptable:

```txt
Tkinter solo si acelera MVP.
```

## 10.1 Vista de candidatos

Cada tarjeta debe mostrar:

```txt
- cuenta origen
- texto del tweet
- preview media
- URL tweet
- hora publicación
- likes
- reposts
- replies
- views si están disponibles
- score viralidad
- resumen IA
- título sugerido
- caption sugerido
- estado
```

Estados:

```txt
discovered
generated
approved
rejected
queued
published
failed
```

## 10.2 Acciones

MVP:

```txt
- Generate
- Approve
- Reject
- Regenerate caption with instruction
```

No MVP:

```txt
- editor completo de vídeo
- timeline editing
- edición manual avanzada
```

---

# 11. Revisión humana

El usuario quiere aprobar o rechazar, no editar manualmente.

Pero sí necesita poder escribir instrucciones a la IA para reescribir caption/título.

MVP debe permitir:

```txt
- ver preview
- aprobar
- rechazar
- escribir comentario/instrucción para IA
- regenerar caption/título/headline según instrucción
```

No debe permitir inicialmente:

```txt
- editar vídeo a mano
- recortar clips manualmente
- timeline editor
- subtítulos palabra por palabra
```

---

# 12. Estilo del contenido generado

Estilo visual:

```txt
Breaking news style.
```

Formato:

```txt
Vertical 9:16 optimizado para Reels/Shorts.
```

Elementos visuales:

```txt
- branding Economica News
- cabecera/titular grande
- tweet/post como fuente visual
- subtítulos dinámicos
- estética rápida de actualidad
- posible ticker/banner inferior
```

Audio MVP:

```txt
Sin audio añadido.
```

Si el tweet trae vídeo:

```txt
Mantener audio original solo si es útil y legalmente aceptable.
```

Pero prioridad confirmada:

```txt
Subtítulos, no voz IA.
```

No MVP inicial:

```txt
- narración IA
- doblaje
- música compleja
- edición cinematográfica
```

---

# 13. Duración

Duración objetivo:

```txt
Depende del contenido.
```

Regla inicial sugerida:

```txt
- Imagen/texto: 8–15 segundos.
- Vídeo corto: duración original si encaja, preferiblemente <45 segundos.
- Vídeo largo: seleccionar fragmento o resumir en futuro.
```

Para MVP:

```txt
No intentar resolver clips largos complejos.
```

Prioridad:

```txt
Vídeos/imágenes fáciles de transformar rápido.
```

---

# 14. Titular dentro del vídeo

Cada pieza debe renderizar una caja de titular.

La IA debe generar:

```txt
- headline principal
- subtitle/caption corto para overlay
- caption largo para plataforma
```

Ejemplo estructura:

```txt
HEADLINE:
"El dato que desmonta el relato fiscal del Gobierno"

SUBHEAD:
"El gráfico que se ha hecho viral entre economistas liberales"

CAPTION:
Texto optimizado para Instagram/YouTube Shorts.
```

---

# 15. Caption IA

El caption debe:

```txt
- ser riguroso;
- aportar información;
- evitar inventar datos;
- hacer fact-check cuando sea posible;
- citar fuentes cuando pueda;
- tener tono liberal/libertario;
- estar optimizado para Instagram/YouTube Shorts.
```

Tono:

```txt
Liberal/libertario, crítico, con datos.
```

No debe ser:

```txt
- conspiranoico;
- insultante;
- sin fuentes;
- clickbait falso;
- genérico.
```

Debe poder usar búsqueda/web/fuentes si el modelo elegido lo permite a coste razonable.

Requisito futuro:

```txt
Caption con trazabilidad de fuentes.
```

## 15.1 Reescritura con instrucciones

El dashboard debe tener una caja:

```txt
"Instrucciones para la IA"
```

Ejemplos:

```txt
- Hazlo más mordaz.
- Añade enfoque fiscal.
- Reduce tono partidista.
- Cita datos sobre deuda pública.
- Hazlo más apto para YouTube Shorts.
```

La IA debe regenerar:

```txt
- headline
- subhead
- caption
```

sin regenerar todo el vídeo salvo que sea necesario.

---

# 16. Hashtags

Decisión provisional:

```txt
Mezcla de hashtags fijos + IA.
```

Hashtags fijos configurables:

```txt
#Economia
#Politica
#España
#Libertad
#Actualidad
```

IA puede añadir hashtags específicos según tema.

Debe evitar spam.

---

# 17. Publishing targets

## Tier 1 MVP

```txt
Instagram Reels
YouTube Shorts
```

## Tier 2

```txt
Instagram Stories
X reposting
```

## Tier 3

```txt
TikTok
Instagram Feed
```

El MVP debe centrarse en Tier 1.

---

# 18. Publishing architecture

Economica News no debe duplicar lógica de publicación.

Responsabilidad:

```txt
Economica News:
- descubre candidatos;
- genera assets;
- prepara metadata;
- manda payload.

CentralPublishingHub:
- publica en plataformas;
- maneja tokens;
- maneja APIs;
- maneja hosting temporal;
- maneja errores por plataforma.
```

## 18.1 Targets

Targets conocidos:

```txt
instagram_reel
instagram_story
instagram_feed
youtube_shorts
```

## 18.2 Payload base

```json
{
  "account_id": "economica_news",
  "video_path": "C:/path/to/video.mp4",
  "video_url": null,
  "caption": "...",
  "title": "...",
  "targets": ["instagram_reel", "youtube_shorts"],
  "publish_mode": "scheduled",
  "scheduled_at": "2026-05-13T18:00:00Z",
  "platforms": ["instagram_reel", "youtube_shorts"],
  "shorts_title": "..."
}
```

## 18.3 Instagram/Catbox note

Históricamente se identificó que Meta/Instagram puede necesitar URLs públicas temporales para media ingestion.

Nota preservada:

```txt
Catbox temporary public URL was considered/practically useful for Meta media ingestion.
```

Pero decisión arquitectónica:

```txt
Temporary hosting belongs in CentralPublishingHub, not Economica News.
```

Economica News no debe subir directamente a Catbox en el flujo principal salvo emergencia/prototipo explícito.

---

# 19. Scheduling

El usuario quiere cola programada, no publicación directa inmediata.

MVP:

```txt
Cola FIFO que publica cada X minutos.
```

Configuración inicial sugerida:

```txt
publish_interval_minutes: 30
```

Futuro:

```txt
- horarios fijos;
- IA decide mejor horario;
- calendario editorial;
- rate limits por plataforma.
```

Flujo:

```txt
approved → queued → scheduled → publishing → published/failed
```

---

# 20. Render local

Render debe ocurrir localmente.

Razón:

```txt
- control;
- coste bajo;
- acceso a archivos;
- posible uso de GPU local;
- no depender de SaaS de vídeo.
```

El render service puede ser interno al proyecto o módulo separado.

MVP técnico recomendado:

```txt
Local Render Engine
```

No hace falta microservicio al principio.

Futuro:

```txt
Dedicated Render Service
```

---

# 21. Almacenamiento

Decisión técnica recomendada:

```txt
SQLite.
```

Razón:

- local;
- simple;
- suficiente para cola/candidatos;
- mejor que JSON para estados;
- no requiere servidor DB.

Tablas sugeridas:

```txt
accounts
candidates
generated_assets
review_queue
publish_queue
publish_results
settings
```

No usar PostgreSQL en MVP.

---

# 22. Interfaz recomendada

Recomendación:

```txt
Web local.
```

Stack sugerido:

```txt
FastAPI backend + simple frontend.
```

Opciones frontend:

```txt
- HTML/Jinja + HTMX para rapidez.
- React si se necesita dashboard más rico.
```

Para MVP rápido:

```txt
FastAPI + Jinja/HTMX
```

Razón:

- dashboard grid más cómodo;
- previews fáciles;
- estado persistente;
- API interna limpia;
- más mantenible que Tkinter para este caso.

---

# 23. Regla de oro

Prioridad máxima del usuario:

```txt
Que el contenido quede profesional.
```

Pero también:

```txt
No hay prisa en empezar a sacar contenido si la base es mala.
```

Orden de prioridades propuesto:

```txt
1. Contenido profesional.
2. Fácil de mantener.
3. Que funcione de forma fiable.
4. Que genere mucho contenido rápido.
```

Matiz:

Aunque el usuario eligió “throughput” antes, ahora aclara que no tiene prisa y prefiere calidad profesional. Por tanto, MVP debe evitar chapuzas visuales.

---

# 24. Qué NO construir en MVP

No construir todavía:

```txt
- editor de vídeo completo;
- multi-idioma;
- TikTok;
- Instagram Feed;
- Stories;
- X reposting;
- automatic posting sin aprobación;
- AI voice;
- TTS;
- música avanzada;
- thread support;
- paid scraper integration;
- mobile app;
- cloud SaaS;
- multi-user auth.
```

---

# 25. Riesgos principales

## 25.1 X ingestion

Mayor riesgo del proyecto.

Problemas observados:

```txt
Twikit:
- Couldn't get KEY_BYTE indices
- KeyError('urls')

Nitter:
- 403
- sin resultados
- DNS

Playwright async:
- problemas Windows/event loop/subprocess
```

Decisión:

```txt
No basar el producto en Twikit/Nitter.
```

Investigar seriamente:

```txt
- Playwright sync + persistent context;
- DOM scraping visible;
- login manual;
- bajo volumen;
- capturas/screenshot fallback;
- posible API oficial o scraper pago si todo falla.
```

## 25.2 Rights/reuse

El producto reutiliza contenido de terceros.

Decisión pendiente:

```txt
Cómo mostrar atribución.
```

Asunción provisional:

```txt
Guardar siempre fuente original internamente.
Mostrar @usuario de forma discreta en el vídeo o caption si no perjudica el formato.
```

## 25.3 Publishing APIs

Meta/YouTube pueden fallar por:

```txt
- tokens;
- permisos;
- URLs públicas;
- processing delays;
- rate limits;
- OAuth.
```

Mitigación:

```txt
CentralPublishingHub owns platform-specific complexity.
```

---

# 26. Fases recomendadas

## Phase 0 — Product skeleton after wipeout

Objetivo:

```txt
Crear repo limpio con blueprint, arquitectura mínima y decisions log.
```

Tickets:

```txt
EN-000 Create PRODUCT_BLUEPRINT.md
EN-001 Create clean repo skeleton
EN-002 Create architecture decision records folder
EN-003 Define config format
EN-004 Define database schema draft
```

---

## Phase 1 — X ingestion proof of concept

Objetivo:

```txt
Demostrar que podemos obtener tweets reales de cuentas configuradas.
```

NO hacer render todavía.

Tickets:

```txt
EN-010 Implement account config file
EN-011 Implement Playwright sync persistent browser profile
EN-012 Add first-run login flow for X
EN-013 Extract latest posts from one X profile
EN-014 Extract media URLs or screenshots
EN-015 Extract engagement metrics from visible DOM
EN-016 Store raw candidates in SQLite
EN-017 Add candidate scoring function
EN-018 Add scan last 24h command
EN-019 Add debug artifacts folder
EN-020 Add ingestion reliability report
```

Exit criteria:

```txt
Given 5 configured accounts,
when scan runs,
then app stores at least some recent posts with URL/text/media/metrics.
```

---

## Phase 2 — Candidate dashboard

Objetivo:

```txt
Mostrar candidatos en grid local.
```

Tickets:

```txt
EN-030 Create FastAPI app shell
EN-031 Create SQLite repository layer
EN-032 Create candidates API
EN-033 Create dashboard grid view
EN-034 Add candidate detail page
EN-035 Add approve/reject actions
EN-036 Add status transitions
EN-037 Add scan button
EN-038 Add basic filters/sorting
```

Exit criteria:

```txt
User can scan X accounts and approve/reject candidates from dashboard.
```

---

## Phase 3 — AI metadata generation

Objetivo:

```txt
Generar headline, subhead, caption y hashtags.
```

Tickets:

```txt
EN-040 Define AI metadata schema
EN-041 Implement CentralAIService client
EN-042 Generate headline/subhead/caption for candidate
EN-043 Add libertarian/rigurosity prompt
EN-044 Add fact-check/source-aware prompt mode
EN-045 Add regenerate with user instruction
EN-046 Store generated metadata
EN-047 Display metadata in dashboard
```

Exit criteria:

```txt
Approved candidate can receive usable headline/subhead/caption.
```

---

## Phase 4 — Render engine MVP

Objetivo:

```txt
Crear vídeo vertical breaking-news style.
```

Tickets:

```txt
EN-050 Define visual template spec
EN-051 Create branding assets folder
EN-052 Implement screenshot/image template render
EN-053 Implement video media template render
EN-054 Add headline box overlay
EN-055 Add subtitle overlay
EN-056 Add Economica News logo/watermark
EN-057 Export MP4 9:16
EN-058 Store generated asset path
EN-059 Add render preview to dashboard
```

Exit criteria:

```txt
System generates professional-looking vertical MP4 for image/video candidate.
```

---

## Phase 5 — Review queue

Objetivo:

```txt
Approve generated videos into queue.
```

Tickets:

```txt
EN-060 Add generated preview status
EN-061 Add approve generated asset
EN-062 Add reject generated asset
EN-063 Add regenerate metadata with instruction
EN-064 Add queue table
EN-065 Add queue dashboard
```

Exit criteria:

```txt
User can approve generated piece into scheduled queue.
```

---

## Phase 6 — Scheduled publishing via CentralPublishingHub

Objetivo:

```txt
Publicar Instagram Reels y YouTube Shorts.
```

Tickets:

```txt
EN-070 Implement CentralPublishingHub client
EN-071 Build publish payload for instagram_reel
EN-072 Build publish payload for youtube_shorts
EN-073 Add scheduled queue worker
EN-074 Add FIFO every X minutes config
EN-075 Add publish result handling
EN-076 Add retry/failure states
EN-077 Add publishing logs
EN-078 Add manual publish-now override
```

Exit criteria:

```txt
Approved piece is published through CentralPublishingHub to Instagram Reels and YouTube Shorts.
```

---

## Phase 7 — Operational launcher

Objetivo:

```txt
Arranque local claro.
```

Tickets:

```txt
EN-080 Add EconomicaNews.bat
EN-081 Add start script
EN-082 Add diagnose script
EN-083 Check CentralAIService
EN-084 Check CentralPublishingHub
EN-085 Check browser profile availability
EN-086 Document local setup
```

Exit criteria:

```txt
User can start app by double-clicking launcher.
```

---

## Phase 8 — Hardening

Objetivo:

```txt
Dejarlo usable a diario.
```

Tickets:

```txt
EN-090 Add CI
EN-091 Add secret scan
EN-092 Add backup/export SQLite
EN-093 Add structured logs
EN-094 Add error dashboard
EN-095 Add rate limits for X scanning
EN-096 Add duplicate detection
EN-097 Add source attribution policy
EN-098 Add config validation
```

---

# 27. Proposed clean architecture

```txt
economica-news/
  PRODUCT_BLUEPRINT.md
  README.md

  app/
    main.py
    settings.py

    discovery/
      x_browser_source.py
      scoring.py
      models.py

    ai/
      metadata_generator.py
      prompts.py

    render/
      templates/
      renderer.py
      subtitles.py

    publishing/
      payloads.py
      hub_client.py
      queue.py

    storage/
      db.py
      repositories.py
      migrations/

    web/
      routes.py
      templates/
      static/

  config/
    accounts.yaml
    settings.example.yaml

  runtime/
    browser_profile/
    debug/
    output/
    app.db

  scripts/
    start.ps1
    diagnose.ps1

  tests/
```

Do not commit:

```txt
runtime/
.env
browser profile
cookies
tokens
output videos
```

---

# 28. Immediate next step

After project wipeout is merged, next PR should NOT implement the whole MVP.

Next PR should be:

```txt
EN-000 / EN-001 — Create clean skeleton from blueprint.
```

Scope:

```txt
- PRODUCT_BLUEPRINT.md
- README
- app package skeleton
- config example
- empty tests
- CI
```

No scraping yet.

Then next:

```txt
EN-010 — X ingestion proof of concept.
```

---

# 29. Summary

Economica News must become a semi-automatic, professional content factory.

MVP success means:

```txt
The system can automatically discover viral X posts from configured accounts, generate professional vertical breaking-news style pieces, let the user approve them, and schedule them for Instagram Reels and YouTube Shorts.
```

The hardest part is X ingestion.

Do not hide that risk.

Build in phases, starting with proof that X ingestion works.
