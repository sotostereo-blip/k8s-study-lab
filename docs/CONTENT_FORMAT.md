# Content format

All study content lives in `content/` as YAML, separate from the code, so anyone
can add or fix questions with a pull request.

```
content/
├── certifications.yaml         # what the app offers, in selector order
├── glossary.yaml               # shared technical glossary
├── glossary.d/<area>.yaml      # more glossary terms, one file per area (terraform, security…)
├── vocabulary.yaml             # everyday exam English
├── vocabulary.d/<area>.yaml    # more exam-English words, one file per area
├── interviews/                 # job interviews in English
│   ├── interviews.yaml         # categories
│   ├── phrases.yaml            # useful spoken phrases, in groups
│   └── <category>.yaml         # questions of one category
├── <exam>/                     # multiple-choice exam (kcna, kcsa, terraform)
│   ├── exam.yaml               # metadata, domains with weights, optional facts_note
│   └── <domain-id>.yaml        # one file per domain
└── <track>/                    # hands-on labs (cka, ckad, cks, terraform)
    ├── labs.yaml               # domains, environments, mock exam settings
    └── tasks/<id>.yaml         # one file per task
```

A folder can have both (`content/terraform/` has the question bank and the labs).

## Real exam facts (`certifications.yaml` → `official`)

Shown in the **Real exam** tab. Write what the official page says; when a number is not published
(question count, passing score), say so in the text.

```yaml
    official:
      provider: Linux Foundation / CNCF
      format: Multiple choice, online with a proctor
      questions: About 60 questions (the number is not on the official page)
      minutes: 90
      passing: 75% (reported by candidates, not on the official page)
      cost: USD 250                       # exam alone; tiles show "USD <n>" or "Varies"
      includes: [One free retake]         # what the price includes
      prerequisites: None                 # e.g. "You must pass the CKA before you can take the CKS"
      valid: 2 years
      renewal: Pass the same exam again before your certification expires.
      notes: []
      checked: "2026-11"                  # month the facts were checked
      url: https://training.linuxfoundation.org/...
```

## Glossary terms

```yaml
terms:
  - id: gha-workflow
    term: Workflow (GitHub Actions)
    match: [workflow, workflows]          # forms highlighted in the text (whole words)
    certs: [gha, interview]               # optional: only highlight in these certifications
    definition: "An automated process defined in a YAML file in .github/workflows."
    es: "Flujo de trabajo automatizado"
```

A match form may belong to one term only. Use `certs` for everyday words that mean something
special in one area, so they are not highlighted in other certifications' labs. Questions list
their own `glossary` ids, and those are always highlighted.

## Exam English (`content/vocabulary.yaml`)

Everyday (non-technical) words used in the questions and tasks that a learner may not
know. They are highlighted automatically wherever they appear.

```yaml
words:
  - id: ensure
    word: ensure
    match: [ensure, ensures, ensured, ensuring]   # forms to highlight (whole words)
    definition: "To make certain that something happens or is true."
    example: "Ensure that the Pod is running before you test the Service."
    es: "asegurar, garantizar"
```

A form may not repeat a glossary term, and every word must appear somewhere in the content
(a test checks this).

## Question

```yaml
domain: kubernetes-fundamentals     # must match a domain id in exam.yaml
questions:
  - id: kcna-fund-001               # unique: <exam>-<domain short>-<number>
    difficulty: 1                   # 1 = basic, 2 = intermediate, 3 = advanced
    type: single                    # single | multiple
    question: What is the smallest deployable unit ...?
    options:                        # 2 to 6 options, ids a..f
      - id: a
        text: "A container"         # always quote
        why: "Containers run inside Pods. Kubernetes never schedules a container on its own."
      - id: b
        text: "A Pod"               # correct options do not need 'why'

    answer: [b]                     # list; exactly 1 id for single, 2+ for multiple
    explanation: |                  # why the answer is right (and others wrong)
      ...
    docs:                           # at least one link to official docs
      - https://kubernetes.io/docs/...
    glossary: [pod, container]      # ids from glossary.yaml (optional)
```

## Rules for contributors

1. **Original questions only.** Never publish questions remembered from the real
   exam. CNCF exams are covered by a confidentiality agreement. Write questions
   from the public curriculum and documentation.
2. Write in clear, simple English. The project is also for practising English.
3. Every question needs an explanation and at least one official docs link, and every
   **wrong option needs a `why`**: 1–2 sentences on what that option really is and why it
   does not fit. The app shows it when a learner picks that option.
4. Keep options similar in length and make wrong options plausible (real
   concepts used in the wrong place). The validator warns when the right answer
   is much longer than every distractor.
5. Run `python scripts/validate_content.py` before opening a pull request.

## Lab tasks (hands-on)

One file per task: `content/<exam>/tasks/<id>.yaml`. Domains and environments are
defined in `content/<exam>/labs.yaml`. Ids: `<exam>-<area>-<NNN>` (e.g. `cka-net-003`).

```yaml
id: cka-ts-001
title: Fix a Deployment that does not start
domain: troubleshooting        # a domain id from labs.yaml
difficulty: 1                  # 1-3
minutes: 5                     # target time shown by the timer
environment: single-node       # single-node | two-node (labs/envs/<name>)
setup: |                       # bash, runs once the cluster is ready (optional)
  kubectl create deployment broken-web --image=nginx:1.27-alpinee --replicas=2
task: |                        # what the student sees; supports `code`, **bold**, lists
  The Deployment `broken-web` ... Find the problem and fix it.
checks:                        # bash in the toolbox; exit code 0 = pass
  - name: Deployment `broken-web` has 2 ready replicas
    run: '[ "$(kubectl get deploy broken-web -o jsonpath="{.status.readyReplicas}")" = 2 ]'
  - name: The Deployment is still called broken-web in default
    run: kubectl get deploy broken-web
    guard: true                # already true before the task: no points, but breaking it = 0
solution: |                    # shown only when the student asks
  kubectl set image deployment/broken-web nginx=nginx:1.27-alpine
docs:
  - https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/
auto_solution: |               # optional; runnable version of `solution` for scripts/verify_labs.py
  kubectl set image deployment/broken-web nginx=nginx:1.27-alpine
mock_exam: true                # optional; false if the task changes the whole cluster
conflicts_with: []             # optional; tasks that cannot share one cluster with this one
```

Rules for tasks:

1. Checks must look at the **real cluster state**, not at the commands typed.
   Accept any valid way to solve the task.
2. Before the task is solved, at least one check must fail; after the solution,
   all must pass. Test both on a real lab before opening a pull request:
   `python scripts/verify_labs.py tasks <id>` (and `mock <track>` for mock exams).
   If `solution` has manual steps ("edit the file"), add a runnable `auto_solution`.
3. Use small public images with a fixed tag (`nginx:1.27-alpine`, `busybox:1.36`).
4. **Mock exams run many tasks in one cluster** (the track's `mock_environment`). Use object names no other task
   uses. If your task drains or taints nodes, or reuses a name, set `mock_exam: false`
   or list the other tasks in `conflicts_with` (on both tasks).
5. Checks run with `set -o pipefail`: in `cmd | grep` a failing `cmd` fails the check even
   if grep matches. Capture first: `out=$(cmd 2>&1); echo "$out" | grep -q …`. This also
   avoids leftover Pods from `kubectl run --rm -i … | grep -q` (SIGPIPE).
6. For RBAC on subresources use `kubectl auth can-i create pods --subresource=exec`
   (`pods/exec` is read as "the Pod named exec").
7. Mark with `guard: true` every check that already passes before the task is solved
   ("do not remove the taint", "the user cannot delete…"). Mock exams give partial credit
   only for the other checks, so doing nothing scores 0.

## Lab environments (`labs.yaml` → `environments`)

```yaml
intro: "a Linux server in Docker"          # optional: "Choosing a lab starts <intro> with a terminal…"
environments:
  linux:                                   # = labs/envs/linux/compose.yaml
    name: "Ubuntu 24.04 server with systemd"
    nodes: 0                               # Kubernetes nodes; 0 = no cluster
    label: "Linux"                         # short label on the lab cards
    tools: "You are root on the server"    # terminal bar text (`code` allowed)
    ready: "lab-ready"                     # optional; bash run until it exits 0 before the setup
    ready_timeout: 300                     # seconds (default 300)
```

Every environment's compose file needs a service called `toolbox` with bash: setups and checks
run there (`docker compose exec -T toolbox bash -s`) and it serves the web terminal (ttyd) on
container port 7681, published as `127.0.0.1:${TERMINAL_PORT:-7681}:7681`. No other service
may publish host ports (several labs and verifications run at the same time). With `nodes: 0`
the default `ready` command is `lab-ready`, a script the toolbox image must ship.

## Job interviews (`content/interviews/`)

```yaml
category: docker                     # a category id from interviews.yaml
questions:
  - id: iv-dkr-001                   # iv-<category short>-<NNN>
    level: junior                    # junior | mid | senior
    type: technical                  # technical | behavioral | scenario | design
    question: What is the difference between an image and a container?
    minutes: 1.5                     # target speaking time (default 2)
    tips: "Define both, then give an analogy."   # how to structure the answer (optional)
    key_points:                      # 2-8 points a good answer covers; the learner ticks them
      - An image is a read-only template made of layers
      - A container is a running instance of an image with a writable layer
    model_answer: |                  # a strong spoken answer, 60-200 words, natural spoken English
      ...
    follow_ups: [How do layers make builds faster?]
    glossary: [container-image]      # glossary ids (optional)
    docs: [https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-an-image/]
```

A learner answers aloud (or types), then sees the key points and ticks the ones they covered.
Covering 70% or more counts as a good answer for spaced repetition.

`phrases.yaml` holds groups of useful spoken English:

```yaml
groups:
  - id: time
    name: "Buy time to think"
    when: "When you need a few seconds before you answer."
    phrases:
      - { text: "Let me think about that for a second.", es: "Déjame pensarlo un segundo.", note: "" }
```
