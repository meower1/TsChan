from __future__ import annotations

import logging
import hmac
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from .errors import MelodifyAuthError, MelodifyError, TS3AudioBotError
from .logging_utils import set_request_id
from .melodify_client import MelodifyClient
from .queue_manager import PlaybackCoordinator
from .stream_proxy import StreamRelayGone, StreamRelayStore
from .ts3audiobot_client import TS3AudioBotClient

LOGGER = logging.getLogger(__name__)


def create_ops_app(
    *,
    coordinator: PlaybackCoordinator,
    melodify: MelodifyClient,
    ts3audiobot: TS3AudioBotClient,
    debug_token: str,
    smoke_default_query: str,
    stream_relay: StreamRelayStore | None = None,
) -> FastAPI:
    app = FastAPI(title="Melodify TS3 Bot Ops", version="1.0.0")

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            set_request_id(None)
        response.headers["X-Request-ID"] = request_id
        return response

    async def require_debug_token(authorization: str | None = Header(default=None)) -> None:
        expected = f"Bearer {debug_token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid debug token",
            )

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready() -> JSONResponse:
        melodify_health_ok = await melodify.health()
        melodify_search_ok = False
        if melodify_health_ok:
            try:
                await melodify.search_tracks(smoke_default_query, limit=1)
                melodify_search_ok = True
            except MelodifyAuthError:
                melodify_search_ok = False
            except MelodifyError:
                melodify_search_ok = False
        ts3ab_ok = await ts3audiobot.readiness()

        state = await coordinator.state_snapshot()
        ready = bool(
            melodify_health_ok and melodify_search_ok and ts3ab_ok and state.get("ts_connected")
        )
        payload = {
            "ready": ready,
            "checks": {
                "melodify_health": melodify_health_ok,
                "melodify_search": melodify_search_ok,
                "ts3audiobot_webapi": ts3ab_ok,
                "teamspeak_query_connected": bool(state.get("ts_connected")),
            },
            "last_error": state.get("last_error"),
        }
        return JSONResponse(status_code=200 if ready else 503, content=payload)

    @app.get("/debug/state", dependencies=[Depends(require_debug_token)])
    async def debug_state() -> dict:
        return await coordinator.state_snapshot()

    @app.post("/debug/smoke-play", dependencies=[Depends(require_debug_token)])
    async def debug_smoke_play(payload: dict | None = None) -> dict:
        query = smoke_default_query
        if payload and isinstance(payload.get("query"), str) and payload["query"].strip():
            query = payload["query"].strip()

        try:
            queued = await coordinator.smoke_enqueue_first_result(query)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except MelodifyAuthError as exc:
            raise HTTPException(status_code=502, detail=f"Melodify auth error: {exc}") from exc
        except (MelodifyError, TS3AudioBotError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        LOGGER.info("smoke play enqueued", extra={"event": "smoke_play", "track_id": queued.track_id})
        return {
            "status": "queued",
            "query": query,
            "track": {
                "track_id": queued.track_id,
                "title": queued.title,
                "artist": queued.artist,
                "quality": queued.quality,
            },
        }

    @app.get("/internal/stream/{token}")
    async def internal_stream(token: str) -> Response:
        if stream_relay is None:
            raise HTTPException(status_code=404, detail="Stream relay disabled")
        try:
            grant = await stream_relay.consume(token)
        except StreamRelayGone as exc:
            LOGGER.warning("relay token rejected: %s", exc)
            raise HTTPException(status_code=410, detail=str(exc)) from exc

        try:
            content, content_type, content_disposition = await melodify.download_by_track_id(
                track_id=grant.track_id,
                quality=grant.quality,
            )
        except MelodifyAuthError as exc:
            raise HTTPException(status_code=502, detail=f"Melodify auth error: {exc}") from exc
        except MelodifyError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        LOGGER.info(
            "relay stream served",
            extra={
                "event": "relay_stream",
                "track_id": grant.track_id,
                "quality": grant.quality,
                "used_count": grant.used_count,
                "max_uses": grant.max_uses,
                "bytes": len(content),
            },
        )
        headers: dict[str, str] = {}
        if content_disposition:
            headers["Content-Disposition"] = content_disposition
        return Response(
            content=content,
            media_type=content_type or "audio/mpeg",
            headers=headers,
        )

    return app
