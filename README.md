# k8s-study-lab

A local study environment for Kubernetes certifications, built to practise
**the exam content and technical English at the same time**.

Phase 1 covers **KCNA** (Kubernetes and Cloud Native Associate):

- **Practice** with spaced repetition (Leitner boxes): questions you miss come back sooner.
  When you pick a wrong option, the app tells you **why that option is wrong**, then explains the right answer.
- **Mock exams** that follow the official domain weights, with a timer and a per-domain report.
- **Built-in English support**, everywhere (KCNA questions, CKA labs and the mock exam):
  - technical terms (blue, dashed) and everyday exam words such as *ensure*, *by default*
    or *eventually* (amber, dotted) are clickable: simple English definition, example,
    pronunciation, and Spanish only on demand;
  - an **English help** bar under every question and task with its key words and a
    🔊 *Listen* / *Slow* button (US English voice of your browser);
  - an **English** tab to practise those words with spaced repetition; the words you
    looked up most come first;
  - the app counts lookups, translations and listens, so you can watch your need for
    Spanish go down.

**Hands-on labs (CKA)**: choose a task and a real Kubernetes cluster (k3s) starts in
Docker, with a terminal **inside the browser**. Solve it with `kubectl`, press
*Check my work* and the app inspects the real cluster state. 38 tasks across the five
CKA domains (troubleshooting, cluster architecture, networking, workloads, storage —
including Helm, Kustomize, RBAC, certificates, NetworkPolicies and StatefulSets),
on 1-node or 2-node clusters, with an exam-style timer and solutions.
**Mock exam**: 5, 10 or 15 tasks in one cluster with one countdown, graded at the end
with partial credit and the 66% pass mark, plus a full review with solutions. See [labs/README.md](labs/README.md).

Everything runs on your machine. Your progress is stored in a local SQLite file (`data/`).

## Quick start

```bash
cp .env.example .env        # optional
docker compose up --build
```

Open http://localhost:5173. The API runs on http://localhost:8000 (docs at `/docs`).

### Without Docker

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# frontend (another terminal)
cd frontend
npm install
npm run dev
```

## Project layout

```
backend/     FastAPI API, SQLite progress, spaced repetition
frontend/    React (Vite) UI
content/     Questions, glossary and lab tasks as YAML  ← contributions welcome
labs/        Docker Compose lab environments (k3s cluster + web terminal)
scripts/     validate_content.py
docs/        CONTENT_FORMAT.md, ROADMAP.md
```

## Adding questions

See [docs/CONTENT_FORMAT.md](docs/CONTENT_FORMAT.md), then run:

```bash
python scripts/validate_content.py
cd backend && pytest -q
```

**All questions must be original.** CNCF exams are covered by a confidentiality
agreement; never add questions remembered from a real exam.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

## License

Code: [MIT](LICENSE). Content in `content/`: [CC BY-SA 4.0](content/LICENSE).

This project is not affiliated with the CNCF or the Linux Foundation.
Kubernetes is a registered trademark of The Linux Foundation.
