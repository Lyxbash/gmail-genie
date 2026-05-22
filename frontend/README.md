# Gmail Genie — Frontend

React + Vite dashboard. **Setup, OAuth, Ollama, Docker:** see [root README](../README.md).

## Stack

React 19 · Vite 8 · Axios · Recharts · React Router

## Dev

**Backend** (repo root):

```bash
python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

- UI: http://localhost:5173  
- API: http://127.0.0.1:8000  

Windows: `start_gmail_genie.bat` starts both.

## Env

| Variable | Default |
|----------|---------|
| `VITE_API_BASE` | `http://127.0.0.1:8000` |

## Routes

| Path | Page |
|------|------|
| `/` | Dashboard, organize, onboarding |
| `/activity` | Recent classifications |
| `/review` | Review queue |
| `/metrics` | Insights (developer mode only) |
| `/settings` | Config summary |

## Build

```bash
npm run build
```

Set `VITE_API_BASE` before build for production/Docker.

## License

[MIT](../LICENSE)
