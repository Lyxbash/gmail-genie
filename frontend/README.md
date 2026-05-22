# Gmail Genie — Frontend

React + Vite operations dashboard for inbox organization, review, activity, and metrics.

[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)

Full product setup (OAuth, Ollama, Docker, safety model) is documented in the **[root README](../README.md)**. This file covers frontend-only development.

---

## Stack

| Layer | Choice |
|-------|--------|
| UI | React 19 |
| Build | Vite 8 |
| HTTP | Axios |
| Charts | Recharts |
| Routing | React Router 7 |
| Styling | Plain CSS (dark operations theme) |

---

## Prerequisites

- **Node.js 20+** and npm  
- Gmail Genie **backend** running at `http://127.0.0.1:8000` (see root README)

---

## Setup

```bash
cd frontend
npm install
```

Optional environment file:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_BASE` | `http://127.0.0.1:8000` | Backend URL for API calls |

---

## Run (development)

**Terminal 1 — backend** (from repository root):

```bash
# Windows
.\venv\Scripts\activate
python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000

# macOS / Linux
source venv/bin/activate
python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — frontend:**

```bash
cd frontend
npm run dev
```

| URL | Service |
|-----|---------|
| http://localhost:5173 | Vite dev server (UI) |
| http://127.0.0.1:8000 | FastAPI backend |
| http://127.0.0.1:8000/docs | OpenAPI (development) |

CORS is configured on the backend; default dev origins include `http://localhost:5173`.

**Windows shortcut:** run `start_gmail_genie.bat` from the repo root to launch both services.

---

## Build for production

```bash
cd frontend
# Set API URL for your deployment
export VITE_API_BASE=https://api.your-host.example   # Linux/macOS
# set VITE_API_BASE=...                             # Windows cmd

npm run build
npm run preview
```

Docker builds the frontend image with `VITE_API_BASE` passed as a build arg (see root README → Docker).

---

## Pages & routes

| Route | Purpose |
|-------|---------|
| `/` | Dashboard — organize, health, last cycle, onboarding |
| `/activity` | Recent classification events |
| `/review` | Human review queue + corrections |
| `/metrics` | Daily charts + session stats (**Insights** — visible in developer mode) |
| `/settings` | Read-only config summary |

---

## Developer mode

Toggle on the dashboard stores preference in `localStorage` (`gmail-genie-developer-mode`).

When enabled:

- Extra diagnostics on the dashboard  
- Transport / inference details in tables  
- **Insights** (`/metrics`) link in navigation  

Normal users can ignore this.

---

## Project layout

```
frontend/src/
├── components/     # OrganizeInbox, tables, health widgets
├── pages/          # Dashboard, Activity, Review, Metrics, Settings
├── hooks/          # useDeveloperMode, API hooks
├── utils/          # User-facing labels
└── api.js          # Axios client (VITE_API_BASE)
```

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| API errors / CORS | Backend running? `VITE_API_BASE` matches backend URL? |
| Blank dashboard | Browser console; backend `/health` |
| Metrics 404 / hidden | Enable **Developer mode** for Insights nav |
| Stale preview | Backend `GET /pending-preview`; re-run organize preview |

See **[root README § Troubleshooting](../README.md#troubleshooting)** for OAuth, Ollama, Docker, and Gmail issues.

---

## License

MIT — same as the parent project ([LICENSE](../LICENSE)).
