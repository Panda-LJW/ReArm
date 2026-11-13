"""HTTP/WebSocket adapter; receives state exclusively from subscribed events."""
import asyncio
from copy import deepcopy
from pathlib import Path
from threading import RLock
from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
import cv2
from rearm.interfaces import CommandController, EventBus, FrameSource
from rearm.types import Event, jsonable


def create_server(controller: CommandController, bus: EventBus, initial: dict,
                  camera: FrameSource | None = None, jpeg_quality: int | None = None) -> FastAPI:
    app = FastAPI(title="ReArm", docs_url=None, redoc_url=None)
    view, lock, listeners = deepcopy(initial), RLock(), []
    # Recent notable events for the panel feed; kept across snapshots.
    feed_kinds = {"alarm", "switch", "version_committed", "rejected", "rollback", "retrained", "damage_injected", "manual_switch"}
    view["events"] = []

    def consume(event: Event):
        nonlocal view
        with lock:
            if event.kind == "snapshot":
                snapshot = deepcopy(event.data["snapshot"])
                # Keep static display settings (camera geometry, limits) that snapshots do not carry.
                view = {k: v for k, v in initial.items() if k not in snapshot} | snapshot | {"events": view.get("events", [])}
            elif event.kind == "state":
                view["state"] = event.data["state"]
            elif event.kind == "shot":
                view["recent"] = (view.get("recent", []) + [event.data["shot"]])[-initial["history_limit"]:]
                view["shots"] = view.get("shots", 0) + 1
            elif event.kind == "diagnosis":
                view["diagnosis"] = event.data["diagnosis"]
            elif event.kind in feed_kinds:
                view["events"] = (view["events"] + [jsonable(event)])[-initial["history_limit"]:]
            elif event.kind == "preview":
                view["preview"] = event.data["preview"]
            for loop, queue in tuple(listeners):
                def deliver(q=queue, message=jsonable(event)):
                    if q.full():
                        q.get_nowait()
                    q.put_nowait(message)
                if not loop.is_closed():
                    loop.call_soon_threadsafe(deliver)
    unsubscribe = bus.subscribe(consume)
    app.state.unsubscribe = unsubscribe

    @app.get("/")
    def index():
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/api/camera.jpg")
    def camera_frame():
        if camera is None:
            raise HTTPException(status_code=404, detail="no camera attached")
        ok, encoded = cv2.imencode(".jpg", camera.read(), [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        if not ok:
            raise HTTPException(status_code=500, detail="frame encoding failed")
        return Response(encoded.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})

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
        except (ValueError, KeyError, FileNotFoundError) as error:
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
