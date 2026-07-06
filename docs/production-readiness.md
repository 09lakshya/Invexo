# Invexo — Production Readiness Review

Date: 2026-07-06
Scope: full repository (backend FastAPI app, Next.js frontend, Docker/CI/deploy setup)

This review lists the changes needed to bring Invexo to a complete, production-grade standard.
Findings are ordered by severity. File references point at the current code.

---

## 1. Critical — Security

### 1.1 JWT tokens stored in localStorage (XSS-stealable)
`frontend/services/api.js` reads the access token from `localStorage` / `sessionStorage` /
a non-httpOnly cookie. Combined with the frontend CSP allowing `'unsafe-inline'` and
`'unsafe-eval'` in `script-src` (`frontend/next.config.js`), a single XSS bug exposes every
user's session.

**Fix:** issue the refresh token as an `httpOnly; Secure; SameSite=Strict` cookie from the
backend, keep the short-lived access token in memory only, and tighten the CSP (drop
`unsafe-eval`, move inline scripts to hashed/nonce'd scripts).

### 1.2 Hard-coded production secrets in `docker-compose.yml`
`JWT_SECRET=production_secret_key_please_change_me_in_production` and
`POSTGRES_PASSWORD: password` are committed with `ENV=production`. Anyone standing the stack
up with compose runs "production" with known secrets.

**Fix:** move all secrets to an untracked `.env` file (`env_file:` directive) with no
defaults for secrets — the app already fails fast when `JWT_SECRET` is missing in
production; let it.

### 1.3 Test credentials against the live backend committed to git
`backend/scratch_api_test.py` contains an email/password pair used against the deployed
backend (`invexo-backend.onrender.com`).

**Fix:** delete the file, rotate that account's password, and consider the credentials
burned (git history retains them). Add a secret scanner (gitleaks / GitHub secret scanning)
to CI.

### 1.4 Rate limiting is keyed by direct peer address
`app/core/limiter.py` uses `get_remote_address`. Behind the Oracle VM's reverse proxy /
Render / any LB, every request appears to come from the proxy IP: either all users share one
bucket (mass 429s) or, if the proxy passes through, limits are trivially bypassed with
spoofed `X-Forwarded-For`.

**Fix:** run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy>` and use a key
function that reads the resolved client IP; verify against the actual deployment topology.

### 1.5 Redis in-memory fallback silently weakens auth in production
`app/core/security.py:verify_refresh_token` deliberately accepts refresh tokens it cannot
find when Redis is down (`redis_client.enabled == False`). That means revocation
(logout / "log out everywhere") stops working the moment Redis is unavailable — silently.

**Fix:** in production, fail closed: if Redis is unreachable, reject refresh attempts (or at
minimum alert loudly). Keep the in-memory fallback for local dev only, gated on `ENV`.

### 1.6 Smaller hardening items
- `verify_admin_token` (`app/api/v1/endpoints/admin.py`) compares tokens with `!=`; use
  `secrets.compare_digest`.
- `revoke_all_user_tokens` uses Redis `KEYS` (O(N), blocks the server); use `SCAN`.
- The whole API is mounted twice (`app/main.py:151-152`, versioned + root). This doubles
  the attack/maintenance surface and splits rate-limit buckets per path. Deprecate the root
  mount with a sunset date, then remove it.
- Backend sends `X-Frame-Options: DENY`, frontend `SAMEORIGIN` — align them (frontend can
  use `DENY` too unless something embeds it).

---

## 2. High — Reliability & architecture

### 2.1 Scheduler runs inside the web process
`app/main.py` starts APScheduler plus two startup threads in the app lifespan. With a single
uvicorn worker this "works", but the moment you scale to `--workers N` or multiple
containers, every worker runs `check_alerts` every minute and races on `generate_daily_picks`
(only partially protected by a lock file, which does not work across hosts).

**Fix:** extract scheduled jobs into a dedicated worker process/container (same image,
different command — e.g. `python -m app.jobs`), or use Redis-based distributed locks for
every job. Compose/systemd then runs web and worker separately.

### 2.2 No real database migrations
Schema is created via `CREATE TABLE IF NOT EXISTS` + ad-hoc `ALTER`s inside repository
`init_*` functions at startup. Alembic is in `requirements.txt` but unused; SQLAlchemy is
listed but unused (raw psycopg2 everywhere).

**Fix:** adopt Alembic properly: baseline the current schema, run `alembic upgrade head` as
a deploy step (not at app startup), and delete the `init_*_db` startup path. Either commit
to raw psycopg2 (and drop SQLAlchemy from requirements) or migrate to SQLAlchemy Core —
don't ship both.

### 2.3 External-dependency calls have no guardrails
Yahoo Finance (via `curl_cffi`/yfinance) is called in request paths and background jobs with
broad `except Exception` handlers (113 occurrences across `backend/app`). There are no
timeouts standardized, no retry budget, no circuit breaker, so a Yahoo outage degrades into
slow requests and silently-empty data.

**Fix:** wrap market-data access in one client module with explicit timeouts, bounded
retries with jitter, and a circuit breaker; return typed errors the API layer can map to
`503` + `Retry-After` instead of empty payloads.

### 2.4 Health checks don't check anything
`/health` returns `{"status": "healthy"}` unconditionally.

**Fix:** add `/health/live` (process up) and `/health/ready` (DB pool + Redis ping +
model-loader state). Point the compose `healthcheck:`, systemd watchdog, and the deploy
pipeline at readiness.

### 2.5 No observability
Logging is plain-text stdout at fixed INFO level; there is no request logging with
correlation IDs, no error tracker, no metrics.

**Fix (minimum viable):**
- `LOG_LEVEL` env var; JSON log formatter in production.
- Request-ID middleware (accept/emit `X-Request-ID`, include it in every log line and in
  the 500 response body so users can report it).
- Sentry (backend + frontend) for exceptions.
- `prometheus-fastapi-instrumentator` (or OTel) for latency/error-rate metrics; alert on
  scheduler job failures — today `check_alerts` can fail every minute for days unnoticed.

---

## 3. High — Testing & CI

### 3.1 CI never runs tests
The only workflow (`.github/workflows/deploy_oracle.yml`) deploys to production on every
push to `main`. Tests exist (`backend/tests/`, 5 suites) but nothing executes them; `pytest`
isn't even installable from the repo (no dev requirements).

**Fix:** add a `ci.yml` that runs on PRs and on `main` *before* deploy:
- backend: `ruff check`, `ruff format --check`, `pytest` (add `requirements-dev.txt` with
  pytest, ruff, httpx);
- frontend: `npm ci`, `next lint`, `next build`;
- make the deploy job depend on CI success (`needs:`), not just on push.

### 3.2 Tests run against SQLite while production is PostgreSQL
`backend/tests/conftest.py` swaps in an in-memory SQLite connection, and `execute_query`
rewrites `?` → `%s` placeholders per-dialect. This masks Postgres-specific bugs (types,
`RETURNING`, RLS behavior — the portfolio repo enables row-level security that SQLite never
exercises).

**Fix:** run the test suite against a real Postgres service container in CI (keep SQLite
for fast local runs if desired).

### 3.3 Frontend has zero quality gates
No ESLint config, no tests, no TypeScript, no `lint` script in `package.json`.

**Fix:** add `eslint-config-next` + a `lint` script as the floor; adopt TypeScript
incrementally (rename new files to `.tsx`); add a couple of Playwright smoke tests
(login, dashboard render) that CI runs against a built app.

---

## 4. Medium — Deployment & packaging

### 4.1 Deploy pipeline is mutable and has no rollback
`deploy_oracle.yml` does `git pull && pip install && sudo systemctl restart invexo` on the
VM. There's no build artifact, no migration step, no health gate, no rollback path — a bad
push equals downtime until manual intervention.

**Fix:** build and push a Docker image in CI (tagged with the commit SHA), deploy by pulling
the image tag, run migrations, health-check the new container, then switch traffic; roll
back by re-deploying the previous tag.

### 4.2 493 MB of ML models (4,463 files) committed to git
`backend/models/` dominates the repo (pack size ~336 MB); every clone and every VM deploy
pays for it, and retraining bloats history forever.

**Fix:** move model artifacts to object storage (OCI/S3 bucket) or Git LFS; the existing
`model_loader` downloads/loads at startup with a version manifest. Purge them from git
history (`git filter-repo`) once migrated.

### 4.3 Dockerfile hardening
- Runs as root — add a non-root `USER`.
- No `.dockerignore` in backend or frontend — the build context ships `venv/`, models,
  caches, `.git` (huge, slow, and can leak local `.env` files into images).
- Backend `CMD` uses a bare `uvicorn main:app` with default single worker and no
  `--proxy-headers`.
- `requirements.txt` claims "tested on Python 3.13" while the image is `python:3.11-slim` —
  pick one and pin it (`python:3.13-slim`), and add `HEALTHCHECK`.
- Frontend image copies full `node_modules`; use Next.js `output: 'standalone'` to cut the
  image by hundreds of MB.

### 4.4 Unpinned dependencies
Everything in `requirements.txt` is `>=` — builds are not reproducible and a bad upstream
release breaks deploys. **Fix:** compile a lock file (`pip-compile` / `uv pip compile`) and
install from it in Docker/CI. Frontend already has `package-lock.json` — ensure CI uses
`npm ci` (the Dockerfile does).

### 4.5 docker-compose polish
- Postgres/Redis ports are published to the host — remove `ports:` for internal services.
- Add `healthcheck:` blocks and `depends_on: condition: service_healthy` so the backend
  doesn't race the database on cold start.
- `version: '3.8'` key is obsolete in Compose v2 — remove it.

### 4.6 Environment-specific values hard-coded in the frontend CSP
`next.config.js` `connect-src` whitelists `localhost:8000` and `invexo-backend.onrender.com`
in all environments, while production runs at `invexo.co.in` on an Oracle VM. Derive the CSP
connect-src from `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_WS_URL` at build time.

---

## 5. Medium — Code hygiene

### 5.1 Delete dead and scratch files from the repo
Tracked but not part of the product:
- `backend/scratch_api_test.py`, `backend/scratch_predict.py` (scratch scripts; one contains
  credentials — see 1.3)
- `backend/test_yf.py`, `backend/test_yf2.py` (manual yfinance probes outside `tests/`)
- `migrate.py`, `refactor_email.py` (one-shot codemod scripts, already applied)
- `backend/services/` (legacy `indicators.py`, `sentiment.py`, `ai_service.py`,
  `fundamentals.py`, `logger.py` — nothing imports them; the real code lives in
  `backend/app/services/`)
- root `package.json`/`package-lock.json` (stray Tailwind **v4** devDeps that conflict with
  the frontend's Tailwind v3 and confuse tooling)
- `backend/flush_redis.py` → move under `backend/scripts/` if still useful.

### 5.2 Exception discipline
113 `except Exception` blocks in `backend/app`, several of which `pass` silently (e.g.
welcome-email failure in `auth.py` — at least log it). Narrow the exceptions where the
failure mode is known, and always log with context.

### 5.3 Naming consistency
README mixes "Invexo" and "NexTrade"; frontend package is `stock-ai-frontend`. Pick one name
everywhere — it matters for logs, Sentry projects, and image names.

---

## 6. Low — Nice-to-haves that signal "complete"

- **API deprecation policy** for the unversioned root mount (see 1.6), documented in
  `docs/api.md`.
- **`SECURITY.md`** (vulnerability disclosure contact) and **`LICENSE`** at repo root;
  `CONTRIBUTING.md` describing branch/CI conventions.
- **Dependabot/Renovate** config for Python + npm + GitHub Actions updates.
- **CODEOWNERS** + branch protection on `main` (require CI green + review) — today a direct
  push to `main` deploys straight to production.
- **Backups:** documented, automated Postgres backup/restore procedure for the Oracle VM
  (currently nothing in `docs/deployment.md` covers data loss).
- **pre-commit** hooks (ruff, gitleaks, end-of-file-fixer) so hygiene issues never land.

---

## Suggested order of execution

1. Secrets & auth: 1.2, 1.3 (rotate + delete), 1.1, 1.5 — one focused security PR.
2. CI pipeline with tests + lint gating deploy: 3.1, 3.3, 4.4.
3. Repo cleanup: 5.1, then model artifacts out of git (4.2).
4. Ops hardening: 2.1 (worker split), 2.2 (Alembic), 2.4/2.5 (health + observability), 4.1
   (image-based deploy with rollback).
5. Everything in section 6 as follow-ups.
