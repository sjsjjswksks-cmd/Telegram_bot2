# Telegram Bot Builder — hanamii

## Deploy
1. Push this repo to GitHub.
2. In hanamii: New Project → connect GitHub → select repo.
3. Environment variables:
   - `ADMIN_PASSWORD` (required) – panel password
   - `ADMIN_USER` (default `admin`)
   - `DATA_DIR` (default `data`)
4. Port is read from `PORT`. Health check: `/health`.
