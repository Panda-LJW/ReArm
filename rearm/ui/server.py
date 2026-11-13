"""HTTP/WebSocket adapter; receives state exclusively from subscribed events."""
import asyncio
from copy import deepcopy
from pathlib import Path
from threading import RLock
from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response, StreamingResponse
import cv2
from rearm.interfaces import CommandController, EventBus, FrameSource
from rearm.types import Event, jsonable


def create_server(controller: CommandController, bus: EventBus, initial: dict,
                  camera: FrameSource | None = None, jpeg_quality: int | None = None) -> FastAPI:
    app = FastAPI(title="ReArm", docs_url=None, redoc_url=None)
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
    def index():
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})

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
