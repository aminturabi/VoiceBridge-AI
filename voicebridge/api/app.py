"""FastAPI application: meeting UI + WebSocket event stream + control API.

Endpoints:
* ``GET  /``            -> two-participant meeting UI (static HTML).
* ``GET  /api/info``    -> pipeline + backend status.
* ``POST /api/start``   -> start a call (body: my_lang, other_lang, source).
* ``POST /api/stop``    -> stop the call.
* ``WS   /ws``          -> stream of PipelineEvents as JSON.
* ``GET  /media/...``   -> generated TTS/lip-sync files (audio/video).

The pipeline runs in background threads; the broker marshals its events onto
the asyncio loop for the WebSocket handlers.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from voicebridge.api.broker import EventBroker
from voicebridge.config import Config, load_config
from voicebridge.logging_conf import configure_logging, get_logger
from voicebridge.pipeline.orchestrator import Orchestrator

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class StartRequest(BaseModel):
    my_language: str | None = None
    other_language: str | None = None
    # "microphone" for a live call, or "wav" (with wav_path) for a demo.
    source_kind: str = "microphone"
    wav_path: str | None = None
    # If true, register both directions (two-way call). Else one-way.
    two_way: bool = True


def create_app(config: Config | None = None) -> FastAPI:
    config = config or load_config()
    configure_logging(config.get("logging.level", "INFO"), config.get("logging.file", None))

    broker = EventBroker()
    state: dict = {"orchestrator": None}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        broker.bind_loop(asyncio.get_running_loop())
        try:
            yield
        finally:
            orch = state["orchestrator"]
            if orch and orch.is_running:
                await asyncio.to_thread(orch.stop)

    app = FastAPI(title=config.get("app.name", "VoiceBridge AI"), lifespan=lifespan)

    # Serve generated media (audio + lip-sync clips) so the UI can play them.
    output_dir = config.path("app.output_dir")
    output_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(output_dir)), name="media")
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def _media_url(path_str: str) -> str:
        """Rewrite an absolute generated-file path to a /media URL."""
        if not path_str:
            return ""
        try:
            rel = Path(path_str).resolve().relative_to(output_dir.resolve())
            return f"/media/{rel.as_posix()}"
        except ValueError:
            return ""  # outside the served dir (e.g. a static face asset)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return HTMLResponse(index_file.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>VoiceBridge AI</h1><p>UI not found.</p>")

    @app.get("/api/info")
    async def info() -> JSONResponse:
        orch = state["orchestrator"]
        data = {
            "app": config.get("app.name", "VoiceBridge AI"),
            "languages": {
                k: v.get("display_name", k) for k, v in config.languages.items()
            },
            "defaults": config.get("defaults", {}),
            "pipeline": orch.info if orch else {"running": False},
        }
        return JSONResponse(data)

    @app.post("/api/start")
    async def start(req: StartRequest) -> JSONResponse:
        if state["orchestrator"] and state["orchestrator"].is_running:
            return JSONResponse({"error": "already running"}, status_code=409)

        my_lang = req.my_language or config.get("defaults.my_language", "en")
        other_lang = req.other_language or config.get("defaults.other_language", "ar")

        orch = Orchestrator(config, emit=broker.publish)
        # Direction 1: I speak my_lang -> other hears other_lang.
        orch.add_direction(
            source_lang=my_lang, target_lang=other_lang, speaker="me",
            source_kind=req.source_kind, wav_path=req.wav_path,
        )
        # Direction 2 (two-way): other speaks other_lang -> I hear my_lang.
        if req.two_way and req.source_kind == "microphone":
            orch.add_direction(
                source_lang=other_lang, target_lang=my_lang, speaker="other",
                source_kind="microphone",
            )
        orch.start()
        state["orchestrator"] = orch
        return JSONResponse({"status": "started", "info": orch.info})

    @app.post("/api/stop")
    async def stop() -> JSONResponse:
        orch = state["orchestrator"]
        if not orch or not orch.is_running:
            return JSONResponse({"status": "not running"})
        # stop() joins threads; run off the event loop.
        await asyncio.to_thread(orch.stop)
        state["orchestrator"] = None
        return JSONResponse({"status": "stopped"})

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        queue_ = await broker.subscribe()
        # Replay recent history so a fresh tab isn't blank.
        for payload in broker.history[-20:]:
            await websocket.send_json(_with_media_urls(payload, _media_url))
        try:
            while True:
                payload = await queue_.get()
                await websocket.send_json(_with_media_urls(payload, _media_url))
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        finally:
            broker.unsubscribe(queue_)

    return app


def _with_media_urls(payload: dict, media_url) -> dict:
    """Rewrite absolute file paths in an event payload to /media URLs."""
    out = dict(payload)
    if out.get("audio_url"):
        out["audio_url"] = media_url(out["audio_url"])
    if out.get("video_url"):
        out["video_url"] = media_url(out["video_url"])
    return out


app = create_app()
