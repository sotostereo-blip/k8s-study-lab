# Hands-on lab environments

Each lab runs a small **k3s** Kubernetes cluster in Docker plus a **toolbox**
container with `kubectl` and a web terminal (ttyd). The app embeds that terminal,
so you solve tasks in the browser, like in the real exam.

```
labs/
├── toolbox/              # image: kubectl 1.37, helm, trivy, kube-linter, jq, ttyd (web terminal)
├── toolbox-terraform/    # image: terraform 1.12, AWS CLI, providers mirrored offline
└── envs/
    ├── single-node/      # k3s v1.37: controlplane only            (CKA, CKAD)
    ├── two-node/         # k3s v1.37: controlplane + node01        (CKA scheduling, drain, taints)
    ├── secure-node/      # k3s v1.37 with API audit logging        (CKS)
    └── terraform/        # LocalStack (free AWS emulator) + terraform (Terraform labs)
```

The backend starts them for you when you open a lab. It runs
`docker compose -p k8slab -f labs/envs/<env>/compose.yaml up -d --build`,
waits for the nodes, runs the task `setup`, and later the task `checks`.
Only one lab runs at a time and every start begins with a clean environment.

Verify tasks on real environments (also several at once, with different projects/ports):

```bash
python scripts/verify_labs.py tasks --track ckad --project verify-ckad --port 7702
python scripts/verify_labs.py mock cks --project verify-cks --port 7703
```

Requirements: Docker Desktop running, about 2 GB of free memory, and internet the
first time (images: `rancher/k3s`, `localstack/localstack`, `alpine`, `nginx`, `busybox`).
The CKS terminal includes a trivy vulnerability database baked in at build time, so scans
are fast and the checker sees the same results as you.

Debug by hand:

```bash
docker compose -p k8slab -f labs/envs/single-node/compose.yaml up -d --build
open http://localhost:7681                     # the web terminal
docker compose -p k8slab down -v               # remove everything
```

Change the terminal port with `LAB_TERMINAL_PORT` (and `LAB_TERMINAL_URL`) in `.env`.
Tasks live in `content/cka/tasks/` — see `docs/CONTENT_FORMAT.md`.
