# Central Services Notes

## CentralAIService

- Path: `D:\Scripts\CentralAIService`
- Health endpoint: `http://localhost:8080/health`
- `GEMINI_API_KEY` belongs in `.env`, not Git.

## CentralPublishingHub

- Path: `D:\Scripts\CentralPublishingHub`
- Health endpoint: `http://localhost:8000/health`
- Fallback checks used previously: `http://localhost:8000/docs` and `http://localhost:8000/`

## Boundary

EconomikaNoticias should orchestrate product workflow and user review.

It should not duplicate central AI generation logic or platform publishing logic.

