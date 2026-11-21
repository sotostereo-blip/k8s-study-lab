# Install k8s-study-lab (step by step, for a person or an AI assistant)

> **For AI coding assistants (Claude Code, Codex, Cursor, Copilot…):** follow these steps in order
> on the user's machine. Run each command, check the result shown under **Expected**, and only then go to
> the next step. If a step fails, use the **Troubleshooting** table at the end before you change any file.
> Do not change application code to make the install work. Do not ask the user for an API key: the AI
> feature is optional and the app works fully without it.
> When you finish, tell the user the URL to open and which optional steps you skipped.

**Done means:** `http://localhost:5173` shows the app, and `http://localhost:5173/api/health` returns
`"status":"ok"`.

Everything runs in Docker: the web app (React), the API (FastAPI + SQLite) and the hands-on labs
(Kubernetes clusters, Linux servers, Gitea, Prometheus…), which the API starts on demand.

---

## 1. Check the requirements

| Need | Minimum | Check with |
|---|---|---|
| Docker Desktop (macOS, Windows) or Docker Engine (Linux) | Docker 24+, running | `docker info` |
| Docker Compose v2 | 2.24+ | `docker compose version` |
| git | any | `git --version` |
| Memory for Docker | 4 GB (6 GB for the Argo CD labs) | `docker info --format '{{.MemTotal}}'` (bytes) |
| Free disk | ~2 GB for the app, ~15 GB more if you use every lab | |
| Free ports | 5173 (app), 8000 (API), 7681 (lab terminal) | see below |

```bash
docker info >/dev/null && echo "docker OK"
docker compose version
git --version
```

**Expected:** `docker OK` and a Compose version of 2.24 or newer.

- If Docker is not installed: install **Docker Desktop** from https://docs.docker.com/get-docker/
  (Linux: Docker Engine + the compose plugin, https://docs.docker.com/engine/install/). Then start it.
- **Windows:** use Docker Desktop with the **WSL 2** backend and run every command below inside a WSL
  terminal (Ubuntu), with the project cloned inside the WSL file system (for example `~/k8s-study-lab`).
- **Linux:** your user must be able to run `docker` without `sudo` (`sudo usermod -aG docker $USER`,
  then log out and in).
- Apple Silicon (M1–M4) and x86_64 both work; every image is multi-architecture.

Check the ports (macOS / Linux):

```bash
for p in 5173 8000 7681; do (lsof -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1 && echo "port $p is BUSY") || echo "port $p free"; done
```

If 5173 or 8000 is busy, choose other ports in step 3 (`APP_PORT`, `API_PORT`).
Port 7681 is used by the lab terminal and must be free when a lab runs.

## 2. Get the code

```bash
git clone https://github.com/sotostereo-blip/k8s-study-lab.git
cd k8s-study-lab
```

**Expected:** a folder with `docker-compose.yml`, `backend/`, `frontend/`, `content/` and `labs/`.

## 3. Create the settings file (optional, but recommended)

```bash
cp .env.example .env
```

Every value is optional. Edit `.env` only if you need to:

| Variable | When | Example |
|---|---|---|
| `APP_PORT` | port 5173 is busy | `APP_PORT=5180` |
| `API_PORT` | port 8000 is busy | `API_PORT=8010` |
| `LAB_IMAGE_REGISTRY` | set it empty (`LAB_IMAGE_REGISTRY=`) to always build lab images locally, e.g. after editing `labs/` | |
| `ANTHROPIC_API_KEY` | the user wants AI feedback on interview answers (paid, optional) | `sk-ant-...` |

Never commit `.env` (it is already in `.gitignore`).

## 4. Start the app

```bash
docker compose up -d --build
```

The first build downloads the Python and Node images and takes 2–5 minutes.

**Expected:** at the end, `Container …-backend-1 Healthy` and `Container …-frontend-1 Started`. Check:

```bash
docker compose ps
for i in $(seq 1 30); do curl -sf http://localhost:5173/api/health && break; sleep 2; done
```

**Expected:** both services `Up` (backend `healthy`) and a JSON answer like
`{"status":"ok","questions":1072,"terms":605}` (the numbers grow as content is added).
If you changed `APP_PORT`, use that port instead of 5173.

Open **http://localhost:5173** in a browser. Choose a certification in the selector at the top.

## 5. (Optional) Prepare the hands-on labs

Nothing to do: the first time the user opens a lab, the app gets that lab's images. It downloads
**ready-made images** from GitHub (`ghcr.io`) when the project publishes them, and builds the missing ones
on this machine (a few minutes per lab, the Argo CD lab ~10). After that a lab starts in seconds.
To get them ahead of time, for example before an offline session:

```bash
sh scripts/build_labs.sh                     # every lab environment: ~15 GB
sh scripts/build_labs.sh single-node linux   # or only some (names: ls labs/envs)
```

| Environment | Used by |
|---|---|
| `single-node`, `two-node` | CKA, CKAD |
| `secure-node` | CKS |
| `argocd` | CAPA (needs 6 GB of Docker memory) |
| `istio` | Istio ICA |
| `linux` | LFCS |
| `docker` | Docker DCA |
| `gitea` | GitHub Actions GH-200 |
| `prometheus` | Prometheus PCA |
| `terraform` | Terraform Associate |
| `vault` | Vault Associate |
| `aws` | AWS SAA-C03 |

## 6. (Optional) Smoke-test one lab

This starts a small lab (two Ubuntu servers), runs its checks and stops it:

```bash
curl -s -X POST http://localhost:5173/api/labs/lfcs-ess-001/start >/dev/null
for i in $(seq 1 60); do
  s=$(curl -s http://localhost:5173/api/labs/status)
  echo "$s" | grep -q '"status":"ready"' && { echo "lab ready"; break; }
  echo "$s" | grep -q '"status":"error"' && { echo "$s"; break; }
  sleep 5
done
curl -s -o /dev/null -w "terminal: %{http_code}\n" http://localhost:7681/
curl -s -X POST http://localhost:5173/api/labs/stop >/dev/null && echo "lab stopped"
```

**Expected:** `lab ready`, `terminal: 200`, `lab stopped`.
If `lfcs-ess-001` does not exist, list the lab ids with `curl -s http://localhost:5173/api/labs?track_id=lfcs`.

## 6b. (Optional) Phone and installable app

The app is also reachable from other devices on the same network at `http://<this computer's IP>:5173`.
Installing it as an app (PWA) works on `http://localhost` and on any `https://` address. For a phone, an
easy https option is Tailscale: `tailscale serve 5173` (the Vite server accepts `*.ts.net` and `*.local`
host names; add others with `ALLOWED_HOSTS=name1,name2` in the frontend environment).

## 7. Daily use

```bash
docker compose up -d      # start (no --build needed after the first time)
docker compose down       # stop; your progress stays in ./data
git pull && docker compose up -d --build   # update to a new version
```

Progress (answers, mock exams, plan) is saved in `data/progress.db`. To keep a backup or move it to
another computer, use **My path → Your data → Download my progress**, and **Import progress…** on the other one
(the progress it replaces is saved in `data/backups/`).
New versions add database columns automatically; progress is never deleted.

To remove everything (app, lab containers and images; this deletes the progress only if you also delete `data/`):

```bash
docker compose down
docker compose -p k8slab down -v --remove-orphans
docker images --format '{{.Repository}}:{{.Tag}}' | grep '^k8s-study-lab' | xargs -r docker rmi
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker is not running | Start Docker Desktop (or `sudo systemctl start docker`) and retry |
| `port is already allocated` / `address already in use` | 5173 or 8000 is taken | Set `APP_PORT` / `API_PORT` in `.env`, then `docker compose up -d` |
| `env_file … unknown field "path"` or `required` error | Docker Compose older than 2.24 | Update Docker Desktop / the compose plugin |
| Page loads but shows errors / no certifications | backend not ready yet | Wait 20 s; check `docker compose logs backend` |
| Lab stays in *starting* for a long time the first time | images are being downloaded or built (Argo CD: up to ~10 min) | Wait; or prepare them with `sh scripts/build_labs.sh <env>` |
| Lab log says `Building … here (no ready-made image)` | the images are not published (private repository, or offline) | Nothing to fix: they are built locally once |
| Lab error `permission denied … docker.sock` (Linux) | the socket is not accessible | Check `ls -l /var/run/docker.sock`; Docker must run as root (default), not rootless |
| Lab error `toomanyrequests` / rate limit while pulling | Docker Hub or ECR public rate limit | Wait a minute and open the lab again; or `docker login` |
| Lab terminal is blank / `localhost:7681` refused | port 7681 is taken, or the lab stopped | Free port 7681; open the lab again |
| Lab error about memory, pods `Pending`, k3s restarts | Docker has too little memory | Docker Desktop → Settings → Resources → Memory: 6 GB or more |
| Lab error `no space left on device` | Docker disk is full | `docker system prune` (removes unused images; lab images are rebuilt when needed) |
| *Get AI feedback* button missing | no API key (expected) | Optional: add `ANTHROPIC_API_KEY` to `.env`, then `docker compose up -d` |
| Windows: very slow, or labs fail with path errors | project is on the Windows disk (`/mnt/c/...`) | Clone inside WSL (`~/k8s-study-lab`) and run from there |

Logs: `docker compose logs -f backend` (API and lab start), `docker compose logs -f frontend`.
Lab containers: `docker compose -p k8slab ps`.

## How it fits together (for debugging)

```
browser ──► frontend (Vite, :5173) ──/api──► backend (FastAPI, :8000) ──► data/progress.db (SQLite)
   │                                              │
   │                                              └─ /var/run/docker.sock ─► docker compose -p k8slab
   │                                                                          -f labs/envs/<env>/compose.yaml up
   └──────────── iframe ─────────────► lab terminal (ttyd, 127.0.0.1:7681) inside the lab's "toolbox" container
```

The backend container uses the host's Docker engine through the socket, so lab containers run next to
the app containers (not inside them). Lab images are named `k8s-study-lab/*`; lab containers belong to
the compose project `k8slab`. Only one lab runs at a time.

## Without Docker for the app (development)

Labs still need Docker, but the app itself can run directly (Python 3.12+, Node 22+):

```bash
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload          # API on :8000
# in another terminal
cd frontend && npm install && npm run dev   # app on :5173, proxies /api to :8000
```

Tests: `python scripts/validate_content.py` and `cd backend && pytest -q`.
