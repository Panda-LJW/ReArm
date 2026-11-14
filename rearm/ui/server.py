"""HTTP/WebSocket adapter; receives state exclusively from subscribed events."""
import asyncio
from copy import deepcopy
from http.client import HTTPConnection, HTTPSConnection, HTTPException as HTTPError
from ipaddress import ip_address, ip_network
import json
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit
from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response, StreamingResponse
import cv2
from rearm.interfaces import CommandController, EventBus, FrameSource
from rearm.types import Event, jsonable


def validate_backend_url(value: str) -> str:
    """Accept an origin using localhost or a literal loopback/LAN address only."""
    message = "--backend 地址无效：仅支持 http/https 的 localhost、本机或局域网 IP，可带端口，不能带账号、路径、查询或片段"
    try:
        url = urlsplit(value)
        if (url.scheme not in {"http", "https"} or not url.hostname
                or url.username is not None or url.password is not None
                or url.path not in {"", "/"} or "?" in value or "#" in value
                or any(c.isspace() or ord(c) < 32 for c in value)
                or "%" in value or url.netloc.endswith(":")
                or (url.port is not None and not 1 <= url.port <= 65535)):
            raise ValueError(message)
        host = url.hostname
        if host != "localhost":
            address = ip_address(host)
            lan = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
            if not (address.is_loopback or address.is_link_local
                    or any(address in ip_network(network) for network in lan)):
                raise ValueError(message)
        authority = f"[{host}]" if ":" in host else host
        if url.port is not None:
            authority += f":{url.port}"
        if url.netloc.lower() != authority:
            raise ValueError(message)
        return f"{url.scheme}://{authority}"
    except ValueError as error:
        raise ValueError(message) from error


def _backend_error(error: Exception, timeout: float) -> HTTPException:
    reason = f"请求超时（{timeout:g} 秒）" if isinstance(error, TimeoutError) else f"连接或响应失败：{error}"
    return HTTPException(status_code=502, detail=f"后端{reason}")


def _open_backend(backend: str, path: str, timeout: float, body: bytes | None = None):
    url = urlsplit(backend)
    connection = (HTTPSConnection if url.scheme == "https" else HTTPConnection)(
        url.hostname, url.port, timeout=timeout)
    try:
        # Fixed paths, no redirects, environment proxies, cookies or browser credentials.
        connection.request("POST" if body is not None else "GET", path, body=body,
                           headers={"Content-Type": "application/json"} if body is not None else {})
        upstream = connection.getresponse()
        if 300 <= upstream.status < 400:
            upstream.close()
            raise HTTPException(status_code=502, detail="后端返回重定向，已拒绝转发")
        return connection, upstream
    except BaseException:
        connection.close()
        raise


def _backend_headers(upstream) -> dict:
    headers = {"Cache-Control": "no-store"}
    for name in ("Content-Type", "Content-Encoding"):
        if value := upstream.getheader(name):
            headers[name] = value
    return headers


def _read_backend(backend: str, path: str, timeout: float, body: bytes | None = None):
    try:
        connection, upstream = _open_backend(backend, path, timeout, body)
        try:
            return Response(upstream.read(), status_code=upstream.status, headers=_backend_headers(upstream))
        finally:
            upstream.close()
            connection.close()
    except (OSError, HTTPError) as error:
        raise _backend_error(error, timeout) from error


class _BackendStream(StreamingResponse):
    """Own the upstream until the ASGI response ends, including failed sends."""

    def __init__(self, request: Request, connection, upstream, first: bytes):
        self.connection, self.upstream = connection, upstream

        async def chunks():
            chunk = first
            while chunk and not await request.is_disconnected():
                yield chunk
                if await request.is_disconnected():
                    break
                try:
                    # read1 returns available bytes without waiting to fill 64 KiB.
                    # The worker is bounded by the socket timeout and never detached.
                    chunk = await run_in_threadpool(upstream.read1, 65536)
                except (OSError, HTTPError):
                    # Headers are already sent; a mid-stream failure ends the stream.
                    break

        super().__init__(chunks(), status_code=upstream.status,
                         headers=_backend_headers(upstream) | {"X-Accel-Buffering": "no"})

    def close(self):
        self.upstream.close()
        self.connection.close()

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Outside StreamingResponse's disconnect cancellation scope, wait for cleanup.
            await run_in_threadpool(self.close)


def _stream_backend(backend: str, request: Request):
    timeout = 2
    try:
        connection, upstream = _open_backend(backend, "/api/camera/color.mjpg", timeout)
        try:
            if upstream.status != 200:
                response = Response(upstream.read(), status_code=upstream.status, headers=_backend_headers(upstream))
                upstream.close()
                connection.close()
                return response
            # Fetch the first bytes before committing 200 so initial timeouts return 502.
            first = upstream.read1(65536)
            return _BackendStream(request, connection, upstream, first)
        except BaseException:
            upstream.close()
            connection.close()
            raise
    except (OSError, HTTPError) as error:
        raise _backend_error(error, timeout) from error


def create_server(controller: CommandController, bus: EventBus, initial: dict,
                  camera: FrameSource | None = None, jpeg_quality: int | None = None,
                  backend: str | None = None) -> FastAPI:
    if backend is not None:
        backend = validate_backend_url(backend)
    app = FastAPI(title="ReArm", docs_url=None, redoc_url=None)
    if backend is not None:
        @app.get("/backend/api/state")
        async def backend_state():
            return await run_in_threadpool(_read_backend, backend, "/api/state", 2)

        @app.get("/backend/api/vision/overlay.jpg")
        async def backend_overlay():
            return await run_in_threadpool(_read_backend, backend, "/api/vision/overlay.jpg", 2)

        @app.get("/backend/api/camera/color.mjpg")
        async def backend_camera(request: Request):
            return await run_in_threadpool(_stream_backend, backend, request)

        @app.post("/backend/api/cmd")
        async def backend_command(request: Request):
            def invalid_constant(value):
                raise ValueError(f"非法 JSON 常量：{value}")

            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 4096:
                    raise HTTPException(status_code=413, detail="指令 JSON 不能超过 4096 字节")
                body.extend(chunk)
            try:
                payload = json.loads(body, parse_constant=invalid_constant)
            except (ValueError, UnicodeError, RecursionError) as error:
                raise HTTPException(status_code=400, detail="指令必须是合法的 JSON") from error
            if not isinstance(payload, dict) or payload.get("action") != "estop":
                raise HTTPException(status_code=403, detail="第一档只读：该指令未开放")
            return await run_in_threadpool(_read_backend, backend, "/api/cmd", 5, bytes(body))

    view, lock, listeners = deepcopy(initial), RLock(), []
    # Recent notable events for the panel feed; kept across snapshots.
    feed_kinds = {"alarm", "switch", "version_committed", "rejected", "rollback", "retrained", "damage_injected", "manual_switch", "estop", "estop_reset"}
    view["events"] = []

    def consume(event: Event):
        nonlocal view
        with lock:
            if event.kind == "snapshot":
                snapshot = deepcopy(event.data["snapshot"])
                # Safety/operation events may overtake a workflow's snapshot copy.
                # Their live values remain authoritative, including for reconnects.
                live = {k: view[k] for k in ("estop", "laser_on", "estop_error", "busy", "active_command") if k in view}
                # Keep static display settings (camera geometry, limits) that snapshots do not carry.
                view = {k: v for k, v in initial.items() if k not in snapshot} | snapshot | live | {"events": view.get("events", [])}
            elif event.kind == "state":
                view.update(event.data)
            elif event.kind == "shot":
                view["recent"] = (view.get("recent", []) + [event.data["shot"]])[-initial["history_limit"]:]
                view["shots"] = view.get("shots", 0) + 1
            elif event.kind == "diagnosis":
                view["diagnosis"] = event.data["diagnosis"]
            elif event.kind == "preview":
                view["preview"] = event.data["preview"]
            elif event.kind in {"estop", "estop_reset", "safety", "laser", "operation"}:
                view.update(event.data)
            if event.kind in feed_kinds:
                view["events"] = (view["events"] + [jsonable(event)])[-initial["history_limit"]:]
            for loop, queue in tuple(listeners):
                message = jsonable(event)
                if event.kind == "snapshot":
                    message["data"]["snapshot"] = deepcopy(view)
                def deliver(q=queue, message=message):
                    if q.full():
                        q.get_nowait()
                    q.put_nowait(message)
                if not loop.is_closed():
                    loop.call_soon_threadsafe(deliver)
    unsubscribe = bus.subscribe(consume)
    app.state.unsubscribe = unsubscribe
    static = Path(__file__).parent / "static"

    @app.get("/static/{filename:path}")
    def static_file(filename: str):
        path = (static / filename).resolve()
        if not path.is_relative_to(static.resolve()) or not path.is_file():
            raise HTTPException(status_code=404, detail="static file not found")
        return FileResponse(path, headers={"Cache-Control": "no-cache"})

    @app.get("/")
    def index(request: Request):
        filename = "index.html" if request.query_params.get("legacy") == "1" else "console.html"
        return FileResponse(static / filename, headers={"Cache-Control": "no-cache"})

    camera_lock = RLock()

    def encode_frame():
        with camera_lock:
            ok, encoded = cv2.imencode(".jpg", camera.read(), [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality or 80])
        if not ok:
            raise HTTPException(status_code=500, detail="frame encoding failed")
        return encoded.tobytes()

    @app.get("/api/camera.jpg")
    def camera_frame():
        if camera is None:
            raise HTTPException(status_code=404, detail="no camera attached")
        return Response(encode_frame(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/camera.mjpg")
    async def camera_stream(request: Request):
        if camera is None:
            raise HTTPException(status_code=404, detail="no camera attached")

        async def frames():
            while not await request.is_disconnected():
                # FastAPI's worker waits for its current read even on disconnect;
                # there is no detached producer or per-client background thread.
                frame = await run_in_threadpool(encode_frame)
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
                await asyncio.sleep(0.2)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @app.get("/api/fault-codes")
    def fault_codes():
        path = Path(__file__).resolve().parents[2] / "docs" / "故障码.md"
        if not path.exists():
            raise HTTPException(status_code=404, detail="fault code document missing")
        return Response(path.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")

    @app.get("/api/state")
    def state():
        with lock:
            return deepcopy(view)

    @app.post("/api/command/{name}")
    async def command(name: str, payload: dict = Body(default_factory=dict)):
        try:
            return await asyncio.to_thread(controller.command, name, payload)
        except FileNotFoundError as error:
            raise HTTPException(status_code=400, detail="required data file not found") from error
        except KeyError as error:
            raise HTTPException(status_code=400, detail="required field missing: " + str(error.args[0])) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.websocket("/ws")
    async def websocket(socket: WebSocket):
        await socket.accept()
        queue = asyncio.Queue(maxsize=initial["history_limit"])
        listener = (asyncio.get_running_loop(), queue)
        with lock:
            listeners.append(listener)
            snapshot = deepcopy(view)
        await socket.send_json({"kind": "snapshot", "data": {"snapshot": snapshot}})
        async def send_events():
            while True:
                await socket.send_json(await queue.get())
        async def receive_close():
            while True:
                await socket.receive_text()
        sender, receiver = asyncio.create_task(send_events()), asyncio.create_task(receive_close())
        try:
            done, _ = await asyncio.wait([sender, receiver], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            sender.cancel()
            receiver.cancel()
            await asyncio.gather(sender, receiver, return_exceptions=True)
            with lock:
                listeners.remove(listener)
    return app


if __name__ == "__main__":
    # CLI delegates assembly to the designated composition root.
    from rearm.app import serve_ui
    serve_ui()
