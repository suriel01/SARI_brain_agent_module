# Phase B — Alarm state machine and supervision

Objective: arm/disarm modes (Alarmo model) gate the siren; device heartbeats raise faults, never the siren.
Branch: `feat/alarm-state-machine` (stacked on `feat/hexagonal-core`). Delivery: ask-on-risk. Runner: `.venv/bin/pytest tests/unit -q`.

## Specs

- **S1 States.** From the approved plan: "States: `disarmed → arming(exit delay) → armed_{away,home,night} → pending(entry delay) → triggered`." "Each mode has its own zones, sensors and delays. \"Failed to arm\" is an event, not a state."
  - Pure domain module (`domain/alarm.py`), no I/O; every transition unit-tested.
  - Arming is allowed from `disarmed` or another armed mode; from `pending`/`triggered` the operator must disarm first.
  - `triggered` lasts `trigger_time`, then returns to the armed mode it came from (or `disarmed` when it was raised while disarmed).
- **S2 Policy.** "The trigger policy moves from `alert_ingest.py:SIREN_CONFIDENCE_THRESHOLD` into a domain policy: zone + mode + schedule + confidence. Tamper always alarms, except in maintenance mode."
  - A qualifying detection (intrusion ≥ 0.70) raises the alarm only when the mode arms the detection's zone; an immediate zone triggers at once, an entry zone starts the entry delay.
  - `tamper` raises the alarm in every state, disarmed included.
  - Assumption: schedules and maintenance mode are deferred (no schedule or maintenance source exists yet); zone configuration editing is deferred to Phase D, which adds zones to the Eyes. The default zone `perimeter` is immediate in every armed mode.
- **S3 Done.** "Done when: state machine unit tests cover every transition, and an alert while disarmed records an event but does not sound the siren."
- **S4 Arm/disarm.** "an arm/disarm panel with a PIN". Arm and disarm need an authenticated human with `can_control_hardware` plus the PIN; nodes and the system can never disarm. Every attempt (success, denied, failed to arm) is audited in `physical_action_log`. Disarming while `pending`/`triggered` silences the siren through the choke point.
- **S5 Supervision.** "Every device (Jetson, camera stream, ESP32, siren circuit) has a heartbeat with a timeout." "A missed heartbeat raises a `fault` event. It shows in the UI and goes to Telegram, but it does not trigger the siren."
  - Devices today: vision nodes (telemetry heartbeat) and the siren service (`/health`). ESP32 joins in Phase C.
  - Arming with an active fault is refused as a `failed_to_arm` event unless the operator forces it.
  - Phase A follow-up: the watchdog keeps alerting from a process-local copy when the state store is down.
- **S6 Timeline.** "a timeline of state transitions": transitions, faults and failed-to-arm events are stored and listed newest first.
- **S7 Fail toward safety.**
  - If the alarm store is unavailable during ingest, the legacy threshold decides (the siren still sounds).
  - The first state after deploy is `armed_away`, which keeps today's behavior (every qualifying intrusion sounds the siren) until an operator disarms.

## Tasks

| ID | Specs | Route | Status | Commit |
|---|---|---|---|---|
| B1 | S1, S2, S3 | inline | done (38 tests RED→GREEN) | see git log |
| B2 | S4, S6, S7 | inline | done (21 tests RED→GREEN, suite 477 passed) | see git log |
| B3 | S5 | inline (parallel with B4) | done (15 tests RED→GREEN) | see git log |
| B4 | S4, S5, S6 (UI) | writer (parallel with B3) | done (lint/tsc/build; no UI test runner, not browser-checked) | see git log |

## Log

- L1 (2026-11-14) user: "Sí, sigue con B" — continue with Phase B of the approved SARI v2 plan (`Phase B — Alarm state machine + supervision`).
- L2 design: alarm state is one row (`alarm_state`) changed under a row lock by API and worker; timeline in `alarm_event`; active faults in `alarm_fault`. The worker scheduler advances timers (exit delay end, entry delay → triggered, triggered → armed) and sounds the siren for an entry-delay expiry as a `system` actor that may only raise the siren.
- L3 RDD B1+B2 (`base b742b89`, lineage review-d8341848d23626f8, lenses risk/resilience/reliability): approved and acknowledged. Ten non-blocking advisories; fixed with RED tests: disarm survives a crashing siren adapter, an entry-delay siren that fails is retried while triggered, tamper sounds through the store-down fallback, re-arming while armed never opens an exit-delay window, `detection_ignored` rows limited to one per node per minute. Left as informational: any logged-in user may read the alarm status (dashboard monitors need it); invalid modes are rejected without an audit row.
- L4 B3: supervision supervises registered nodes (15 s) and the siren service `/health` (probe every 10 s, 15 s timeout). Faults go to `alarm_fault`, the timeline and the WebSocket (`alarm_fault`); Telegram only for non-node devices, because node loss already sends the watchdog's sabotage alert. The watchdog keeps an in-memory copy of node liveness (MQTT telemetry notes it before the store write), so it alerts during a store outage and does not mistake live nodes for sabotage; a reachable store stays authoritative.
- L5 B4: `AlarmPanel.tsx` in the Control tab (writer). Checks: `npm run lint` 0 errors (16 warnings, same as baseline), `npx tsc -b` ok, `npm run build` ok. Not exercised in a browser against a running backend.
- L6 Suite: `pytest tests/unit` 498 passed, 3 skipped; ruff clean.
