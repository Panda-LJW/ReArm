"""Panel safety and streaming regressions, with no hardware or network listeners."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import json
import time
import pytest

from rearm.app import build_app
from rearm.sim.sim_camera import SimCamera
from rearm.ui.server import create_server
from tests.test_ui_architecture import request


def test_estop_blocks_commands_and_reset_restores_operation(config, tmp_path):
    c = build_app(config, tmp_path)
    app = create_server(c, c.bus, c.snapshot())
    assert request(app, '/api/command/estop', 'POST')[0] == 200
    for name in ('selfcheck', 'baseline', 'retrain', 'preview', 'switch', 'inject'):
        status, body = request(app, '/api/command/' + name, 'POST')
        assert status == 400 and 'emergency stop active' in json.loads(body)['detail']
    state = json.loads(request(app, '/api/state')[1])
    assert state['estop'] and not state['laser_on']
    assert c.sequence == 0
    assert request(app, '/api/command/reset_estop', 'POST')[0] == 200
    assert request(app, '/api/command/selfcheck', 'POST')[0] == 200
    assert c.sequence == config.thresholds['detector']['window']
    assert not json.loads(request(app, '/api/state')[1])['estop']


@pytest.mark.parametrize('name', ['selfcheck', 'baseline', 'preview', 'recovery'])
def test_estop_interrupts_multishot_without_waiting_for_workflow_lock(config, tmp_path, name):
    c = build_app(config, tmp_path)
    if name == 'recovery':
        c.command('inject', {'kind': 'j1', 'amount': 1})
    app = create_server(c, c.bus, c.snapshot())
    entered, release = Event(), Event()
    observe = c.arm.observe_spot
    count = 0

    def blocked_observation():
        nonlocal count
        count += 1
        # Recovery: stop in its holdout loop, whose ValueError handler must not swallow estop.
        if name != 'recovery' or count == config.thresholds['detector']['window'] + 17:
            entered.set()
            assert release.wait(5)
        return observe()

    c.arm.observe_spot = blocked_observation
    with ThreadPoolExecutor(max_workers=2) as pool:
        job = pool.submit(request, app, '/api/command/' + ('selfcheck' if name == 'recovery' else name),
                          'POST', {'version_id': 'v0001'})
        try:
            assert entered.wait(5)
            assert json.loads(request(app, '/api/state')[1])['laser_on']
            stop = pool.submit(request, app, '/api/command/estop', 'POST')
            status, body = stop.result(timeout=1)
            assert status == 200 and json.loads(body)['estop']
            assert not c.arm.laser_on
            assert not job.done(), 'estop must finish while the original workflow is still blocked'
            assert request(app, '/api/command/reset_estop', 'POST')[0] == 400
            before = count
        finally:
            release.set()
        assert job.result(timeout=5)[0] == 400
    assert count == before, 'no next shot after the stop latch'
    assert c.store.head().id == 'v0001'
    assert c.stop_requested.is_set() and not c.busy
    assert request(app, '/api/command/reset_estop', 'POST')[0] == 200
    assert request(app, '/api/command/selfcheck', 'POST')[0] == 200


@pytest.mark.parametrize('error', [NotImplementedError, OSError, ValueError])
def test_estop_latches_even_if_laser_driver_fails(config, tmp_path, error):
    c = build_app(config, tmp_path)
    app = create_server(c, c.bus, c.snapshot())
    c.set_laser(True)
    calls = []
    def fail(on):
        calls.append(on)
        raise error('driver failure')
    c.arm.laser = fail
    assert request(app, '/api/command/estop', 'POST')[0] == 200
    state = json.loads(request(app, '/api/state')[1])
    assert state['estop'] and state['estop_error']
    assert state['laser_on'], 'failed off write must not claim that the laser is off'
    assert calls == [False]
    assert request(app, '/api/command/selfcheck', 'POST')[0] == 400
    assert request(app, '/api/command/reset_estop', 'POST')[0] == 400
    assert c.stop_requested.is_set()


def test_healing_start_available_midflow_and_stale_snapshot_cannot_clear_estop(config, tmp_path):
    c = build_app(config, tmp_path)
    app = create_server(c, c.bus, c.snapshot())
    c.command('inject', {'kind': 'j1', 'amount': 1})
    checkpoints = []
    def observe(event):
        if event.kind == 'state' and event.data['state'] == '发现异常':
            view = json.loads(request(app, '/api/state')[1])
            assert view['heal_start'] == view['shots'] == 3
        if event.kind == 'shot' and event.data['shot']['role'] == 'recognition':
            view = json.loads(request(app, '/api/state')[1])
            checkpoints.append((view['heal_start'], view['shots']))
    c.bus.subscribe(observe)
    c.command('selfcheck', {})
    assert checkpoints == [(3, 4), (3, 5), (3, 6)]
    stale = c.snapshot()
    c.command('estop', {})
    c.emit('snapshot', snapshot=stale)
    assert json.loads(request(app, '/api/state')[1])['estop']


def test_mjpeg_headers_first_jpeg_and_disconnect_cleanup(config, tmp_path):
    c = build_app(config, tmp_path)
    camera = SimCamera(config)
    reads = []
    read = camera.read
    def counted_read():
        reads.append(time.monotonic())
        return read()
    camera.read = counted_read
    app = create_server(c, c.bus, c.snapshot(), camera, 80)

    async def run():
        messages, disconnected = [], False
        async def receive():
            if disconnected:
                return {'type': 'http.disconnect'}
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        async def send(message):
            nonlocal disconnected
            messages.append(message)
            if message['type'] == 'http.response.body' and message.get('body'):
                disconnected = True
        scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
                 'http_version': '1.1', 'method': 'GET', 'scheme': 'http',
                 'path': '/api/camera.mjpg', 'raw_path': b'/api/camera.mjpg',
                 'query_string': b'', 'headers': [], 'server': ('localhost', 8000), 'client': ('test', 0)}
        await asyncio.wait_for(app(scope, receive, send), 2)
        headers = dict(messages[0]['headers'])
        assert messages[0]['status'] == 200
        assert headers[b'content-type'] == b'multipart/x-mixed-replace; boundary=frame'
        assert headers[b'cache-control'] == b'no-store'
        frame = next(m['body'] for m in messages if m['type'] == 'http.response.body' and m.get('body'))
        prefix, jpeg = frame.split(b'\r\n\r\n', 1)
        assert prefix.startswith(b'--frame\r\nContent-Type: image/jpeg')
        assert jpeg.startswith(b'\xff\xd8') and jpeg.endswith(b'\xff\xd9\r\n')
        await asyncio.sleep(.25)
        assert len(reads) == 1, 'no producer left reading after disconnect'
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    asyncio.run(run())
    no_camera = create_server(c, c.bus, c.snapshot())
    assert request(no_camera, '/api/camera.mjpg')[0] == 404


def test_reset_cannot_clear_a_new_concurrent_estop(config, tmp_path):
    c = build_app(config, tmp_path)
    c.estop()
    entered, release, stopped = Event(), Event(), Event()
    laser = c.arm.laser
    def slow_off(on):
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        laser(on)
    c.arm.laser = slow_off
    c.bus.subscribe(lambda event: stopped.set() if event.kind == 'estop' else None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reset = pool.submit(c.reset_estop)
        try:
            assert entered.wait(2)
            stop = pool.submit(c.estop)
            assert stopped.wait(2), 'new stop latches before the slow laser write finishes'
        finally:
            release.set()
        with pytest.raises(ValueError, match='operation still stopping'):
            reset.result(timeout=2)
        assert stop.result(timeout=2)['estop']
    assert c.stop_requested.is_set()


def test_mjpeg_disconnect_during_read_does_not_abandon_worker(config, tmp_path):
    c = build_app(config, tmp_path)
    camera = SimCamera(config)
    read = camera.read
    entered, release, exited = Event(), Event(), Event()
    def slow_read():
        entered.set()
        assert release.wait(3)
        try:
            return read()
        finally:
            exited.set()
    camera.read = slow_read
    app = create_server(c, c.bus, c.snapshot(), camera, 80)
    async def run():
        incoming = asyncio.Queue()
        await incoming.put({'type': 'http.request', 'body': b'', 'more_body': False})
        async def receive(): return await incoming.get()
        async def send(message): pass
        # ASGI 2.3 actively cancels the streaming scope when disconnect arrives.
        task = asyncio.create_task(app({'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.3'},
            'http_version': '1.1', 'method': 'GET', 'scheme': 'http', 'path': '/api/camera.mjpg',
            'query_string': b'', 'headers': []}, receive, send))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            await incoming.put({'type': 'http.disconnect'})
            await asyncio.sleep(.05)
            assert not task.done(), 'disconnect waits for the in-flight camera read'
        finally:
            release.set()
        await asyncio.wait_for(task, 2)
        assert exited.is_set()
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    asyncio.run(run())
