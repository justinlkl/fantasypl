# GitHub Actions Daily Retraining

This repo includes a workflow at `.github/workflows/daily-retrain.yml`.

## What it does

On each run, it will:

1. Pull latest season files from FPL Core Insights (2025-2026).
2. Sync teams, players, stats, fixtures to DB.
3. Retrain prediction models.
4. Sync latest predictions into the DB.
5. Upload CSV artifacts from `artifacts/`.
6. Optionally trigger backend/frontend deploy hooks.

## Trigger schedule

The workflow runs at:

- `05:15 UTC`
- `17:15 UTC`

These times are set to run shortly after upstream data updates.

## Required repo secrets

Configure in GitHub: Settings -> Secrets and variables -> Actions.

- `DATABASE_URL` (recommended)
  - Production DB connection string for your deployed API.
  - Example: `postgresql+psycopg2://user:pass@host:5432/fpl`
  - If unset, workflow uses local sqlite inside the runner (non-persistent).

## Optional repo secrets

- `BACKEND_DEPLOY_HOOK_URL`
  - Webhook URL from Render/Railway/Fly/etc to redeploy backend.
- `FRONTEND_DEPLOY_HOOK_URL`
  - Webhook URL from Vercel/Netlify/etc to redeploy frontend.

## Manual run

GitHub -> Actions -> FPL Daily Retrain -> Run workflow.

## Local equivalent command

```bash
python -m etl.scheduler --once --force --no-tune
```

## Notes

- Frontend reads live API data (`NEXT_PUBLIC_API_URL`), so the key update path is refreshing the deployed backend DB.
- If your deployment auto-restarts on DB updates, deploy hooks can be omitted.
