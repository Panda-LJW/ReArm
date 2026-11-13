import ast
import asyncio
import json
from pathlib import Path
import re
from rearm.app import build_app
from rearm.ui.server import create_server
from tests.test_ui_architecture import request

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'rearm/ui/static/app.js').read_text()
CSS = (ROOT / 'rearm/ui/static/app.css').read_text()


def test_static_assets_and_path_traversal(config, tmp_path):
    c = build_app(config, tmp_path)
    app = create_server(c, c.bus, c.snapshot())
    for name, content_type in [('app.js', b'javascript'), ('app.css', b'text/css')]:
        assert request(app, '/static/' + name)[0] == 200
        async def run():
            messages = []
            async def receive():
                return {'type': 'http.request', 'body': b'', 'more_body': False}
            async def send(message):
                messages.append(message)
            path = '/static/' + name
            await app({'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1',
                       'method':'GET','scheme':'http','path':path,'query_string':b'','headers':[]}, receive, send)
            headers = dict(messages[0]['headers'])
            assert headers[b'cache-control'] == b'no-cache'
            assert content_type in headers[b'content-type']
        asyncio.run(run())
    for path in ('/static/../server.py', '/static/../../app.py', '/static/', '/static/missing.css'):
        assert request(app, path)[0] == 404
    # resolve() also rejects a symlink outside the static directory.
    assert 'path.is_relative_to(static.resolve())' in (ROOT / 'rearm/ui/server.py').read_text()


def message_template(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return ''.join(part.value if isinstance(part, ast.Constant) else '{' + ast.unparse(part.value) + '}' for part in node.values)


def test_every_reachable_backend_error_has_chinese_translation():
    errors = json.loads(re.search(r'const ERR=(\{.*?\n\});', JS, re.S).group(1))
    # Command closure: controller, algorithms it invokes, persistence, residual I/O, simulation.
    paths = [ROOT / 'rearm/app.py', ROOT / 'rearm/task/shooter.py']
    for folder in ('evo', 'residual', 'sim'):
        paths += list((ROOT / 'rearm' / folder).glob('*.py'))
    messages = set()
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                if node.exc.func.id in ('ValueError', 'KeyError', 'FileNotFoundError') and node.exc.args:
                    value = message_template(node.exc.args[0])
                    if value:
                        messages.add(value)
    doc = (ROOT / 'docs/故障码.md').read_text()
    table = doc.split('## 护栏拒绝原因')[1].split('## ')[0]
    for original, translation in re.findall(r'^\| ([^|]+) \| ([^|]+) \|$', table, re.M):
        if original == '原文':
            continue
        messages.add(original)
        assert errors[original] == translation
    assert messages <= errors.keys(), messages - errors.keys()
    assert all(re.search(r'[\u3400-\u9fff]', errors[m]) for m in messages)
    assert 'required data file not found' in errors and 'required field missing: {field}' in errors
    assert '操作失败，错误信息：' in JS
    assert 'v.reasons.map(tr)' in JS


def test_hash_routes_and_accessibility_contract():
    assert 'location.hash=b.dataset.page' in JS
    assert 'addEventListener("hashchange",route)' in JS
    assert '["home","overview","codes"].includes(location.hash.slice(1))' in JS
    assert 'route();' in JS
    assert 'aria-current' in JS and 'aria-expanded' in JS
    html = (ROOT / 'rearm/ui/static/index.html').read_text()
    assert len(re.findall(r'<canvas[^>]+role="img"[^>]+aria-label=', html)) == 3
    assert JS.count('.setAttribute("aria-label",') >= 3
    def luminance(color):
        rgb = [int(color[i:i+2], 16)/255 for i in (0, 2, 4)]
        return sum(w*(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4) for w, v in zip((.2126,.7152,.0722), rgb))
    mute = re.search(r'--mute:#([0-9a-f]{6})', CSS)[1]
    panel = re.search(r'--panel:#([0-9a-f]{6})', CSS)[1]
    assert (luminance(mute)+.05)/(luminance(panel)+.05) >= 4.5
