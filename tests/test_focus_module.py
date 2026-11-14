"""专注阅读样式契约：状态可辨、动效克制，安全控件不被弱化或屏蔽。"""
from pathlib import Path
import re

import pytest

from rearm.app import build_app
from rearm.ui.server import create_server
from tests.test_ui_architecture import request


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'rearm/ui/static'
CSS = (STATIC / 'modules/focus/focus.css').read_text(encoding='utf-8')
CLEAN_CSS = re.sub(r'/\*.*?\*/', '', CSS, flags=re.S)


def rules(css=CLEAN_CSS):
    """与路演测试相同，展开媒体查询后读取选择器和声明。"""
    css = re.sub(r'@media[^{]+\{((?:[^{}]*\{[^{}]*\})*[^{}]*)\}', r'\1', css)
    return [(selector.strip(), body)
            for selector, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css)]


def declarations(body):
    return {name.strip(): value.strip()
            for name, value in re.findall(r'([\w-]+)\s*:\s*([^;]+)', body)}


def style(selector):
    found = {}
    for selectors, body in rules():
        if selector in (part.strip() for part in selectors.split(',')):
            found.update(declarations(body))
    assert found, f'缺少规则：{selector}'
    return found


def test_focus_css_is_served_and_registered(config, tmp_path):
    controller = build_app(config, tmp_path)
    app = create_server(controller, controller.bus, controller.snapshot())
    path = '/static/modules/focus/focus.css'
    status, body = request(app, path)
    assert status == 200 and body.decode('utf-8') == CSS
    # 直接调用 ASGI，不监听端口。现有 HEAD 探测返回 405，需装配层另行修复；
    # 本任务只新增样式与测试，此处验证 GET 可访问及已有模块注册。
    status, body = request(app, '/static/modules/main.js')
    assert status == 200
    main = body.decode('utf-8')
    assert 'optional("focus"' in main and 'loadCss("focus/focus.css")' in main


def test_no_fixed_pixel_fonts_new_colors_gradients_or_glow():
    assert not re.search(r'font-size\s*:\s*(?:\d+(?:\.\d+)?|\.\d+)px\b', CLEAN_CSS, re.I)
    assert 'gradient' not in CLEAN_CSS.lower()
    assert not re.search(r'\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)\s*\(', CLEAN_CSS, re.I)
    tokens = set(re.findall(r'(--[\w-]+)\s*:', (STATIC / 'tokens.css').read_text()))
    assert set(re.findall(r'var\((--[\w-]+)\)', CLEAN_CSS)) <= tokens
    for selector, body in rules():
        for name, value in declarations(body).items():
            if name == 'box-shadow':
                assert value in ('none', 'inset 3px 0 var(--bad)'), (selector, value)
            if name in ('color', 'background', 'background-color', 'border-color'):
                assert value == 'none' or re.fullmatch(r'var\(--[\w-]+\)', value) or (
                    value == '#fff' and '.stop-banner' in selector), (selector, value)


def test_busy_reuses_a_slow_smooth_animation():
    keyframes = re.findall(r'@keyframes\s+([\w-]+)', CLEAN_CSS)
    existing = re.findall(r'@keyframes\s+([\w-]+)', (STATIC / 'app.css').read_text())
    assert len(keyframes) <= 1 and set(keyframes) <= set(existing)
    animation = style('.s-busy::before')['animation']
    duration = re.search(r'\b(\d+(?:\.\d+)?)(ms|s)\b', animation)
    assert duration is not None
    seconds = float(duration[1]) / (1000 if duration[2] == 'ms' else 1)
    assert seconds >= 2
    assert animation.split()[0] in keyframes
    assert 'ease-in-out' in animation and 'infinite' in animation
    assert style('0%')['opacity'] == '1'
    assert style('100%')['opacity'] == '1'
    assert float(style('50%')['opacity']) == .55
    for _, body in rules():
        for name, value in declarations(body).items():
            if name == 'animation':
                assert value == animation or value.replace(' ', '') == 'none!important'


def test_reduced_motion_disables_animation_and_transition_on_pseudo_elements():
    media = re.search(
        r'@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{'
        r'((?:[^{}]*\{[^{}]*\})*[^{}]*)\}', CLEAN_CSS)
    assert media is not None
    reduced = {part.strip(): declarations(body)
               for selector, body in rules(media[1]) for part in selector.split(',')}
    for selector in ('*', '*::before', '*::after'):
        for name in ('animation', 'transition'):
            assert reduced[selector][name].replace(' ', '') == 'none!important'


def test_safety_controls_are_never_hidden_disabled_or_dimmed():
    protected = r'#(?:estop|resetstop|estopbar|connectionbar)\b|\.(?:banner|stop-banner|stale-banner)\b'
    for selector, body in rules():
        props = declarations(body)
        if re.search(protected, selector):
            assert not re.search(r'display\s*:\s*none\b|visibility|pointer-events', body), selector
            assert float(props.get('opacity', '1')) >= 1, selector
        # 不能通过安全控件的公共祖先或全局选择器降低其透明度。
        if any(part.strip() in ('*', 'html', 'body', 'main', 'header', '.statusbars')
               for part in selector.split(',')):
            assert float(props.get('opacity', '1')) >= 1, selector
    assert '.stop-banner' not in next(
        selector for selector, body in rules() if declarations(body).get('opacity') == '.45')


def test_phase_attention_and_bad_error_marker():
    phases = set(re.findall(r'body\[data-phase="(\w+)"\]', CLEAN_CSS))
    assert {'busy', 'bad', 'stop', 'stale'} <= phases <= {'ok', 'busy', 'bad', 'stop', 'stale'}
    assert float(style('body[data-phase="busy"] .row2 .card:nth-child(3)')['opacity']) == .5
    assert style('body[data-phase="busy"] .cam')['outline'] == '2px solid var(--warn)'
    assert style('body[data-phase="bad"] .cam')['outline'] == '2px solid var(--bad)'
    assert float(style('body[data-phase="stop"] .page')['opacity']) == .45
    banner = style('body[data-phase="stop"] .stop-banner')
    assert banner['background'] == 'var(--bad)' and banner['color'] == '#fff'
    assert int(banner['font-weight']) >= 600 and banner['font-size'] == 'var(--fs-lg)'
    assert style('body[data-phase="stop"] .stop-banner::before')['content'] == '"■ "'
    assert int(style('body[data-phase="stale"] .stale-banner')['font-weight']) >= 600
    assert style('body[data-phase="stale"] .stale-banner::before')['content'] == '"⚠ "'
    assert style('.kpi[data-level="bad"]')['box-shadow'] == 'inset 3px 0 var(--bad)'
    for selector in ('.page', '.row2 .card:nth-child(3)', '.card h3 .aside'):
        assert style(selector)['transition'] == 'opacity .2s'


@pytest.mark.parametrize(('selector', 'icon', 'color'), [
    ('.chip.state.s-ok', '✓', '--cyan'),
    ('.chip.state.s-busy', '◔', '--warn'),
    ('.chip.state.s-bad', '▲', '--bad'),
    ('.chip.state.s-info', '●', '--accent'),
    ('.chip.err.s-ok', '✓', '--cyan'),
    ('.chip.err.s-bad', '▲', '--bad'),
    ('.chip.err.s-info', '●', '--accent'),
    ('.chip.laser', '○', '--sub'),
    ('.chip.laser.laser-on', '●', '--warn'),
    ('.ev i', '·', '--mute'),
    ('.ev i.ok', '✓', '--cyan'),
    ('.ev i.bad', '▲', '--bad'),
    ('.ev i.busy', '◆', '--warn'),
    ('.ev i.info', '●', '--accent'),
    ('.tag.cur', '▶ ', None),
    ('.tag.ok', '✓ ', None),
    ('.tag.bad', '✕ ', None),
    ('.tag.cy', '↺ ', None),
])
def test_status_icons_keep_semantic_colors(selector, icon, color):
    props = style(selector + '::before')
    assert props['content'] == f'"{icon}"'
    if color:
        assert props['color'] == f'var({color})'


def test_icons_replace_circles_without_fixed_sizes_or_chip_wrapping():
    for selector in ('html body .chip.state::before', 'html body .chip.err::before',
                     'html body .chip.laser::before', '.ev i', '.ev i.ok', '.ev i.bad',
                     '.ev i.busy', '.ev i.info', 'html[data-mode="show"] body .ev i'):
        props = style(selector)
        assert props['width'] == props['height'] == 'auto'
        assert props['background'] == 'none' and props['border-radius'] == '0'
        assert props['font-size'] == '1em' and props['line-height'] == '1'
    for selector in ('.chip.state', '.chip.err', '.chip.laser'):
        assert style(selector)['white-space'] == 'nowrap'
    for selector in ('.ev', 'html[data-mode="show"] body .ev'):
        assert '1em' in style(selector)['grid-template-columns']
    # 连接点只去发光，不改形状；品牌和关节也不再发光。
    assert style('.dot.on') == {'box-shadow': 'none'}
    assert not re.search(r'\.dot(?:::?before|\s*\{)', CLEAN_CSS)
    for selector in ('.brand::before', '.bar i'):
        assert style(selector)['box-shadow'] == 'none'


def test_hierarchy_hover_and_keyboard_focus():
    assert style('header button.primary')['font-weight'] == '600'
    assert float(style('html:not([data-mode="show"]) .card h3 .aside')['opacity']) == .8
    assert style('tbody tr:hover td')['background'] == 'var(--hover)'
    # 保留基础样式的焦点颜色与偏移，同时覆盖带元素名的 2px 规则。
    for selector in (':focus-visible', 'input:focus-visible', 'select:focus-visible', 'button:focus-visible'):
        assert style(selector)['outline-width'] == '3px'
