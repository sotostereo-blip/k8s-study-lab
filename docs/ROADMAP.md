# Roadmap

## Phase 1 — KCNA question bank (current)
- [x] YAML content format and validator
- [x] Practice mode with spaced repetition (Leitner)
- [x] Mock exam weighted by official domains, timer, per-domain report
- [x] Glossary with clickable terms and on-demand Spanish
- [x] Dashboard: accuracy per domain, due reviews, Spanish usage
- [x] Grow the bank to 150 original questions (66 / 42 / 24 / 18 per domain)
- [ ] Second review pass of all questions against current docs
- [ ] Reading-speed indicator per question (words per minute)

## Phase 2 — Hands-on labs (CKA first)
- [x] Lab environments with Docker Compose: k3s 1-node and 2-node + toolbox (`labs/`)
- [x] Backend endpoints to start, reset, stop and check a lab
- [x] Task format: `content/cka/tasks/<id>.yaml` (task, setup, checks, solution)
- [x] 17 CKA tasks with checkers that inspect real cluster state
- [x] Web terminal in the browser (ttyd) and exam-style timer
- [ ] More tasks: Ingress / Gateway API, Helm, Kustomize, kubeadm upgrade, etcd backup
- [ ] Multi-task mock exam (several tasks, one timer, weighted score)

## Phase 3 — AI tutor and English feedback (optional, needs API key)
- [ ] "Why?" button after a wrong answer, explained in simple English
- [ ] "Explain it" exercise: write why an answer is right; the LLM corrects grammar and technical accuracy

## Phase 4 — More exams
- [ ] KCSA question bank
- [ ] CKAD and CKS labs
- [ ] Full mock exams and progress history
