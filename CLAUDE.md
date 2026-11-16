# CLAUDE.md

Study environment for Cloud Engineer / DevOps certifications: KCNA, KCSA, CKA, CKAD, CKS,
HashiCorp Terraform Associate, LFCS, Docker DCA, GitHub Actions GH-200, Argo CAPA, Prometheus PCA,
AWS SAA-C03, plus DevOps job interview practice in English. Owner studies in
Spanish but all study content must be in **simple, clear English**.

## Commands
- Validate content: `python scripts/validate_content.py`
- Exam facts age: `python scripts/check_facts.py` (`--online` also opens the official pages)
- Backend tests: `cd backend && pytest -q`
- Run backend: `cd backend && uvicorn app.main:app --reload`
- Run frontend: `cd frontend && npm run dev` (proxies `/api` to :8000)
- Everything: `docker compose up -d --build` (install guide for people and AI assistants: `INSTALL.md`)
- Get all lab images ahead of time: `sh scripts/build_labs.sh [env…]` (downloads ready-made ones from
  `LAB_IMAGE_REGISTRY`; empty value = build locally, needed when you edit `labs/`)
- Verify lab tasks on real environments (Docker): `python scripts/verify_labs.py tasks <ids…>` or
  `--track <id>`; whole mock exam: `python scripts/verify_labs.py mock <track>`
- Debug a lab by hand: `docker compose -p k8slab -f labs/envs/single-node/compose.yaml up -d --build`

## Conventions
- Content lives in `content/` as YAML; never hardcode questions in code.
  Format: `docs/CONTENT_FORMAT.md`. Question ids: `<exam>-<domain short>-<NNN>`.
- Questions must be **original**, based on the public curriculum and official docs.
  Never reproduce real exam questions.
- Every question: explanation + at least one official docs link + glossary ids.
  Add new glossary terms to `content/glossary.yaml` (English definition + `es`).
- Backend: FastAPI app factory `create_app()` in `backend/app/main.py`; SQLite via `app/db.py`.
- Certifications offered: `content/certifications.yaml` (multiple-choice `exam` and/or lab `track`).
- Lab tasks: `content/<track>/tasks/<id>.yaml` (format in `docs/CONTENT_FORMAT.md`), environments in
  `labs/envs/`. Checks inspect real cluster state; verify new tasks on a real lab (fail before, pass after).
- Interview questions: `content/interviews/<category>.yaml` (key points + spoken model answer).
- Glossary terms for common words in one area ("workflow", "bucket") set `certs:` so they are
  only highlighted in that certification.
- Study plan and readiness score: pure functions in `backend/app/plan.py` (progress is read in
  `main.py` `parts_for`); keep the formulas explained in the README.
- AI features must stay optional: the app must work with no API key (`app/ai.py`, off without
  `ANTHROPIC_API_KEY`; tests use a fake client and never call the real API).
- When you change exam facts in `certifications.yaml`, set `official.checked` to the current month.
- Lab compose files never bind-mount repo files (the backend may run in Docker); bake them into an image.
- Keep `INSTALL.md` working when you change ports, services or requirements (CI runs the Docker install).
- Lab containers that create kernel objects (loop devices, LVM, swap) need a `lab-teardown` script.
- Run the validator and tests before finishing any change.
