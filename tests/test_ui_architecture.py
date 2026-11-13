import ast
import asyncio
import json
from pathlib import Path
from rearm.app import build_app
from rearm.ui.server import create_server


def request(app,path,method="GET",payload=None):
    async def run():
        messages=[]
        body=json.dumps(payload or {}).encode()
        async def receive(): return {"type":"http.request","body":body,"more_body":False}
        async def send(message): messages.append(message)
        await app({"type":"http","asgi":{"version":"3.0","spec_version":"2.4"},"http_version":"1.1","method":method,
                   "scheme":"http","path":path,"raw_path":path.encode(),"query_string":b"",
                   "headers":[(b"content-type",b"application/json")],"server":("localhost",8000),"client":("test",0)},receive,send)
        status=next(m["status"] for m in messages if m["type"]=="http.response.start")
        return status,b"".join(m.get("body",b"") for m in messages if m["type"]=="http.response.body")
    return asyncio.run(run())


def test_http_state_commands_and_static(config,tmp_path):
    controller=build_app(config,tmp_path)
    server=create_server(controller,controller.bus,controller.snapshot())
    assert request(server,"/")[0]==200
    assert b"WebSocket" in request(server,"/")[1]
    status,body=request(server,"/api/state")
    assert status==200 and json.loads(body)["head"]["id"]=="v0001"
    assert request(server,"/api/command/inject","POST",{"kind":"j1","amount":1})[0]==200
    status,body=request(server,"/api/command/selfcheck","POST",{})
    assert status==200 and json.loads(body)["head"]["id"]!="v0001"
    assert request(server,"/api/command/unknown","POST",{})[0]==400
    assert request(server,"/docs")[0]==404


def test_websocket_event_stream_and_disconnect(config,tmp_path):
    controller=build_app(config,tmp_path)
    app=create_server(controller,controller.bus,controller.snapshot())
    async def run():
        received=[]; incoming=asyncio.Queue()
        await incoming.put({"type":"websocket.connect"})
        async def receive(): return await incoming.get()
        async def send(message):
            received.append(message)
            if message["type"]=="websocket.send":
                data=json.loads(message["text"])
                if data["kind"]=="snapshot": controller.transition(controller.state)
                if data["kind"]=="state": await incoming.put({"type":"websocket.disconnect","code":1000})
        await asyncio.wait_for(app({"type":"websocket","asgi":{"version":"3.0"},"scheme":"ws","path":"/ws",
             "raw_path":b"/ws","query_string":b"","headers":[],"client":("test",0),"server":("localhost",8000),"subprotocols":[]},receive,send),5)
        kinds=[json.loads(m["text"])["kind"] for m in received if m["type"]=="websocket.send"]
        assert "snapshot" in kinds and "state" in kinds
    asyncio.run(run())


def test_module_boundaries():
    root=Path(__file__).resolve().parents[1]/"rearm"
    for path in root.rglob("*.py"):
        if path.relative_to(root).as_posix() in ("app.py","evo/controller.py"):
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith("rearm."):
                assert node.module in ("rearm.types","rearm.interfaces") or (path.name=="server.py" and node.module=="rearm.app"), (path,node.module)
            if isinstance(node,(ast.ClassDef,)) and any(isinstance(d,ast.Name) and d.id=="dataclass" or isinstance(d,ast.Call) and isinstance(d.func,ast.Name) and d.func.id=="dataclass" for d in node.decorator_list):
                assert path.name=="types.py"
