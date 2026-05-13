# Launcher And Local Ops

The previous implementation had:

- `EconomikaNoticias.bat`
- `scripts/start_economika.ps1`
- `scripts/diagnose_mvp.ps1`

The launcher checked Python and local services before opening the GUI.

The startup script checked:

- CentralAIService at `http://localhost:8080/health`
- CentralPublishingHub at `http://localhost:8000/health`, `/docs`, or `/`

This local launcher idea can be reused later, but no active runtime is preserved after the reset.

