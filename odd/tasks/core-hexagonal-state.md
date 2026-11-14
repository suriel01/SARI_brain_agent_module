# Feature: core-hexagonal-state (SARI v2, Phase A)
Objective: move the brain's business rules out of routers into domain/application layers and replace in-memory `HardwareState` with persisted state so the API can run with several workers and survive restarts.
Branch: `feat/hexagonal-core` (stacked on `chore/claude-odd-reorg`, PR #1). Delivery: ask-on-risk, slices ≤ ~900 lines for RDD. Test runner: `.venv/bin/pytest -q tests/unit`.

## Specs
- S1 — Layout: `backend/app/domain/` (pure Python: Actor, permissions, alarm/actuator state values, trigger policy), `backend/app/application/` (use cases: `ExecutePhysicalAction`, `IngestAlert`), `backend/app/adapters/` (http, mqtt, telegram, mcp, persistence, actuators). Domain imports nothing from FastAPI, SQLAlchemy or requests.
- S2 — Public contracts unchanged: every existing HTTP route, MQTT topic, Telegram command and response shape behaves as before (characterization tests first); the 278 existing unit tests stay green.
- S3 — `HardwareState` is replaced by a `StateRepository` port with a Postgres adapter (Alembic migration): siren/gates state, alert counters, last alert thread, node status/telemetry, operational log. State survives a process restart.
- S4 — Background work (MQTT subscriber, Telegram poller, watchdog, siren auto-off, ghost-node pruning) runs in a separate `sari-worker` process/service, not in API workers; siren auto-off and pruning leave the `/state` GET.
- S5 — Login/PIN limiters and WebSocket broadcast work across processes (Postgres-backed limiter counters; broadcast via Postgres LISTEN/NOTIFY or equivalent, no new mandatory service).
- S6 — The API runs with `uvicorn --workers 2` without duplicated alert ingestion, duplicated siren commands or Telegram poller conflicts.

## Tasks
| ID | Specs | Route | Status | Evidence |
|---|---|---|---|---|
| A1 | S1, S2 | delegated (context backstop) | pending | — |
| A2 | S3, S2 | delegated (context backstop) | pending | — |
| A3 | S4, S5, S6, S2 | delegated (context backstop) | pending | — |

Route evidence: parent context is past the ~150k backstop; units are sequential (A2 builds on A1's ports, A3 on A2's repository), one writer at a time.

## Log
- L1 (2026-11-13, user, verbatim): "ok arma un plan de ataque de todos estos arreglos, no lo ejecutes primero preparalo escribelo todo, busca en internet si hay alguna tecnologia que nos pueda ayudar, algo nuevo para seguridad, lo que sea para que este sistema esté en la vanguardia (con lo que tenemos, y que sea escalable) tambien tengo un esp32 entonces si es posible incluyelo, tambien tengo a la mira el lenguaje de programacion Rust para todas las conexiones fisicas del esp32"
- L2: Plan approved: `~/.claude/plans/joyful-scribbling-raven.md` (SARI v2, phases 0, A–J). This document covers Phase A only. ESP32 model unknown (Phase 0 decision pending).
