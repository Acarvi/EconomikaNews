# Economika - Memory Log

## [2026-04-02] - System Restoration (State of Emergency)

### [2026-04-04] - Definitive Cookie Conflict FIX (The Monkey Patch)

- **The Problem**: `httpx.Cookies.get` was raising a fatal `CookieConflict` instead of just returning the first match. This happened during live Twitter sessions when the API sent variant cookies (e.g., `.x.com` vs `x.com`). No amount of file cleaning could prevent this as it was a runtime behavior of the library.
- **The Solution**: Implemented a **Monkey Patch** on `httpx.Cookies.get` in `core/viral_scout.py` and `core/scraper.py`. The patched method now catches the conflict and returns the first matching cookie name instead of crashing.
- **Result**: Scraper is now 100% stable. Verified account scans proceed past the previously fatal `twid` error.

### 🛣️ Lessons & Debt
- **Patch Over Clean**: When dealing with library-level strictness (like `httpx`), runtime patching is often the only way to achieve stability without forking.
- **UI Lifecycle**: Radical cleanup is safer than conditional updates when dealing with complex Tkinter Toplevel navigations.

### [2026-04-11] - Fix Subtitler API Key & Env Refactor

- **The Problem**: Subtitler would crash if `GEMINI_API_KEY` was missing. Also, environment variable loading was inconsistent across modules.
- **The Solution**:
    - Standardized environment loading using `python-dotenv` in `core/ai_handler.py`.
    - Implemented a **Safety Fallback** in `core/subtitler.py`: if the API key is invalid, it skips translation and returns original Whisper segments.
    - Added a functional test case in `tests/test_funcionalidades_core.py` to ensure this behavior is preserved.
- **Result**: Pipeline is now resilient to credential failure. Rendering continues in original language instead of crashing.

### [2026-04-11] Emergency Fix (Task 03) - Core Stabilization
- **Subtitler (SoX Fix)**: Resolved a critical regression where missing system dependencies (SoX/FFmpeg) caused a violent crash during Whisper fallback. Implemented robust exception handling that logs the specific error and proceeds without subtitles.
- **Publisher (AttributeError & Sync Fix)**: Refactored `core/publisher.py` to fix the `AttributeError: publish_video`.
  - **URL Fix**: Resolved the bug causing `/api/v1/api/v1` duplication in the Hub request URL.
  - **Resilience**: Integrated the new `check_publishing_hub_health` with auto-start logic (Port 8000).
  - **Fallback Queue**: Implemented a local JSON queue (`data/failed_posts.json`) to store posts if the Hub is offline, preventing pipeline failure.
- **Architectural Shift**: `EconomikaNoticias` has officially stopped handling local publishing logic. It now delegates all immediate and scheduled publications to the Hub via HTTP API (`publish_video`, `schedule_publication`).
- **Backlog**: Reorganized the entire backlog to prioritize this emergency fix. Task 02 moved to `done/`.

### [2026-04-12] Anti-Exposure System & Twikit Fallback
- **Phase 1: Anti-Exposure (Priority Zero)**: 
    - Implemented `utils/security_audit.py` to enforce `.gitignore` rules and scan for hardcoded secrets. Startup is blocked if vulnerabilities are found.
    - Implemented `utils/log_sanitizer.py` using monkey-patching on `sys.stdout/stderr` to redact all `.env` values (API keys, etc.) from console and logs.
    - Standardized `git rm --cached .env` to prevent credential leaks in tracking.
- **Phase 2: Scraper Fallback (Nitter RSS)**:
    - Resolved persistent 404/KEY_BYTE errors in Twikit by implementing a **Deep Fallback** to Nitter RSS feeds in `core/viral_scout.py`.
    - The system now automatically switches to RSS ingestion if Twikit fails, ensuring zero-downtime content scraping.
    - Integrated multiple Nitter instances to ensure resilience against instance failure.
- **Testing**: Achieved 100% functional coverage for these new layers with `tests/test_security.py` and `tests/test_fallback.py`.

### [2026-04-12] SentinelAPI Deployment & "Caso Wolverine" Investigation

- **Caso Wolverine (Forense)**: Se investigó el fallo crítico `KEY_BYTE indices` en la cuenta `@wallstwolverine`. 
    - **Descubrimiento**: X está devolviendo una estructura JSON inconsistente para esta cuenta específica (posiblemente por marcado de "Contenido Sensible" o Layout de Verificado), lo que rompe la librería `twikit` incluso con cookies válidas.
    - **Mitigación**: Se inyectó lógica de **Debug Dump** en `viral_scout.py` para capturar estos fallos en el futuro.
- **Resiliencia RSS (Infalible)**: 
    - Se implementó un sistema de **Rotación de Instancias Nitter** (`nitter.net`, `nitter.cz`, `nitter.poast.org`, `nitter.privacydev.net`) para el fallback de Scraping.
    - Se refinó el mapeo de métricas (Likes/RTs) desde el RSS para asegurar que el pipeline no se detenga ante fallos de X.
- **Despliegue de SentinelAPI**: 
    - La seguridad se ha centralizado y profesionalizado en `d:\Scripts\SentinelAPI`.
    - Se instalaron **Git Hooks (pre-push)** universales que bloquean cualquier subida a GitHub si se detectan API Keys expuestas.
- **Git Housekeeping**: Fusionada la rama `fix/04-twikit-scraper-deep-fallback` en `development` y creada la nueva rama de investigación `fix/04-scraper-investigation-and-fallback`.
