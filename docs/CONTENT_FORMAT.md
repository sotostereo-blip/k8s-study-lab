# Content format

All study content lives in `content/` as YAML, separate from the code, so anyone
can add or fix questions with a pull request.

```
content/
├── glossary.yaml               # shared technical glossary
└── kcna/
    ├── exam.yaml               # exam metadata and domains with weights
    └── <domain-id>.yaml        # one file per domain
```

## Question

```yaml
domain: kubernetes-fundamentals     # must match a domain id in exam.yaml
questions:
  - id: kcna-fund-001               # unique: <exam>-<domain short>-<number>
    difficulty: 1                   # 1 = basic, 2 = intermediate, 3 = advanced
    type: single                    # single | multiple
    question: What is the smallest deployable unit ...?
    options:                        # 2 to 6 options, ids a..f
      - { id: a, text: "A container" }   # always quote: commas break flow style
      - { id: b, text: "A Pod" }
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
3. Every question needs an explanation and at least one official docs link.
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
solution: |                    # shown only when the student asks
  kubectl set image deployment/broken-web nginx=nginx:1.27-alpine
docs:
  - https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/
```

Rules for tasks:

1. Checks must look at the **real cluster state**, not at the commands typed.
   Accept any valid way to solve the task.
2. Before the task is solved, at least one check must fail; after the solution,
   all must pass. Test both on a real lab before opening a pull request.
3. Use small public images with a fixed tag (`nginx:1.27-alpine`, `busybox:1.36`).
