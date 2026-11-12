# Hands-on lab environments

Each lab runs a small **k3s** Kubernetes cluster in Docker plus a **toolbox**
container with `kubectl` and a web terminal (ttyd). The app embeds that terminal,
so you solve tasks in the browser, like in the real exam.

```
labs/
├── toolbox/              # image: bash, kubectl, vim, jq, ttyd (web terminal on :7681)
└── envs/
    ├── single-node/      # controlplane only
    └── two-node/         # controlplane + node01 (scheduling, drain, taints)
```

The backend starts them for you when you open a lab. It runs
`docker compose -p k8slab -f labs/envs/<env>/compose.yaml up -d --build`,
waits for the nodes, runs the task `setup`, and later the task `checks`.
Only one lab runs at a time and every start begins with a clean cluster.

Requirements: Docker Desktop running, about 2 GB of free memory, and internet the
first time (images: `rancher/k3s`, `alpine`, `nginx`, `busybox`).

Debug by hand:

```bash
docker compose -p k8slab -f labs/envs/single-node/compose.yaml up -d --build
open http://localhost:7681                     # the web terminal
docker compose -p k8slab down -v               # remove everything
```

Change the terminal port with `LAB_TERMINAL_PORT` (and `LAB_TERMINAL_URL`) in `.env`.
Tasks live in `content/cka/tasks/` — see `docs/CONTENT_FORMAT.md`.
