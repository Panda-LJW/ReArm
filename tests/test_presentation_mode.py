"""路演模式模块的契约测试：只靠覆盖 design tokens 放大，且完全不影响日常模式。"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import pytest
from rearm.app import build_app
from rearm.ui.server import create_server
from tests.test_ui_architecture import request

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'rearm/ui/static'
MODULE = STATIC / 'modules/presentation'
CSS = (MODULE / 'presentation.css').read_text()
JS = (MODULE / 'presentation.js').read_text()
NODE = shutil.which('node')


def rules(css: str):
    """Yield (selector, body) for every style rule, flattening @media blocks."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    css = re.sub(r'@media[^{]+\{((?:[^{}]*\{[^{}]*\})*[^{}]*)\}', r'\1', css)
    return [(sel.strip(), body) for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css)]


def test_presentation_files_are_served(config, tmp_path):
    controller = build_app(config, tmp_path)
    app = create_server(controller, controller.bus, controller.snapshot())
    for name in ('presentation.js', 'presentation.css'):
        assert request(app, '/static/modules/presentation/' + name)[0] == 200
    assert '<div id="modeslot"></div>' in request(app, '/')[1].decode()


def test_every_rule_is_scoped_to_show_mode():
    found = rules(CSS)
    assert len(found) > 40
    for selector, _ in found:
        for part in selector.split(','):
            part = part.strip()
            assert part.startswith('html[data-mode="show"]') or part == '#modetoggle', part


def test_minimum_font_size_is_18px_through_tokens():
    root = next(body for selector, body in rules(CSS) if selector == 'html[data-mode="show"]')
    tokens = dict(re.findall(r'(--[\w-]+):([^;]+)', root))
    assert tokens['--fs-min'].startswith('clamp(18px,')
    base = dict(re.findall(r'(--fs-[\w-]+):', (STATIC / 'tokens.css').read_text()) and
                [(name, None) for name in re.findall(r'(--fs-[\w-]+):', (STATIC / 'tokens.css').read_text())])
    # 基础 tokens 里的每一个字号变量都被覆盖，且都不小于 --fs-min。
    assert set(base) <= set(tokens)
    for name in base:
        value = tokens[name]
        if name in ('--fs-kpi', '--fs-kpi-wide'):
            assert value.startswith('clamp(40px') or value == 'var(--fs-kpi)'
        else:
            assert value == 'var(--fs-min)' or re.fullmatch(r'calc\(var\(--fs-min\) \* 1\.\d+\)', value), (name, value)
    # 其余规则不再写死小于 18px 的字号（相对单位和变量除外）。
    for selector, body in rules(CSS):
        for size in re.findall(r'font-size:\s*(\d+(?:\.\d+)?)px', body):
            assert float(size) >= 18, selector


def test_module_only_touches_its_own_slot():
    assert 'querySelector' not in JS and JS.count('getElementById') == 1 and 'getElementById("modeslot")' in JS
    assert 'root.dataset.mode' in JS and 'rearm:theme' in JS
    # 主程序和其它模块不认识路演模式；它们只响应通用的 rearm:theme 事件。
    app_js = re.sub(r'/\*.*?\*/', '', (STATIC / 'app.js').read_text(), flags=re.S)
    assert 'data-mode' not in app_js and 'presentation' not in app_js and 'dataset.mode' not in app_js
    assert 'data-mode' not in (STATIC / 'app.css').read_text()


def test_safety_controls_are_never_hidden_or_disabled_by_the_mode():
    for selector, body in rules(CSS):
        if re.search(r'#estop\b|#estopbar|#resetstop|#connectionbar|\.banner|\.stop-banner', selector):
            assert 'display:none' not in body and 'visibility' not in body and 'pointer-events' not in body, selector
    assert 'estop' not in JS and 'disabled' not in JS


def test_url_round_trip_keeps_other_parameters_and_page():
    if NODE is None:
        pytest.skip('node not installed')
    script = '''
import { urlFor, isShow } from "./presentation.js";
const on = urlFor("http://127.0.0.1:8000/?twin=sim#overview", true), off = urlFor(on, false);
console.log(JSON.stringify({ on, off, a: isShow(new URLSearchParams("mode=show")), b: isShow(new URLSearchParams("mode=other")), c: isShow(new URLSearchParams("")) }));
'''
    result = subprocess.run([NODE, '--input-type=module', '-e', script], capture_output=True, text=True, cwd=MODULE, timeout=60)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out['on'] == 'http://127.0.0.1:8000/?twin=sim&mode=show#overview'
    assert out['off'] == 'http://127.0.0.1:8000/?twin=sim#overview'
    assert (out['a'], out['b'], out['c']) == (True, False, False)
