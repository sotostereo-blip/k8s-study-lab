# k8s-study-lab

A local study environment for **Cloud Engineer / DevOps certifications**, built to practise
**the exam content and technical English at the same time**.

| Certification | Multiple choice | Hands-on labs (terminal in the browser) |
|---|---|---|
| **KCNA** — Kubernetes and Cloud Native Associate | 150 questions | — |
| **KCSA** — Kubernetes and Cloud Native Security Associate | 120 questions | — |
| **CKA** — Certified Kubernetes Administrator | — | 38 tasks + mock exam |
| **CKAD** — Certified Kubernetes Application Developer | — | 27 tasks + mock exam |
| **CKS** — Certified Kubernetes Security Specialist | — | 24 tasks + mock exam |
| **Terraform Associate (004)** — HashiCorp | 152 questions | 17 tasks (Terraform + LocalStack) |
| **LFCS** — Linux Foundation Certified System Administrator | 80 concept questions | 30 tasks + mock exam (Ubuntu servers with systemd) |
| **DCA** — Docker Certified Associate | 120 questions | 23 tasks + mock exam (Docker Engine, Swarm, registry) |
| **GH-200** — GitHub Actions | 100 questions | 18 tasks + mock exam (Gitea Actions, GitHub compatible) |
| **CAPA** — Certified Argo Project Associate | 100 questions | 14 tasks + mock exam (Argo CD, Rollouts, Workflows) |
| **PCA** — Prometheus Certified Associate | 100 questions | 19 tasks + mock exam (Prometheus, Alertmanager, exporters) |
| **AWS SAA-C03** — Solutions Architect Associate | 150 questions | 12 tasks + mock exam (AWS CLI + LocalStack) |
| **DevOps job interviews in English** | 135 interview questions | mock interviews, useful phrases |

### The real exams (checked November 2026)

| Exam | Questions | Time | Price (USD) | Prerequisite | Valid |
|---|---|---|---|---|---|
| KCNA | ~60 multiple choice | 90 min | 250, 1 free retake | — | 2 years |
| KCSA | ~60 multiple choice | 90 min | 250, 1 free retake | — | 2 years |
| CKA | 15-20 hands-on tasks | 2 h | 445, 1 free retake | — | 2 years |
| CKAD | 15-20 hands-on tasks | 2 h | 445, 1 free retake | — | 2 years |
| CKS | 15-20 hands-on tasks | 2 h | 445, 1 free retake | passed CKA | 2 years |
| Terraform Associate (004) | ~57 multiple choice | 1 h | 70.50 + tax, no retake | — | 2 years |
| LFCS | ~17-20 hands-on tasks | 2 h | 445, 1 free retake | — | 2 years |
| DCA | 55 (13 MC + 42 DOMC) | 90 min | 199, no retake | — | 2 years |
| GH-200 | ~60-75 multiple choice | 100 min | by country (~99 in the US) | — | 2 years |
| CAPA | ~60 multiple choice | 90 min | 250, 1 free retake | — | 2 years |
| PCA | ~60 multiple choice | 90 min | 250, 1 free retake | — | 2 years |
| AWS SAA-C03 | 65 multiple choice | 130 min | 150, no retake | — | 3 years |

"~" means the provider does not publish the number. More detail (passing score, renewal, what the price
includes, official link) is in the **Real exam** tab of each certification and in `content/certifications.yaml`.
Prices change: check the official page before you pay.

Choose the certification in the selector at the top of the page.

- **Practice** with spaced repetition (Leitner boxes): questions you miss come back sooner.
  When you pick a wrong option, the app tells you **why that option is wrong**, then explains the right answer.
- **Mock exams** that follow the official domain weights, with a timer and a per-domain report.
- **Hands-on labs**: choose a task and a real environment starts in Docker with a terminal
  **inside the browser** — a Kubernetes 1.37 cluster (k3s; 1 node, 2 nodes, with API audit
  logging for CKS, or with Argo CD), Ubuntu servers with systemd, a Docker Engine, Gitea with
  Actions, a Prometheus stack, or Terraform / the AWS CLI with LocalStack, a free local AWS emulator. Solve it,
  press *Check my work*, and the app inspects the real state. Every task was verified on a real
  environment (fails before, passes after the solution). See [labs/README.md](labs/README.md).
- **Lab mock exams** (CKA, CKAD, CKS, LFCS, DCA, GH-200, CAPA, PCA, AWS): 5, 10 or 15 tasks in one lab environment with one countdown,
  graded at the end with partial credit, plus a full review with solutions.
- **Job interviews in English** (DevOps / Cloud Engineer): hear the question, answer aloud
  (speech to text in Chrome, or type), tick the key points you covered, listen to a model
  answer and the likely follow-ups. Timed **mock interviews** open with a behavioral (STAR)
  question and mix topics; the app tracks your speaking pace (words per minute) and filler
  words. A **Phrases** tab has spoken English for interviews (buying time, trade-offs,
  admitting you don't know…).
- **Built-in English support**, everywhere (questions, labs and mock exams):
  - technical terms (blue, dashed) and everyday exam words such as *ensure*, *by default*
    or *eventually* (amber, dotted) are clickable: simple English definition, example,
    pronunciation, and Spanish only on demand;
  - an **English help** bar under every question and task with its key words and a
    🔊 *Listen* / *Slow* button (US English voice of your browser);
  - an **English** tab to practise those words with spaced repetition; the words you
    looked up most come first;
  - the app counts lookups, translations and listens, so you can watch your need for
    Spanish go down.

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
