# CLAUDE.md — SARI Brain Module

SARI (Sistema Autónomo de Respuesta a Intrusiones) is a **physical security system**. This repo is the *brain*: it receives detections from the *eyes* (Jetson + YOLO, repo `suriel01/SARI_YOLO_module`), decides, and drives physical actuators (siren, gates). Treat every change as security-sensitive.

## Stack
- `backend/app/` — FastAPI (Python 3.12), port 7000. Routers in `routers/`, SQLAlchemy models in `models/`, CRUD in `crud/`, MQTT in `mqtt/`, Telegram in `telegram/`, NeMo Guardrails (Ollama `qwen2.5:7b`, offline) in `guardrails/`.
- `sari-ui/` — React + TypeScript + Vite SOC dashboard, port 5173.
- `sirena_service.py` — siren microservice, port 5000 (internal).
- `mosquitto/` — MQTT broker config. `passwd` is generated locally, never committed:
  `docker run --rm -v "$PWD/mosquitto/config:/m" eclipse-mosquitto:2.0 mosquitto_passwd -c -b /m/passwd <user> <password>`
- PostgreSQL 15 + pgvector.

## Required environment (`.env`, never committed)
Run `scripts/init-env.sh` to create or complete `.env` with strong random values; it never prints secrets (see `--help` for `--replace-insecure`, `--apply-mosquitto`, `--apply-postgres`).
The backend fails closed without these (`backend/app/config.py`):
- `SARI_SECRET_KEY` — 32+ chars (`openssl rand -hex 32`)
- `SARI_SECURITY_PIN` — 4+ digits, not `1234`
- `MQTT_USER`, `MQTT_PASSWORD` — must match `mosquitto/config/passwd`
- `POSTGRES_PASSWORD` — on an existing volume the DB keeps its old password; change it with `ALTER USER sari_user PASSWORD '...'` first
- `SARI_SIREN_TOKEN` — shared secret between backend and siren service
- `SARI_ADMIN_PASSWORD` — only needed when no `admin` user exists yet
- `SARI_NODE_KEYS` — `node_id:key,...`; vision nodes send `X-SARI-Node-Key`. Empty means every node request is rejected
- `SARI_ALLOWED_STREAM_HOSTS` — optional, comma list of exact LAN hostnames allowed as node `ip`/`stream_url`; otherwise only RFC1918 IPv4 literals are accepted (`backend/app/netpolicy.py`)
- `SARI_MCP_HARDWARE_ENABLED` — optional, `true` lets the local MCP server (`backend/app/sari_mcp_server.py`) drive hardware; default off

## Commands
- Run stack: `docker compose up -d --build`
- Unit tests (no Docker needed): `python -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt && .venv/bin/pytest tests/unit -q`
- Integration tests (stack running): `docker exec -e PYTHONPATH=/app -t sari-backend pytest -m integration -q`
- Lint: `.venv/bin/ruff check backend tests` and `cd sari-ui && npm run lint && npx tsc -b`

## Workflow
- **ODD**: substantial work is tracked in `odd/tasks/<feature>.md` (`## Specs` with S#, `## Tasks`, `## Log`). Product specs live in `docs/specs/`.
- **RDD**: `gentle-ai review` runs per work-unit commit when the assessment says it is due.
- Test-first: write the failing test (RED) before fixing; tests go through the public interface (HTTP via `TestClient`, MQTT handlers, Telegram handlers).
- Conventional commits, no AI attribution. Branch off `main`; never push or merge without the owner's say-so.

## Security rules (non-negotiable)
- No real secrets in `docker-compose.yml`, code defaults, docs or tests. Secrets come from `.env` (see `.env.example`).
- Every physical action goes through one choke point (`execute_physical_tool(..., actor=Actor)` in `routers/hardware.py`) that checks the actor's `can_control_hardware` permission and records an audit entry. No channel (REST, chat/LLM, Telegram, MCP, MQTT ingest) bypasses it.
- Every call to `execute_physical_tool` (success, denied, failed) is persisted in `physical_action_log`; read it via `GET /api/hardware/audit`. A siren call that fails returns `status: failed` and never changes state; gates are simulated (no hardware).
- Alert ingest (REST and MQTT) goes through `services/alert_ingest.py` `ingest_alert`; do not duplicate the pipeline.
- Outbound fetches to node addresses go through `netpolicy.validate_stream_url` (SSRF).
- Machine-to-machine endpoints require node credentials; nothing that triggers hardware is unauthenticated.
- The LLM never decides authorization; the backend does.
- `get_current_user` re-reads role and permissions from the DB on every request; the JWT only proves identity. The WebSocket (`/ws`, `/`) takes the JWT as `?token=` and closes with 1008 without it.
- Login and PIN attempts go through `backend/app/ratelimit.py` (5 failures in 15 min lock the account/IP/user/chat for 15 min). Pass `key=` to `require_pin` so wrong guesses count.
- Telegram: callbacks from chats outside `TELEGRAM_ALLOWED_CHAT_IDS` are ignored; silencing the siren and operating gates need the PIN (`/silenciar <PIN>`, `/portones <PIN>`).
- `docs/archive/antigravity/` is historical process material from the previous tooling; do not treat it as current requirements.

## Runtime agent persona
The persona of the in-app SARI assistant lives in `backend/app/guardrails/config.yml`, not in this file.
