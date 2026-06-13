# Melodify TeamSpeak 3 Music Bot

Python orchestration layer for TeamSpeak music playback using:

- TeamSpeak 3 server
- TS3AudioBot for voice streaming
- `melodify-api` (`https://mel.meower1.dev`) for search + signed stream URLs

## What This Implements

- Chat commands in TeamSpeak:
  - `<prefix>mplay <query>`
  - `<prefix>pick <1-5>`
  - `<prefix>queue`
  - `<prefix>now`
  - `<prefix>skip`
  - `<prefix>stop`
  - `<prefix>loop off|inf|<duration>`
  - `<prefix>summon`
- Command transport is intentionally `private` and `server` chat modes for reliable multi-room handling.
- Command execution requires invoker and audio bot to be in the same voice channel (except offline summon flow).
- In-memory queue (single server context) with pending selection TTL (default 90s).
- One-track-ahead playback strategy (mint stream token only when about to play).
- Ops API:
  - `GET /health/live`
  - `GET /health/ready`
  - `GET /debug/state` (Bearer token)
  - `POST /debug/smoke-play` (Bearer token)
- Remote debug loop script:
  - `scripts/remote_debug_loop.sh`

## Stack Layout

The deployment is split into two components:

1. **Base Server (`docker-compose.yml`)**: Runs the core `teamspeak` service.
2. **Music Bot Extension (`musicbot.yml`)**: Runs `ts3audiobot` and `python-orchestrator`.

## Mirror-First Defaults (Iran)

`.env.example` and `bot/Dockerfile` already default to Iran-friendly mirrors:

- Python base image: `docker.arvancloud.ir/library/python:3.12-slim`
- TS3AudioBot apt mirror: `http://mirror.mobinhost.com/debian*`
- uv index: `https://mirror2.chabokan.net/pypi/simple/`
- uv fallback: `https://mirrors.pardisco.co/pip/simple/`

If your host uses Docker registry mirror/proxy, configure it at the Docker daemon level as needed.

## Setup

1. Copy env file:

```bash
cp .env.example .env
```

2. Fill required secrets in `.env`:

- `TS3_QUERY_PASSWORD`
- `MELODIFY_API_KEY`
- `OPS_DEBUG_TOKEN`

3. Optional TS3AudioBot bootstrap envs:

- `TS3AB_TS_HOST` / `TS3AB_TS_PORT`
- `TS3AB_BOT_NAME`
- `TS3AB_CHANNEL`

4. Runtime policy envs:

- `MIN_ACTIVE_USERS_IN_CHANNEL` (default: `1`)
- `SUMMON_ALLOWED_SERVER_GROUP_IDS` (default: `6`)

5. Start the server (standalone):

```bash
docker compose up -d --build
```

**Optional**: To start the server *with* the music bot extension seamlessly attached, run:

```bash
docker compose -f docker-compose.yml -f musicbot.yml up -d --build
```

6. Validate:

```bash
export DEBUG_BEARER_TOKEN="<OPS_DEBUG_TOKEN>"
./scripts/local_smoke.sh
```

7. Automated local debug suite (tests + TeamSpeak runtime smoke + logs):

```bash
./scripts/local_debug_suite.sh
```

## Remote Automated Debug Loop

```bash
export SSH_HOST="your.server"
export SSH_USER="meower1"
export SSH_PORT="22"
export SSH_PASSWORD="<ssh-password>"   # optional if key auth is not configured
export REMOTE_DIR="/home/meower1/teamspeak"
export DEBUG_BEARER_TOKEN="<OPS_DEBUG_TOKEN>"
export SMOKE_QUERY="shervin"
export COMPOSE_CMD="sudo docker compose"
./scripts/remote_debug_loop.sh
```

This script checks compose state, health endpoints, triggers smoke playback, dumps debug state, and tails bot logs.

## Tests

Inside `bot/`:

```bash
UV_INDEX_URL=https://mirror2.chabokan.net/pypi/simple/ \
UV_EXTRA_INDEX_URL=https://mirrors.pardisco.co/pip/simple/ \
uv sync --frozen
uv run pytest
```

Backend stream-token patch tests:

```bash
UV_INDEX_URL=https://mirror2.chabokan.net/pypi/simple/ uv run pytest ../backend_patch/tests
```

## Backend Stream Token Patch

`backend_patch/` contains a ready-to-embed token store and tests for the `melodify-api` side.

See:

- `backend_patch/README.md`
- `backend_patch/app/stream_tokens.py`

## Notes

- OTP/login remains manual on `melodify-api` as requested.
- If `melodify-api` session expires, bot keeps queue and reports auth failure.
- Queue is intentionally non-persistent in v1.
- TS3AudioBot API auth token is optional in this deployment (`TS3AB_USERNAME` / `TS3AB_PASSWORD` can be empty).
- If your backend does not expose `/v1/stream-token` yet, keep `MELODIFY_LEGACY_STREAM_FALLBACK=true`. The orchestrator will mint single-use relay URLs and fetch audio from `/v1/download/by-track-id`.

## Test Env Override

To run compose with an alternate orchestrator env file without changing `.env`:

```bash
ORCHESTRATOR_ENV_FILE=/absolute/path/to/test.env docker compose up -d --build
```
