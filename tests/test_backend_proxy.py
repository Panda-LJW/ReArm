"""Read-only backend proxy against a real, local stdlib HTTP server."""
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from threading import Event, Thread, current_thread
from types import SimpleNamespace
from urllib.parse import urlsplit

import cv2
import numpy as np
import pytest
from starlette.requests import ClientDisconnect

from rearm.app import serve_ui
from rearm.logging.bus import LocalEventBus
from rearm.ui import server as proxy


STATE = Path(__file__).with_name("fixtures").joinpath("backend_state_r61.json").read_bytes()
JPEG = cv2.imencode(".jpg", np.zeros((2, 2, 3), dtype=np.uint8))[1].tobytes()
FRAME = (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
         + str(len(JPEG)).encode() + b"\r\n\r\n" + JPEG + b"\r\n")
ROUTES = [
    ("GET", "/backend/api/state"),
    ("GET", "/backend/api/camera/color.mjpg"),
    ("GET", "/backend/api/vision/overlay.jpg"),
    ("POST", "/backend/api/cmd"),
]


@pytest.fixture
def upstream():
    state = SimpleNamespace(requests=[], commands=[], status=200, delay_headers=False,
                            delay_body=False, stream_open=False, entered=Event(),
                            release=Event(), closed=Event())

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            state.commands.append((raw, dict(self.headers)))
            self.respond()

        def respond(self):
            state.requests.append((self.command, self.path, dict(self.headers)))
            state.entered.set()
            try:
                if state.delay_headers:
                    assert state.release.wait(8)
                body, content_type = {
                    "/api/state": (STATE, "application/json; charset=utf-8"),
                    "/api/cmd": (b'{"ok":true}', "application/json"),
                    "/api/vision/overlay.jpg": (JPEG, "image/jpeg"),
                    "/api/camera/color.mjpg": (FRAME, "multipart/x-mixed-replace; boundary=frame"),
                }[self.path]
                self.send_response(state.status)
                self.send_header("Content-Type", content_type)
                self.send_header("Set-Cookie", "upstream-secret=hidden")
                if state.status == 302:
                    self.send_header("Location", "/api/cmd?action=enable")
                streaming = state.stream_open and self.path.endswith(".mjpg")
                if not streaming:
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if state.delay_body:
                    assert state.release.wait(8)
                self.wfile.write(body)
                self.wfile.flush()
                if streaming:
                    self.connection.settimeout(6)
                    assert self.connection.recv(1) == b"", "proxy must close the upstream socket"
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                state.closed.set()

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    state.url = f"http://127.0.0.1:{server.server_port}"
    state.server = server
    try:
        yield state
    finally:
        state.release.set()
        server.shutdown()
        server.server_close()
        thread.join(8)
        assert not thread.is_alive()


def app(backend=None):
    return proxy.create_server(None, LocalEventBus(), {"history_limit": 10}, backend=backend)


def scope(path, method="GET", headers=(), spec="2.4"):
    url = urlsplit(path)
    return {"type": "http", "asgi": {"version": "3.0", "spec_version": spec},
            "http_version": "1.1", "method": method, "scheme": "http",
            "path": url.path, "query_string": url.query.encode(), "headers": list(headers)}


def request(application, path, method="GET", body=b"", headers=(), chunks=None):
    async def run():
        incoming = asyncio.Queue()
        parts = chunks if chunks is not None else [body]
        for i, part in enumerate(parts):
            incoming.put_nowait({"type": "http.request", "body": part, "more_body": i < len(parts) - 1})
        messages = []

        async def send(message):
            messages.append(message)

        await asyncio.wait_for(application(scope(path, method, headers), incoming.get, send), 7)
        start = next(m for m in messages if m["type"] == "http.response.start")
        return (start["status"], b"".join(m.get("body", b"") for m in messages), dict(start["headers"]))
    return asyncio.run(run())


def test_estop_reaches_backend_with_only_original_json(upstream, monkeypatch):
    # A direct HTTPConnection must also ignore proxy settings from the environment.
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    body = '{ "action": "estop", "note": "测试急停" }'.encode()
    status, result, headers = request(app(upstream.url), "/backend/api/cmd?ignored=1", "POST", body,
        [(b"cookie", b"session=secret"), (b"authorization", b"Bearer secret"),
         (b"proxy-authorization", b"Basic secret"), (b"x-extra", b"secret")])
    assert status == 200 and json.loads(result) == {"ok": True}
    received, forwarded = upstream.commands[0]
    assert received == body
    assert forwarded["Content-Type"] == "application/json"
    assert not {"cookie", "authorization", "proxy-authorization", "x-extra"} & {k.lower() for k in forwarded}
    assert upstream.requests[0][:2] == ("POST", "/api/cmd")
    assert b"set-cookie" not in headers


@pytest.mark.parametrize("payload", [{"action": "enable"}, {"action": "pick"}, {"action": "reset_estop"},
    {"action": "ESTOP"}, {"action": None}, {"action": ["estop"]}, {}, [], "estop"])
def test_other_commands_never_reach_backend(upstream, payload):
    status, body, _ = request(app(upstream.url), "/backend/api/cmd", "POST", json.dumps(payload).encode())
    assert status == 403 and json.loads(body)["detail"] == "第一档只读：该指令未开放"
    assert not upstream.requests and not upstream.commands


@pytest.mark.parametrize("method,path", ROUTES)
def test_unconfigured_routes_are_not_registered(method, path):
    assert request(app(), path, method, b'{"action":"estop"}')[0] == 404


@pytest.mark.parametrize("method,path", [("GET", "/backend/api/camera/depth.mjpg"),
    ("POST", "/backend/api/command/enable"), ("GET", "/backend/anything")])
def test_only_whitelisted_paths_exist(upstream, method, path):
    assert request(app(upstream.url), path, method)[0] == 404
    assert not upstream.requests


@pytest.mark.parametrize("method,path", ROUTES)
def test_closed_upstream_returns_chinese_502(upstream, method, path):
    upstream.server.shutdown()
    upstream.server.server_close()
    status, body, _ = request(app(upstream.url), path, method, b'{"action":"estop"}')
    assert status == 502 and "后端连接或响应失败" in json.loads(body)["detail"]


def test_state_bytes_and_content_type_are_unchanged(upstream):
    status, body, headers = request(app(upstream.url), "/backend/api/state?ignored=1")
    assert status == 200 and body == STATE
    assert headers[b"content-type"] == b"application/json; charset=utf-8"
    assert upstream.requests[0][:2] == ("GET", "/api/state")


def test_overlay_and_upstream_error_statuses(upstream):
    application = app(upstream.url)
    status, body, headers = request(application, "/backend/api/vision/overlay.jpg")
    assert status == 200 and body == JPEG and headers[b"content-type"] == b"image/jpeg"
    for code, path in [(404, "/backend/api/vision/overlay.jpg"), (503, "/backend/api/camera/color.mjpg")]:
        upstream.status = code
        assert request(application, path)[0] == code


def test_redirect_is_not_followed(upstream):
    upstream.status = 302
    status, body, headers = request(app(upstream.url), "/backend/api/state")
    assert status == 502 and "重定向" in json.loads(body)["detail"]
    assert b"location" not in headers and len(upstream.requests) == 1 and not upstream.commands


def test_cmd_size_limit_includes_chunked_body(upstream):
    application = app(upstream.url)
    exact = b'{"action":"estop","padding":"' + b"x" * 4065 + b'"}'
    exact += b" " * (4096 - len(exact))
    assert len(exact) == 4096
    assert request(application, "/backend/api/cmd", "POST", exact)[0] == 200
    for chunks in ([exact + b" "], [exact[:100], exact[100:], b" "]):
        status, body, _ = request(application, "/backend/api/cmd", "POST", chunks=chunks)
        assert status == 413 and "4096 字节" in json.loads(body)["detail"]
    assert len(upstream.commands) == 1


@pytest.mark.parametrize("body", [b"", b"not json", b'{"action":', b"\xff", b'{"action":"estop","value":NaN}'])
def test_invalid_json_is_not_forwarded(upstream, body):
    status, result, _ = request(app(upstream.url), "/backend/api/cmd", "POST", body)
    assert status == 400 and "JSON" in json.loads(result)["detail"]
    assert not upstream.commands


@pytest.mark.parametrize("method,path,seconds,delay", [
    ("GET", "/backend/api/state", 2, "delay_headers"),
    ("GET", "/backend/api/state", 2, "delay_body"),
    ("POST", "/backend/api/cmd", 5, "delay_headers"),
    ("GET", "/backend/api/camera/color.mjpg", 2, "delay_body"),
])
def test_upstream_timeouts_are_chinese_502(upstream, method, path, seconds, delay):
    setattr(upstream, delay, True)
    status, body, _ = request(app(upstream.url), path, method, b'{"action":"estop"}')
    assert status == 502 and json.loads(body)["detail"] == f"后端请求超时（{seconds} 秒）"


@pytest.mark.parametrize("spec,broken_send", [("2.3", False), ("2.4", False), ("2.4", True)])
def test_mjpeg_first_frame_and_disconnect_close_upstream(upstream, spec, broken_send):
    upstream.stream_open = True  # Never ends until the proxy closes it.

    async def run():
        incoming, messages = asyncio.Queue(), []
        incoming.put_nowait({"type": "http.request", "body": b"", "more_body": False})
        received = bytearray()

        async def send(message):
            messages.append(message)
            received.extend(message.get("body", b""))
            if JPEG + b"\r\n" in received:
                if broken_send:
                    raise OSError("client closed")
                incoming.put_nowait({"type": "http.disconnect"})

        response = app(upstream.url)(scope("/backend/api/camera/color.mjpg", spec=spec), incoming.get, send)
        if broken_send:
            with pytest.raises(ClientDisconnect):
                await asyncio.wait_for(response, 3)
        else:
            await asyncio.wait_for(response, 3)
        assert received == FRAME
        assert messages[0]["status"] == 200
        assert dict(messages[0]["headers"])[b"content-type"] == b"multipart/x-mixed-replace; boundary=frame"
        assert await asyncio.to_thread(upstream.closed.wait, 1)
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    asyncio.run(run())


def test_disconnect_during_stream_read_waits_for_worker_cleanup(upstream, monkeypatch):
    from http.client import HTTPResponse
    upstream.stream_open = True
    entered, exited = Event(), Event()
    original = HTTPResponse.read1
    reads = []

    def read(response, size):
        reads.append(current_thread())
        if len(reads) > 1:
            entered.set()
        try:
            return original(response, size)
        finally:
            if len(reads) > 1:
                exited.set()

    monkeypatch.setattr(HTTPResponse, "read1", read)

    async def run():
        incoming = asyncio.Queue()
        incoming.put_nowait({"type": "http.request", "body": b"", "more_body": False})

        async def send(message):
            pass

        task = asyncio.create_task(app(upstream.url)(scope("/backend/api/camera/color.mjpg", spec="2.3"), incoming.get, send))
        assert await asyncio.to_thread(entered.wait, 1)
        incoming.put_nowait({"type": "http.disconnect"})
        await asyncio.wait_for(task, 3)
        assert exited.is_set() and len(reads) == 2
        assert all(thread is not current_thread() for thread in reads)
        assert await asyncio.to_thread(upstream.closed.wait, 1)
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    asyncio.run(run())


@pytest.mark.parametrize("url", ["http://localhost:8080", "https://127.0.0.1/", "http://192.168.1.20:8080",
    "http://10.0.0.2", "http://172.16.1.2", "http://[::1]:8080", "https://[fd00::1]", "http://169.254.1.2"])
def test_local_backend_origins_are_accepted(url):
    assert proxy.validate_backend_url(url) == url.rstrip("/")


@pytest.mark.parametrize("url", ["", "ftp://127.0.0.1", "file:///tmp/state", "http://example.com",
    "http://8.8.8.8", "http://0.0.0.0", "http://224.0.0.1", "http://192.0.2.1", "http://[::]",
    "http://user:pass@localhost", "http://localhost/api", "http://localhost?x=1", "http://localhost#x",
    "http://localhost:abc", "http://localhost:0", "http://localhost:65536", "http://localhost:",
    "http://localhost\n", "http://127.1", "http://localhost.evil", "http://[::1", "http://[::1]evil"])
def test_invalid_backend_fails_before_startup(url, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["server", "--sim", "--backend", url])
    with pytest.raises(SystemExit) as error:
        serve_ui()
    assert error.value.code == 2 and "--backend 地址无效" in capsys.readouterr().err
    with pytest.raises(ValueError, match="--backend 地址无效"):
        app(url)


def test_cli_passes_backend_to_create_server(upstream, monkeypatch, tmp_path):
    captured = []
    monkeypatch.setattr("sys.argv", ["server", "--sim", "--backend", upstream.url, "--data-dir", str(tmp_path)])
    monkeypatch.setattr("uvicorn.run", lambda application, **kwargs: captured.append(application))
    serve_ui()
    assert request(captured[0], "/backend/api/state")[1] == STATE
