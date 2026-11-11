# Llevar k8s-study-lab al Mac mini y seguir con Claude Code

## 1. Pasar el proyecto al Mac

Opción A (más simple): en el Mac, abre esta misma conversación en la app de Claude
y descarga `k8s-study-lab.zip`.

Opción B: desde el celular, guarda el zip en iCloud Drive (Compartir → Guardar en
Archivos) o mándalo por AirDrop al Mac.

Luego, en la Terminal del Mac:

```bash
mkdir -p ~/Projects
cd ~/Projects
unzip ~/Downloads/k8s-study-lab.zip      # ajusta la ruta si lo guardaste en iCloud
cd k8s-study-lab
git log --oneline                        # deberías ver 3 commits
```

El zip incluye la carpeta `.git`, así que el historial viene completo.

## 2. Requisitos (una sola vez)

```bash
# Homebrew, si no lo tienes: https://brew.sh
brew install python@3.12 node@22 git
brew install --cask docker               # Docker Desktop (también lo usará kind en la fase 2)
```

## 3. Levantarlo

Con Docker:

```bash
cp .env.example .env
docker compose up --build
```

Sin Docker:

```bash
# terminal 1
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# terminal 2
cd frontend
npm install
npm run dev
```

Abre http://localhost:5173.

Comprueba que todo está bien:

```bash
python3 scripts/validate_content.py      # debe terminar en OK (150 preguntas)
cd backend && pytest -q                  # 6 passed
```

## 4. Abrir Claude Code

```bash
cd ~/Projects/k8s-study-lab
claude
```

Claude Code lee `CLAUDE.md` al iniciar, así que ya conoce las reglas del proyecto
(contenido en YAML, preguntas originales, validar y testear antes de terminar).

Primeros prompts sugeridos:

- `Lee docs/ROADMAP.md y resume en qué estado está el proyecto.`
- `Empecemos la fase 2: crea labs/kind-config.yaml y los endpoints del backend para crear y resetear un clúster kind.`
- `Revisa las preguntas de content/kcna/container-orchestration.yaml contra la documentación actual de Kubernetes y propón correcciones.`

## 5. Subirlo a GitHub (privado por ahora)

```bash
brew install gh
gh auth login
gh repo create k8s-study-lab --private --source=. --push
```

Cuando quieras hacerlo público: `gh repo edit --visibility public --accept-visibility-change-consequences`.

## Estructura

```
k8s-study-lab/
├── CLAUDE.md                 # instrucciones para Claude Code
├── README.md
├── docker-compose.yml        # backend :8000 + frontend :5173
├── .env.example              # API key opcional (fase 3)
├── .github/workflows/ci.yml  # valida contenido, tests y build en cada push
├── backend/                  # FastAPI + SQLite
│   ├── app/
│   │   ├── main.py           # endpoints: práctica, examen, glosario, stats
│   │   ├── content.py        # carga y valida los YAML
│   │   ├── db.py             # esquema SQLite (data/progress.db)
│   │   └── srs.py            # repetición espaciada (Leitner)
│   ├── tests/test_api.py
│   └── requirements.txt
├── frontend/                 # React + Vite
│   └── src/App.jsx           # Dashboard, Practice, Exam mode, Glossary
├── content/                  # ← el contenido de estudio
│   ├── glossary.yaml         # 101 términos (inglés + español bajo demanda)
│   ├── kcna/                 # 150 preguntas, un archivo por dominio
│   └── cka/tasks/            # fase 2
├── labs/                     # fase 2: configuración de kind
├── scripts/validate_content.py
└── docs/
    ├── CONTENT_FORMAT.md     # cómo escribir preguntas
    ├── ROADMAP.md            # fases y pendientes
    └── SETUP_MAC.md          # esta guía
```

Tu progreso se guarda en `data/progress.db`, que está en `.gitignore` y nunca se sube.
