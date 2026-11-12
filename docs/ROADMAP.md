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
- [ ] Second review pass of all questions against current docs
- [ ] Reading-speed indicator per question (words per minute)

## Phase 2 — Hands-on labs (CKA first)
- [x] Lab environments with Docker Compose: k3s 1-node and 2-node + toolbox (`labs/`)
- [x] Backend endpoints to start, reset, stop and check a lab
- [x] Task format: `content/cka/tasks/<id>.yaml` (task, setup, checks, solution)
- [x] 38 CKA tasks with checkers that inspect real cluster state (incl. Helm, Kustomize, CSR, Ingress)
- [x] Web terminal in the browser (ttyd) and exam-style timer
- [ ] More tasks: Gateway API, kubeadm upgrade, etcd backup (need a kubeadm-based environment)
- [x] Multi-task mock exam (several tasks, one cluster, one timer, partial credit)

## Phase 2b — More certifications (Cloud Engineer / DevOps)
- [x] App supports several certifications (selector, per-exam progress, per-track labs and mocks)
- [x] Terraform Associate 004: 152 questions over the 8 official objectives + 17 labs on LocalStack
- [x] KCSA: 120 questions over the 6 official domains
- [x] CKAD: 27 labs over the 5 official domains + mock exam
- [x] CKS: 24 labs over the 6 official domains + mock exam (audit-log environment)
- [x] Labs on Kubernetes 1.37 (same version as the CKA/CKAD/CKS curriculum)
- [ ] CKS topics that need a real node: AppArmor, Falco, kube-bench, API server flags
- [ ] Terraform labs for `depends_on` / `create_before_destroy` (need plan-JSON checks)
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
- [ ] LFCS storage labs with LVM and swap (need a VM; loop devices are shared in Docker Desktop)
- [ ] Argo Events labs (EventBus), Grafana dashboard labs
- [ ] Later: Ansible (RHCE), HashiCorp Vault Associate
- [x] Real exam facts per certification (questions, time, cost, prerequisites, validity)
- [x] Study plan by exam date (work for today, phases, pace) and readiness score (`backend/app/plan.py`)
- [ ] Certification path map (KCNA → CKA → CKS, Kubestronaut) with expiry reminders
- [ ] Exam-like mock details: DOMC questions for DCA, AWS ESL +30 minutes, docs-only browser in labs

## Phase 3 — AI tutor and English feedback (optional, needs API key)
- [ ] "Explain more" button: LLM follow-up on top of the written `why`
- [ ] "Explain it" exercise: write why an answer is right; the LLM corrects grammar and technical accuracy

## Phase 4 — More exams
- [ ] Full mock exams and progress history
