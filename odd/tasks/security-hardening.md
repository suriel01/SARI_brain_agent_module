# Feature: security-hardening
Objective: adapt the SARI brain repo to Claude Code + ODD/RDD and harden the physical-security attack surface found in the 2026-11-13 audit.
Branch: `chore/claude-odd-reorg` (reorg + test base), then `fix/security-hardening`. Delivery: ask-on-risk. Test runner: `pytest tests/unit -q` (local venv), integration via `docker exec sari-backend pytest -m integration`.

## Specs
- S1 — User request: "reornagiza el proyecto ya que estaba ajustado apra google antigravity, acomodalo para ti y para ODD y RDD". Remove/archive Antigravity-era process artifacts, add `CLAUDE.md`, keep product docs and specs.
- S2 — User request: "dime que puedes mejorar o cambiar ya que es un sistema de seguridad". Each audited weakness below is fixed with a failing test first.
- S3 — Test base: unit tests run without Docker, broker or Postgres; integration tests are marked and opt-in.
- S4 — Physical actions (`activar_sirena`, `desactivar_sirena`, `cerrar_accesos`) require an authenticated actor with `can_control_hardware`, whatever the channel (REST, chat/LLM, Telegram, MCP, alert ingest by an authenticated node).
- S5 — No secret has a hardcoded default; the backend refuses to start without `SARI_SECRET_KEY`, the security PIN and the MQTT/DB passwords.
- S6 — Machine endpoints (`/api/alerts/event`, `/api/hardware/telemetry/node`) require a per-node key.
- S7 — Siren service requires a shared token and is reachable only on the internal Docker network.
- S8 — Every physical action is persisted with actor, channel, action, result and timestamp.
- S9 — Telegram callbacks enforce the chat allowlist; silencing requires confirmation.
- S10 — WebSocket requires a JWT; Eyes router enforces RBAC; empty PIN never bypasses checks.
- S11 — `stream_url` is restricted to private node addresses (SSRF).
- S12 — Login and PIN are rate limited; PIN comparison is constant-time; permissions are re-read from the DB per request.
- S13 — MQTT uses per-node users, ACLs and TLS (assumption: Mosquitto config only; Jetson side in Eyes repo).
- S14 — Infra: Postgres not published, non-root containers, no host-specific paths.

## Tasks
| ID | Specs | Route | Status | Evidence |
|---|---|---|---|---|
| R1 | S1 | inline | done | f65b14e |
| B1 | S3 | inline | done | e760e89 — `pytest -q`: 2 passed, 12 integration deselected |
| T1 | S5 | inline | done | 3b499f1 — RED: empty-PIN eye update returned 200; GREEN 15 passed |
| T3 | S7 | inline | done | 6a194ab — RED 10 failed; GREEN 30 passed |
| T4 | S4 | inline | done | 7787584 (+89ff663 mcp<2 pin) — RED collection error; GREEN 46 passed |
| T2 | S6 | inline | done | 997f1c9 — RED 13 failed; GREEN 62 passed |
| T7 | S9 | inline | partial | allowlist enforced on callbacks via T4 actor; silence confirmation pending |
| T8 | S10 | inline | pending | — |
| T10 | S12 | inline | pending | — |
| T5 | S8 | inline | pending | — |
| T6 | S4 | inline | pending | — |
| T9 | S11 | inline | pending | — |
| T11 | S13 | inline | pending | — |
| T12 | S14 | inline | pending | — |
| T13 | — | inline | pending | Alembic migrations |
| T14 | — | inline | pending | dedupe alert ingest |
| E1 | — | other repo | deferred | Eyes repo hardening (separate session) |

Route evidence: all tasks inline; no Writer trigger (units are sequential and share `hardware.py`/`security.py`).

## Log
- L1 (2026-11-13, user, verbatim): "ok reornagiza el proyecto ya que estaba ajustado apra google antigravity, acomodalo para ti y para ODD y RDD, dime que puedes mejorar o cambiar ya que es un sistema de seguridad, este es el modulo brain, en la jetson esta el modulo ojos para las detecciones pero ese lo encuentras en este repo: https://github.com/suriel01/SARI_YOLO_module.git el modulo brai nen el que estamos esta aqui: https://github.com/suriel01/SARI_brain_agent_module.git checalos tambien. armame un plan /plan"
- L2: Plan approved: `~/.claude/plans/joyful-scribbling-raven.md`. Phase 0 (rotate Telegram token, camera and MQTT passwords leaked in the public Eyes repo) is a manual owner action.
- L3: R1 decisions: `NeMo-Guardrails/` gitlink untracked and ignored but left on disk (180 MB, unused; pip package is used). `jetson_telemetry.py` and `sari-jetson.service` stay until E1 moves them to the Eyes repo.
- L4: RDD review of the R1+B1 slice (lineage review-c90eeaaba9178788) was granted but could not run: the reviewer needs the `claude` CLI on PATH, which this machine lacks. Status: unavailable; no PASS claimed.
- L5: T2 deviation: node keys come from `SARI_NODE_KEYS` env instead of hashed DB rows (simpler, no migration). Legacy alert route aliases kept (Eyes repo depends on them) but all require the key.
- L6: Found while pinning: `mcp` 2.x removed `mcp.server.fastmcp`; an unpinned rebuild would have broken the MCP server. Pinned `mcp==1.30.0`.
- L7: Compatibility impact: the Eyes REST alert POST is rejected until E1 adds `X-SARI-Node-Key`; the MQTT `sari/alerts` path still triggers the siren (as `Actor.node`), so detection→siren keeps working over MQTT.
- L8: Next: T7 (silence confirmation), T8 (WS JWT, Eyes RBAC), T10, T5, T6, T9, T11–T14, then E1 in the Eyes repo.
