# Roadmap

## Phase 1 — KCNA question bank (current)
- [x] YAML content format and validator
- [x] Practice mode with spaced repetition (Leitner)
- [x] Mock exam weighted by official domains, timer, per-domain report
- [x] Glossary with clickable terms and on-demand Spanish
- [x] Dashboard: accuracy per domain, due reviews, Spanish usage
- [x] Grow the bank to 150 original questions (66 / 42 / 24 / 18 per domain)
- [x] Explain why each wrong option is wrong (`why` on every distractor)
- [x] English everywhere: exam-English vocabulary, key-word bar, text to speech, vocabulary
      practice with spaced repetition (KCNA and CKA labs)
- [x] Second review pass of all questions against current docs (November 2026: 1072 questions, 86 fixed,
      every docs link checked with `scripts/check_links.py`)
- [x] Reading-speed indicator per question (words per minute) and pace vs. the real exam's time per question

## Phase 2 — Hands-on labs (CKA first)
- [x] Lab environments with Docker Compose: k3s 1-node and 2-node + toolbox (`labs/`)
- [x] Backend endpoints to start, reset, stop and check a lab
- [x] Task format: `content/cka/tasks/<id>.yaml` (task, setup, checks, solution)
- [x] 45 CKA tasks with checkers that inspect real cluster state (incl. Helm, Kustomize, CSR, Ingress, Gateway API)
- [x] Web terminal in the browser (ttyd) and exam-style timer
- [x] Gateway API tasks (k3s with Traefik as the Gateway controller)
- [x] kubeadm environment (kind node images, SSH to the nodes): etcd backup and restore, kubeadm upgrade 1.36 → 1.37, kubeadm join
- [x] Multi-task mock exam (several tasks, one cluster, one timer, partial credit)

## Phase 2b — More certifications (Cloud Engineer / DevOps)
- [x] App supports several certifications (selector, per-exam progress, per-track labs and mocks)
- [x] Terraform Associate 004: 152 questions over the 8 official objectives + 17 labs on LocalStack
- [x] KCSA: 120 questions over the 6 official domains
- [x] CKAD: 27 labs over the 5 official domains + mock exam
- [x] CKS: 24 labs over the 6 official domains + mock exam (audit-log environment)
- [x] Labs on Kubernetes 1.37 (same version as the CKA/CKAD/CKS curriculum)
- [ ] CKS topics that need a real node: AppArmor, Falco, kube-bench, API server flags
- [x] Terraform labs for `depends_on` / `create_before_destroy` (state and plan-JSON checks)
- [x] Platform: any lab environment (Linux, Docker, Gitea, Prometheus…), per-environment ready check,
      mock exams without Kubernetes, glossary terms scoped to certifications
- [x] DevOps job interviews in English: 135 questions in 11 categories, self-check key points,
      spoken model answers, speech to text, timed mock interviews, interview phrases
- [x] LFCS: 80 concept questions + 30 labs on Ubuntu servers with systemd + mock exam
- [x] Docker DCA: 120 questions + 23 labs (Docker in Docker, Swarm, registry) + mock exam
- [x] GitHub Actions GH-200: 100 questions + labs on Gitea Actions + mock exam
- [x] Argo CAPA: 100 questions + 14 labs (Argo CD, Rollouts, Workflows) + mock exam
- [x] Prometheus PCA: 100 questions + 19 labs (Prometheus, Alertmanager, exporters) + mock exam
- [x] AWS SAA-C03: 150 questions + 12 AWS CLI labs on LocalStack + mock exam
- [x] LFCS storage labs with LVM and swap (LVM devices file + `lab-teardown`, so nothing stays in the shared kernel)
- [x] Argo Events labs (JetStream EventBus, webhook EventSource, Sensor that submits a Workflow)
- [x] GH-200 OIDC lab (workflow permissions + IAM trust policy tested with example tokens; Gitea cannot issue OIDC tokens)
- [x] Grafana labs: data source provisioning, dashboards with the HTTP API and as code with a variable
- [x] HashiCorp Vault Associate (003): 64 questions + 12 labs on a real Vault 1.19 server (Shamir seal, PostgreSQL)
- [x] Istio ICA: 53 concept questions + 16 labs on k3s with Istio 1.31 (install, traffic, security, troubleshooting) + mock exam
- [x] Azure AZ-104: 70 questions; Google Cloud ACE: 65 questions (no local labs: real clouds cannot be emulated well)
- [ ] Later: eJPT and OSCP-style pentesting tracks, Ansible (RHCE)
- [x] Real exam facts per certification (questions, time, cost, prerequisites, validity)
- [x] Study plan by exam date (work for today, phases, pace) and readiness score (`backend/app/plan.py`)
- [x] Certification path map (KCNA → CKA → CKS, Kubestronaut) with expiry reminders
- [x] Exam-like mock details: DOMC questions for DCA, AWS ESL +30 minutes, allowed docs in lab mock exams

## Sharing and installing
- [x] Install guide for people and AI assistants (`INSTALL.md`), CI runs the Docker install
- [x] Ready-made lab images on GHCR (amd64 + arm64), built locally only when missing
- [x] Export / import of all progress (My path → Your data), with a backup before every import
- [x] README screenshots and a lab GIF (`scripts/screenshots/`)

- [x] Installable app (PWA): manifest, icons, offline shell; phone access over the LAN or https

## Phase 3 — AI tutor and English feedback (optional, needs API key)
- [x] AI feedback on interview answers: key points, English corrections, an improved answer
- [x] "Explain more" button: LLM follow-up on top of the written `why`, plus your own question
- [x] "Explain it" exercise: write why an answer is right; the LLM corrects grammar and technical accuracy

## Phase 4 — More exams
- [ ] Full mock exams
- [x] Mock exam history: score chart and per-domain trend (Plan tab)
