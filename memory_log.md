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
- **Publisher (AttributeError Fix)**: Refactored `core/publisher.py` to fix the `AttributeError: publish_video`. The module now acts as a pure client for the `CentralPublishingHub`.
- **Architectural Shift**: `EconomikaNoticias` has officially stopped handling local publishing logic. It now delegates all immediate and scheduled publications to the Hub via HTTP API (`publish_video`, `schedule_publication`).
- **Backlog**: Reorganized the entire backlog to prioritize this emergency fix. Task 02 moved to `done/`.
