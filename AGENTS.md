# Repository Guidelines

Contributor guide for **mandarin_foto_hisobot** — an admin-only Telegram bot + Mini App for trip reports ("reys hisoboti"). A single Python process runs an aiogram-3 bot (polling) alongside a FastAPI server that serves the Mini App and its API.

## Project Structure & Module Organization

```
app/                    # Python backend (FastAPI + aiogram-3)
  __main__.py           #   entrypoint — boots server + bot in one event loop
  server.py             #   FastAPI routes, static file serving, WebAuthn endpoints
  bot.py                #   aiogram Dispatcher, admin-gated handlers
  db.py                 #   SQLite/PostgreSQL data layer (WAL, multi-report model)
  db_guard.py           #   database size monitoring (Neon free-tier safety)
  config.py             #   all env vars loaded from .env
  security.py           #   Telegram initData HMAC + browser session tokens
  passwords.py          #   PBKDF2-SHA256 browser login hashing
  passkeys.py           #   WebAuthn passkey store + challenge management
  rules.py              #   business-rule helpers
  storage.py            #   photo storage abstraction (SQLite / Cloudflare R2)
  excel_export.py       #   Excel report generation (openpyxl)
  outbox.py             #   durable channel-send worker

webapp/                 # Frontend — vanilla JS, no build step
  index.html            #   single-page app shell
  js/app.js             #   all client logic (state, bottom-sheet, FormData POST)
  css/styles.css        #   all styles

assets/                 # Excel template files (.xlsx)
data/                   # runtime data (gitignored): reys.db, passkeys.json
```

## Build, Test & Development Commands

```bash
pip install -r requirements.txt   # install dependencies
python -m app                     # run server + bot together (main entrypoint)
python -m app.passwords <user>    # generate an ADMIN_CREDENTIALS line for .env
```

Copy `.env.example` to `.env` and fill in required values before first run.
`WEBAPP_URL` **must be HTTPS**; for local dev use a tunnel (`cloudflared` / `ngrok`).

> No test suite or linter is configured yet.

## Coding Style & Naming Conventions

- **Python**: 4-space indentation, type hints on public functions (`from __future__ import annotations`). Docstrings on modules; inline comments for non-obvious logic.
- **JavaScript**: vanilla JS, no framework or build step. All state lives in a single `state` object in `app.js`.
- **UI text**: all user-facing strings are in **Uzbek** — keep new strings consistent.
- **File naming**: Python modules use `snake_case`; frontend files use `snake_case` or short descriptive names.
- No formatter or linter is enforced at this time.

## Testing Guidelines

No test framework is configured. When adding tests in the future, place them in a `tests/` directory at the project root.

## Commit & Pull Request Guidelines

Commit messages follow the **conventional commits** pattern observed in this repo:

```
feat(scope): short description       # new feature
fix(scope): short description        # bug fix
refactor(scope): short description   # code restructure
```

Keep messages concise and lowercase. Include a scope when the change is localized (e.g., `webapp`, `excel_export`, `coef`).

## Security & Configuration Tips

- **Admin allow-list** is enforced in **two places**: bot handlers (`IsAdmin` filter in `bot.py`) and the API (`authenticate_admin` in `server.py`). Update both when changing admin rules.
- `require_config()` runs at startup; `validate_init_data` fails closed on an empty token — never remove these guards.
- Browser sessions are stateless HMAC tokens; remove a user's `ADMIN_CREDENTIALS` line to revoke access instantly.
- WebAuthn passkeys are bound to `WEBAUTHN_RP_ID` (derived from `WEBAPP_URL`). Changing the domain invalidates all enrolled passkeys.
- Photos are capped server-side (`MAX_PHOTOS`, `MAX_PHOTO_BYTES`, `MAX_TOTAL_BYTES` in `server.py`); client-side caps are convenience only and **not trusted**.

## Architecture Overview

- **Two entry paths**: Telegram Mini App (initData, login-free) or browser (password / WebAuthn passkey → httpOnly session cookie).
- **Data model**: `reports` (named containers, max 5, oldest auto-pruned) → `inventory` (per-report per-type balance) → `activity` (per-report log).
- **Database**: SQLite (local, WAL) or PostgreSQL (Neon) — controlled by `DATABASE_BACKEND` env var.
- **Photo storage**: SQLite/disk (default) or Cloudflare R2 — controlled by `PHOTO_STORAGE_BACKEND`.
- The frontend **cannot** use `tg.sendData()` (4 KB limit, no files); photos go via `fetch` to `/api/report`.
