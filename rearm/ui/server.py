"""HTTP/WebSocket adapter; receives state exclusively from subscribed events."""
import asyncio
from copy import deepcopy
from pathlib import Path
from threading import RLock
from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from rearm.interfaces import CommandController, EventBus
from rearm.types import Event, jsonable


def create_server(controller: CommandController, bus: EventBus, initial: dict) -> FastAPI:
    app = FastAPI(title="ReArm", docs_url=None, redoc_url=None)
    view, lock, listeners = deepcopy(initial), RLock(), []

    def consume(event: Event):
        nonlocal view
        with lock:
            if event.kind == "snapshot":
                view = deepcopy(event.data["snapshot"])
            elif event.kind == "state":
                view["state"] = event.data["state"]
            elif event.kind == "shot":
                view["recent"] = (view.get("recent", []) + [event.data["shot"]])[-initial["history_limit"]:]
                view["shots"] = view.get("shots", 0) + 1
            elif event.kind == "diagnosis":
                view["diagnosis"] = event.data["diagnosis"]
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
