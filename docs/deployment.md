# Invexo Deployment Guide

This document describes how to configure, containerize, run, and scale the Invexo platform in development and production environments.

---

## 1. Environment Variables Configuration

Configure a `.env` file in the root workspace or individually within the backend/frontend directories.

### Backend Configurations (`backend/.env`)
```ini
# Environment
PORT=8000
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/invexo
REDIS_URL=redis://redis:6379/0

# Security (JWT)
JWT_SECRET=super_secret_cryptographic_signing_key_change_me
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRY_MINUTES=15
JWT_REFRESH_EXPIRY_DAYS=7

# Third-party Integrations (Optional)
RESEND_API_KEY=
RESEND_FROM=onboarding@resend.dev
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
```

---

## 2. Docker Containerization

The project is fully dockerized with production-ready multi-stage builds.

### FastAPI Backend Dockerfile (`backend/Dockerfile`)
The backend leverages Python 3.11 slim containers.
* Sets environment variables to optimize compilation (`PYTHONDONTWRITEBYTECODE`, `PYTHONUNBUFFERED`).
* Installs system build tools for C extensions (e.g. `g++`, `libpq-dev`).
* Runs via `uvicorn` web server listening on port 8000.

### Next.js Client Dockerfile (`frontend/Dockerfile`)
The frontend uses a multi-stage compilation flow to minimize final image sizes:
1. **Dependency Stage**: Installs exact node modules using lockfiles.
2. **Build Stage**: Compiles Next.js React assets with performance optimization and static HTML exports.
3. **Runner Stage**: Minimal node image copying built `.next` directories and serving via Next.js standard server on port 3000.

---

## 3. Orchestrating with Docker Compose

A master `docker-compose.yml` file is located in the root folder to spin up all services together.

### Services Orchestrated:
1. **postgres**: PostgreSQL database cluster storing persistent user profiles, portfolios, and indicators. Includes automatic health checks.
2. **redis**: In-memory Redis cache and WebSocket Pub/Sub broker.
3. **backend**: Python FastAPI server. Depends on postgres/redis health status.
4. **frontend**: Next.js client serving components at port 3000.

### Running the Environment:
Build and launch all services in the background:
```bash
docker-compose up --build -d
```

Check status and logs:
```bash
docker-compose ps
docker-compose logs -f
```

Shut down:
```bash
docker-compose down -v
```
