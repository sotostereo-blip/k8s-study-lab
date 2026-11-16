# Hands-on lab environments

Each lab runs in Docker: a few containers started with Docker Compose plus a **toolbox**
container with the tools and a web terminal (ttyd). The app embeds that terminal, so you
solve tasks in the browser, like in the real exam.

```
labs/
├── toolbox/              # image: kubectl 1.37, helm, trivy, kube-linter, jq, ttyd (web terminal)
├── k3s-gateway/          # k3s with Traefik's Gateway API provider on ports 80/443 (CKA Gateway API)
├── kubeadm-node/, toolbox-kubeadm/  # kind node image + sshd, etcdctl, local apt repo with 1.37 packages; terminal with ssh
├── toolbox-terraform/    # image: terraform 1.12, AWS CLI, providers mirrored offline
├── toolbox-linux/        # image: Ubuntu 24.04 with systemd, sshd and admin tools (LFCS)
├── toolbox-docker/, dind/            # Docker CLI + a Docker-in-Docker engine with preloaded images (DCA)
├── toolbox-gitea/, gitea-runner/, gitea-server/  # git + Gitea API helpers, act_runner, Gitea (GH-200)
├── toolbox-prometheus/, prometheus-apps/   # promtool, amtool; demo apps and an alert webhook (PCA)
├── argocd-k3s/, argocd-toolbox/, argocd-git/  # k3s with Argo images preloaded, argocd/argo CLIs, Git server (CAPA)
├── toolbox-aws/          # AWS CLI for LocalStack (AWS SAA)
└── envs/
    ├── single-node/      # k3s v1.37: controlplane only            (CKA, CKAD)
    ├── two-node/         # k3s v1.37: controlplane + node01        (CKA scheduling, drain, taints)
    ├── gateway/          # k3s v1.37 + Gateway API (Traefik)       (CKA Gateway API)
    ├── kubeadm/          # kubeadm v1.36: controlplane + node01 (not joined)  (CKA etcd, upgrade, join)
    ├── secure-node/      # k3s v1.37 with API audit logging        (CKS)
    ├── argocd/           # k3s v1.37 + Argo CD, Rollouts, Workflows + a Git server (CAPA)
    ├── terraform/        # LocalStack (free AWS emulator) + terraform (Terraform labs)
    ├── aws/              # LocalStack with 13 AWS services + AWS CLI (AWS SAA)
    ├── linux/            # two Ubuntu servers with systemd and SSH (LFCS)
    ├── docker/           # Docker Engine 29 (dind) + local registry (DCA)
    ├── gitea/            # Gitea with Actions + a runner (GH-200)
    └── prometheus/       # Prometheus, Alertmanager, Grafana, node-exporter, Pushgateway, demo apps (PCA)
```

Rules for every environment: the service that runs the terminal is called `toolbox`, only it
publishes a host port (`127.0.0.1:${TERMINAL_PORT:-7681}`), and environments without
Kubernetes ship a `lab-ready` script that the app runs until the lab is usable.
Loop devices, LVM volumes and swap belong to the Docker host's kernel, not to a container, so a
toolbox that lets tasks create them ships a `lab-teardown` script (see `toolbox-linux/`): the app
and `scripts/verify_labs.py` run it in every lab container before `docker compose down`.
The `argocd` toolbox is built FROM `k8s-study-lab/toolbox:3`; the app and `scripts/verify_labs.py`
build such base images first when they are missing (`base_images()` in `backend/app/labs.py`).
Compose files must not bind-mount files from the repository (`./file:/path`): the backend may run in
Docker and use the host engine, where those paths do not exist. Bake files into a lab image instead
(see `gitea-server/`). To build every lab image ahead of time: `sh scripts/build_labs.sh`.

**Ready-made images.** `.github/workflows/lab-images.yml` publishes every lab image (amd64 + arm64) to
`ghcr.io/<owner>/k8s-study-lab/<name>:<tag>` when `labs/` changes on `main`, only while the repository is
public (`python scripts/lab_images.py` lists them). With `LAB_IMAGE_REGISTRY` set (the default in
`docker-compose.yml`), the backend runs `docker pull` for each image of an environment before starting it,
tags it with its local name, and builds locally only the images it could not download. When you edit a
lab image, set `LAB_IMAGE_REGISTRY=` (empty) in `.env` so your local build is used, and bump the image tag
in the compose file when the change is not compatible with older content.

The backend starts them for you when you open a lab. It runs
`docker compose -p k8slab -f labs/envs/<env>/compose.yaml up -d --build`,
waits for the nodes and/or the environment's `ready` command, runs the task `setup`, and later the task `checks`.
Only one lab runs at a time and every start begins with a clean environment.

Verify tasks on real environments (also several at once, with different projects/ports):

```bash
python scripts/verify_labs.py tasks --track ckad --project verify-ckad --port 7702
python scripts/verify_labs.py mock cks --project verify-cks --port 7703
```

Requirements: Docker Desktop running, about 2 GB of free memory (3 GB for the Argo CD lab),
and internet the first time (images such as `rancher/k3s`, `localstack/localstack`, `gitea/gitea`,
`prom/prometheus`, `docker:dind`, `ubuntu`). Building all lab images takes several GB of disk.
`scripts/verify_labs.py` runs at most 2 verifications at once (`VERIFY_SLOTS`) to protect memory.
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
