# Gmail Genie — v1.0 Beta Release Notes

**Tagline:** Local AI inbox organizer for Gmail. Your email stays on your machine. Labels only. Fully reversible.

---

## Overview

Gmail Genie helps you organize recent Gmail using a **rules-first** classifier with optional **local Ollama** verification and rare **Groq** escalation. It applies **Gmail labels only** — your inbox remains visible, and you can **undo** the last apply run.

This beta is intended for **self-hosted, single-user** use on your own machine.

---

## Major features

- **Organize recent mail** — Preset ranges (1 / 3 / 7 / 14 days) or custom Gmail query
- **Preview-first workflow** — Dry-run draft with full email table before any Gmail change
- **Draft session persistence** — Preview survives navigation and refresh until apply or dismiss
- **Label memory** — Skips mail already organized with Genie labels
- **Undo last apply** — Removes only Genie-managed labels from the previous run
- **Review queue** — Human-friendly review for uncertain classifications
- **Operations dashboard** — Health checklist, last run summary, activity feed
- **Developer mode** — Optional transport, latency, and inference diagnostics
- **Docker support** — `docker compose up` for containerized local deployment
- **Scheduler** — Optional automatic runs (disabled by default)

---

## Architecture summary

```
Gmail API (paginated scan)
  → skip existing Genie labels
  → dedup (SQLite)
  → rules classifier
  → semantic verify / fallback (Ollama)
  → rare Groq escalation
  → labels-only apply
  → metrics, activity, review queue, undo store
```

Date-range buttons only change the Gmail search query. Per-run caps limit how many **new** emails are organized (default 25).

---

## Safety philosophy

| Principle | Implementation |
|-----------|----------------|
| **Inbox preserved** | No auto-archive, no auto-trash |
| **Labels only** | Category labels under configured Gmail paths |
| **Preview default** | First-time flow encourages dry-run |
| **Reversible** | Undo removes Genie labels from last apply only |
| **Local-first** | Classification runs locally; Gmail API for mail access |

---

## Known limitations

- Single user, single machine — not multi-tenant SaaS
- Per-run email cap — does not exhaustively process entire date ranges in one run
- Undo covers **last apply only**
- Windows + Gmail API: keep fetch concurrency low (default 3, max 5)
- Requires local Ollama (and optional Groq key) for full inference paths
- OAuth setup is the main onboarding step for new users

---

## Local-first approach

- Email content is processed on your computer
- Persistent stores are local SQLite files under `backend/data/` and `data/`
- No cloud vector DB, no hosted sync, no third-party email storage

---

## Docker

- Backend + frontend images via `docker-compose.yml`
- Mount OAuth files and config after first local authentication
- Ollama expected on the host (`host.docker.internal`)

See README for step-by-step setup.

---

## Developer mode

Hidden by default on the dashboard. When enabled:

- Insights page with session metrics
- Gmail transport retry counters
- Raw review-queue diagnostics

---

## Roadmap (community)

- Screenshot assets in README
- Improved scheduler UX
- Optional export of draft previews
- Broader evaluation dataset tooling

---

## Upgrade / install

1. Clone repository
2. Copy `.env.example` → `.env`
3. Complete Gmail OAuth (`backend/credentials.json`, `backend/token.json` — **never commit**)
4. Install Ollama + model from `config.yaml`
5. Run `start_gmail_genie.bat` or `scripts/start_all.bat`

Full details: [README](../README.md)

---

## License

MIT — see [LICENSE](../LICENSE)
