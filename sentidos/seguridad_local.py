"""Origin guards for the local gateway.

The gateway only serves this machine (GUI on 127.0.0.1:8000, Vision Studio on Vite/Tauri). Any web page the
user visits can still reach it from the browser, so:

- CORS only exposes responses to local origins.
- State-changing HTTP requests from foreign origins are rejected. CORS alone does not stop them: "simple"
  requests (e.g. text/plain POST) skip the preflight and still reach the handler.
- WebSockets are not covered by CORS at all, so the handshake Origin is checked explicitly.

Requests without an Origin header (curl, scripts, other local services) are allowed: browsers always send it
on cross-origin requests and WebSocket handshakes.
"""

import re

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

LOCAL_ORIGIN_REGEX = r"^(https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?|tauri://localhost|https?://tauri\.localhost)$"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
POLICY_VIOLATION = 1008


def origin_allowed(origin: str | None) -> bool:
    return origin is None or re.fullmatch(LOCAL_ORIGIN_REGEX, origin) is not None


def install_local_origin_guards(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=LOCAL_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def reject_cross_site_writes(request: Request, call_next):
        if request.method not in SAFE_METHODS and not origin_allowed(request.headers.get("origin")):
            return JSONResponse(
                status_code=403, content={"status": "error", "message": "Cross-origin request rejected."}
            )
        return await call_next(request)


async def accept_local_websocket(websocket: WebSocket) -> bool:
    """Accept the handshake only from local origins; close with 1008 otherwise."""
    if not origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=POLICY_VIOLATION)
        return False
    await websocket.accept()
    return True
