# Gmail Genie — Screenshot assets

Product images for the public README and release notes. **Do not commit personal email content** — use a test account or redacted samples.

## Required captures

| File | What to show | Suggested size |
|------|----------------|----------------|
| [`dashboard.png`](dashboard.png) | Main dashboard: onboarding, organize panel, last run summary | 1440×900 |
| [`preview.png`](preview.png) | Preview table + **Apply labels** bar (dry-run) | 1440×900 |
| [`review-queue.png`](review-queue.png) | Review queue with confidence labels | 1280×800 |
| [`metrics.png`](metrics.png) | Insights / metrics page (developer mode on) | 1280×800 |
| [`undo.png`](undo.png) | Undo last apply affordance or confirmation | 1280×720 |
| [`onboarding.png`](onboarding.png) | Setup checklist (OAuth, Ollama, config) | 1280×720 |

Optional:

| File | What to show |
|------|----------------|
| [`developer-mode.png`](developer-mode.png) | Developer mode toggle + transport stats |

## How to capture

1. Run locally: `start_gmail_genie.bat` or `scripts/start_all.bat`  
2. Use a **test Gmail account** with synthetic mail  
3. Complete one **preview** run and one **apply** (optional undo screenshot)  
4. Export PNG from browser (avoid retina 2× if file size matters)  
5. Place files in this folder with exact names above  

## README embedding

Root `README.md` references:

```markdown
![Dashboard](docs/screenshots/dashboard.png)
![Preview flow](docs/screenshots/preview.png)
![Review queue](docs/screenshots/review-queue.png)
![Metrics](docs/screenshots/metrics.png)
![Undo](docs/screenshots/undo.png)
![Onboarding](docs/screenshots/onboarding.png)
```

Until images exist, GitHub will show broken image links — that is expected for new clones.

## Privacy checklist

- [ ] No real names / addresses in subject lines (or blur)  
- [ ] No API keys or `token.json` paths visible  
- [ ] No full mailbox counts that identify you (optional)  

## Placeholder files

This directory may contain only `.gitkeep` until screenshots are added. Do not commit large binary assets without reviewing content.
