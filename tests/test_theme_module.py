"""视觉主题模块的契约测试：克制的工业风，只动外观，不动布局、交互和安全控件。"""
import colorsys
from pathlib import Path
import re
from rearm.app import build_app
from rearm.ui.server import create_server
from tests.test_ui_architecture import request

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'rearm/ui/static'
CSS = re.sub(r'/\*.*?\*/', '', (STATIC / 'modules/theme/theme.css').read_text(), flags=re.S)


def test_theme_is_served_and_optional(config, tmp_path):
    controller = build_app(config, tmp_path)
    app = create_server(controller, controller.bus, controller.snapshot())
    assert request(app, '/static/modules/theme/theme.css')[0] == 200
    main = (STATIC / 'modules/main.js').read_text()
    assert 'optional("theme"' in main and 'params.get("theme") === "classic"' in main


def test_no_glow_blur_or_real_gradients():
    assert 'blur(' not in CSS and 'text-shadow' not in CSS and 'radial-gradient' not in CSS
    # 允许的 linear-gradient 只有两端同色的“实线”写法。
    for a, b in re.findall(r'linear-gradient\(([^,()]+(?:\([^)]*\))?),([^,()]+(?:\([^)]*\))?)\)', CSS):
        assert a.strip() == b.strip()
    for a, b in re.findall(r'repeating-linear-gradient\(90deg,([^ ]+) 0 1px,(\w+) 1px', CSS):
        assert b == 'transparent'
    # 阴影只用于浮层的层次，必须是黑色，不能是彩色外发光。
    for shadow in re.findall(r'box-shadow:([^;}]+)', CSS):
        assert shadow.strip() == 'none' or shadow.strip().startswith('inset') or 'rgba(0,0,0' in shadow, shadow
    assert '@keyframes' not in CSS and 'animation' not in CSS


def test_palette_is_neutral_with_no_purple_and_no_new_status_colours():
    for value in re.findall(r'#([0-9a-fA-F]{6})\b', CSS):
        r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
        hue, _, saturation = colorsys.rgb_to_hls(r, g, b)
        hue *= 360
        # 中性灰（低饱和）或用于“可操作”的蓝；不出现紫、品红、霓虹绿等色相。
        assert saturation < 0.35 or 200 <= hue <= 225, value
    root = re.search(r':root\{([^}]*)\}', CSS)[1]
    for status in ('--cyan', '--warn', '--bad'):
        assert status + ':' not in root          # 语义色沿用基础 tokens，不在主题里改动


def test_theme_does_not_change_layout_or_safety_controls():
    for prop in ('display:', 'grid-template', 'flex:', 'position:', 'visibility', 'pointer-events', 'font-size:'):
        assert prop not in CSS, prop
    for selector, _ in re.findall(r'([^{}]+)\{([^{}]*)\}', CSS):
        assert not re.search(r'#estop\b|#resetstop|#estopbar|#connectionbar|\.stop-banner|\.stale-banner', selector), selector


def test_data_colour_is_a_token_so_charts_follow_the_theme():
    tokens = (STATIC / 'tokens.css').read_text()
    assert '--data:' in tokens and '--data-fill:' in tokens
    app_js = (STATIC / 'app.js').read_text()
    assert 'line:V("--data")' in app_js and 'V("--data-fill")' in app_js and 'rgba(61,139,255' not in app_js
