# CLAUDE.md

Study environment for Kubernetes certifications (KCNA first). Owner studies in
Spanish but all study content must be in **simple, clear English**.

## Commands
- Validate content: `python scripts/validate_content.py`
- Backend tests: `cd backend && pytest -q`
- Run backend: `cd backend && uvicorn app.main:app --reload`
- Run frontend: `cd frontend && npm run dev` (proxies `/api` to :8000)
- Everything: `docker compose up --build`

## Conventions
- Content lives in `content/` as YAML; never hardcode questions in code.
  Format: `docs/CONTENT_FORMAT.md`. Question ids: `<exam>-<domain short>-<NNN>`.
- Questions must be **original**, based on the public curriculum and official docs.
  Never reproduce real exam questions.
- Every question: explanation + at least one official docs link + glossary ids.
  Add new glossary terms to `content/glossary.yaml` (English definition + `es`).
- Backend: FastAPI app factory `create_app()` in `backend/app/main.py`; SQLite via `app/db.py`.
- AI features must stay optional: the app must work with no API key.
- Run the validator and tests before finishing any change.
