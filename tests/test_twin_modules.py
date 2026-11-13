"""数字孪生与数据源模块的契约测试。

数值部分直接在 Node 里执行前端模块（纯 ES 模块，无构建），没有 Node 时跳过；
结构部分只读文件文本，任何环境都会跑。
"""
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
MODULES = STATIC / 'modules'
NODE = shutil.which('node')


def node(script: str):
    if NODE is None:
        pytest.skip('node not installed')
    result = subprocess.run([NODE, '--input-type=module', '-e', script], capture_output=True, text=True,
                            cwd=MODULES, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_module_files_are_served(config, tmp_path):
    controller = build_app(config, tmp_path)
    app = create_server(controller, controller.bus, controller.snapshot())
    for path in ['modules/main.js', 'modules/main.css', 'modules/twin/twin.js', 'modules/twin/scene.js',
                 'modules/twin/kinematics.js', 'modules/twin/arm-config.js', 'modules/twin/fallback2d.js',
                 'modules/twin/twin.css', 'modules/twin/demo.html', 'modules/datasource/index.js',
                 'modules/datasource/frame.js', 'modules/datasource/panel-source.js',
                 'modules/datasource/sim-source.js', 'modules/datasource/device-source.js',
                 'vendor/three.module.min.js']:
        assert request(app, '/static/' + path)[0] == 200, path


def test_three_is_vendored_at_a_fixed_version_without_cdn():
    head = (STATIC / 'vendor/three.module.min.js').read_text()[:400]
    assert 'SPDX-License-Identifier: MIT' in head and 'const t="160"' in head
    for path in list(MODULES.rglob('*.js')) + list(MODULES.rglob('*.html')) + [STATIC / 'index.html']:
        assert not re.search(r'https?://(?!127\.0\.0\.1|localhost)', re.sub(r'//[^\n]*', '', path.read_text())), path


def test_modules_talk_only_through_declared_interfaces():
    twin = ''.join(p.read_text() for p in (MODULES / 'twin').glob('*.js'))
    source = ''.join(p.read_text() for p in (MODULES / 'datasource').glob('*.js'))
    # 孪生不认识数据源，也不读页面上别的元素或主程序事件。
    assert 'datasource' not in re.sub(r'//[^\n]*', '', twin)
    assert 'getElementById' not in twin and 'rearm:state' not in twin
    # 数据源不认识孪生，不碰 DOM 结构。
    assert 'twin' not in re.sub(r'//[^\n]*', '', source).replace('?twin=', '').replace('get("twin")', '')
    assert 'getElementById' not in source and 'querySelector' not in source
    # 主程序不引用任何可选模块；只广播事件。
    app_js = (STATIC / 'app.js').read_text()
    assert 'modules/' not in app_js and 'CustomEvent("rearm:state"' in app_js


def test_page_survives_without_optional_modules():
    html = (STATIC / 'index.html').read_text()
    # 挂载位默认隐藏，只有模块加载成功才显示并切换栅格。
    assert re.search(r'id="twincard" hidden', html)
    main = (MODULES / 'main.js').read_text()
    assert main.count('await optional(') >= 2 and 'catch (error)' in main
    assert 'card.hidden = true' in main and 'classList.remove("has-twin")' in main
    assert 'body.has-twin' in (MODULES / 'main.css').read_text()
    # app.js 是普通脚本，不依赖模块脚本的执行顺序。
    assert '<script src="/static/app.js" defer></script>' in html


def test_joint_angles_drive_the_model_as_the_panel_defines_them():
    out = node('''
import { ARM_CONFIG as C } from "./twin/arm-config.js";
import { forward, panelToUrdf, position } from "./twin/kinematics.js";
const deg = r => r * 180 / Math.PI, rows = [];
for (const q of [[0,40,-100],[0,90,-90],[30,10,-20],[-45,110,-150],[90,0,0],[-90,55,-127]]) {
  const { frames, tool } = forward(C, panelToUrdf(C, q));
  const p2 = position(frames.joint2), p3 = position(frames.joint3), p4 = position(frames.joint4);
  // 在臂所在的竖直平面内量仰角：水平分量取沿 J1 朝向的带符号投影，这样超过 90° 的后仰也能量对
  const yawRad = -q[0] * Math.PI / 180, ahead = [Math.cos(yawRad), Math.sin(yawRad)];
  const el = (a, b) => deg(Math.atan2(b[2]-a[2], (b[0]-a[0]) * ahead[0] + (b[1]-a[1]) * ahead[1]));
  // 小臂朝向（水平投影）：正前方为 +X，上位机 J1 为正时顺时针（俯视）
  const yaw = deg(Math.atan2(tool[4], tool[0]));
  rows.push({ q, upper: el(p2, p3), fore: el(p3, p4), yaw, toolEl: deg(Math.asin(tool[8])), upperLen: Math.hypot(...p3.map((v,i)=>v-p2[i])), foreLen: Math.hypot(...p4.map((v,i)=>v-p3[i])) });
}
console.log(JSON.stringify(rows));
''')
    for row in out:
        q1, q2, q3 = row['q']
        assert row['upper'] == pytest.approx(q2, abs=0.2)        # 大臂仰角 = J2
        assert row['fore'] == pytest.approx(q2 + q3, abs=0.2)    # 小臂仰角 = J2 + J3
        assert row['toolEl'] == pytest.approx(q2 + q3, abs=1.0)  # 激光方向沿小臂
        if abs(q2 + q3) < 85:
            assert row['yaw'] == pytest.approx(-q1, abs=0.5)     # 偏航 = −J1（URDF 逆时针为正）
        assert row['upperLen'] == pytest.approx(0.264, abs=1e-4)  # 连杆长度来自 URDF
        assert row['foreLen'] == pytest.approx(0.2485, abs=1e-3)


def test_kinematics_clamps_to_joint_limits_and_ignores_bad_input():
    out = node('''
import { ARM_CONFIG as C } from "./twin/arm-config.js";
import { panelToUrdf } from "./twin/kinematics.js";
console.log(JSON.stringify({ far: panelToUrdf(C, [999, 999, -999]), bad: panelToUrdf(C, [NaN, "x", null]), rest: C.restPose,
  limits: Object.fromEntries(C.joints.map(j => [j.id, j.limit])) }));
''')
    for joint, value in out['far'].items():
        lo, hi = out['limits'][joint]
        assert lo <= value <= hi
    assert {k: out['bad'].get(k) for k in out['rest']} == out['rest']
    assert out['bad'].get('joint1') in (None, 0)


def test_data_sources_share_one_frame_shape():
    out = node('''
import { makeFrame, createSource, SOURCES } from "./datasource/index.js";
import { parseTelemetry, PROTOCOL_VERSION, HEARTBEAT_TIMEOUT_MS } from "./datasource/device-source.js";
const sim = createSource("sim"), limits = [[-90,90],[0,110],[-150,0]];
let inside = true;
for (let t = 0; t < 40000; t += 37) sim.anglesAt(t).forEach((v, i) => { if (v < limits[i][0] || v > limits[i][1]) inside = false; });
// 面板数据源：喂一个假的 rearm:state 事件
const target = new EventTarget(), panel = createSource("panel", { target }), seen = [];
panel.subscribe(f => seen.push(f)); panel.start();
const fire = detail => { const e = new Event("rearm:state"); e.detail = detail; target.dispatchEvent(e); };
fire({ connected: true, state: { simulation: true, laser_on: true, recent: [{ q: [1, 2, -3], timestamp: 5 }] } });
fire({ connected: true, state: { simulation: false, laser_on: false, recent: [{ q: [4, 5, -6], timestamp: 6 }] } });
fire({ connected: false, state: { simulation: true, recent: [{ q: [4, 5, -6], timestamp: 6 }] } });
fire({ connected: true, state: { simulation: true, recent: [] } });
const tele = parseTelemetry(JSON.stringify({ v: 1, type: "telemetry", seq: 9, t_ms: 12345, joints: [{ id: 2, pos_deg: 40 }, { id: 1, pos_deg: 3 }, { id: 3, pos_deg: -100 }], laser: true }));
console.log(JSON.stringify({ kinds: Object.keys(SOURCES), inside, seen, tele,
  rejected: [parseTelemetry("not json"), parseTelemetry({ v: 2, type: "telemetry", joints: [] }), parseTelemetry({ v: 1, type: "heartbeat" }), parseTelemetry({ v: 1, type: "telemetry", joints: [{ id: 1, pos_deg: "x" }] }),
    // 缺测（null）、缺轴、重复 id 都必须整帧作废，不能用 0 冒充
    parseTelemetry({ v: 1, type: "telemetry", joints: [{ id: 1, pos_deg: 0 }, { id: 2, pos_deg: null }, { id: 3, pos_deg: -90 }] }),
    parseTelemetry({ v: 1, type: "telemetry", joints: [{ id: 1, pos_deg: 0 }, { id: 3, pos_deg: -90 }] }),
    parseTelemetry({ v: 1, type: "telemetry", joints: [{ id: 1, pos_deg: 0 }, { id: 1, pos_deg: 5 }, { id: 2, pos_deg: 40 }, { id: 3, pos_deg: -90 }] })],
  gripper: parseTelemetry({ v: 1, type: "telemetry", t_ms: 1, joints: [{ id: 1, pos_deg: 0 }, { id: 2, pos_deg: 40 }, { id: 3, pos_deg: -90 }, { id: 7, pos_deg: 12 }] }).angles_deg,
  dirty: makeFrame({ angles_deg: [1, "a"], mode: "weird", online: true }), version: PROTOCOL_VERSION, timeout: HEARTBEAT_TIMEOUT_MS }));
''')
    assert out['kinds'] == ['panel', 'sim', 'device'] and out['inside']
    keys = {'timestamp', 'angles_deg', 'mode', 'online', 'laser'}
    assert all(set(frame) == keys for frame in out['seen'] + [out['tele'], out['dirty']])
    sim, live, offline, empty = out['seen']
    assert (sim['mode'], sim['angles_deg'], sim['laser'], sim['online']) == ('sim', [1, 2, -3], True, True)
    assert (live['mode'], live['angles_deg'], live['laser']) == ('live', [4, 5, -6], False)
    assert (offline['mode'], offline['online'], offline['laser']) == ('offline', False, None)
    assert empty['angles_deg'] is None and empty['mode'] == 'sim'
    assert out['tele']['angles_deg'] == [3, 40, -100] and out['tele']['mode'] == 'live' and out['tele']['timestamp'] == 12.345
    assert out['rejected'] == [None] * 7
    assert out['gripper'] == [0, 40, -90]   # 夹爪 id=7 的毫米值不混进角度
    assert out['dirty'] == {**out['dirty'], 'angles_deg': None, 'mode': 'offline', 'online': False}
    assert out['version'] == 1 and out['timeout'] == 1000


def test_device_source_is_never_the_default_and_only_listens():
    index = (MODULES / 'datasource/index.js').read_text()
    assert 'return createSource("panel");' in index and '/^wss?:\\/\\//' in index
    device = (MODULES / 'datasource/device-source.js').read_text()
    assert '.send(' not in device


def test_arm_config_documents_sources_and_placeholders():
    config = (MODULES / 'twin/arm-config.js').read_text()
    assert 'ReBot_Arm_DM.urdf' in config and config.count('占位') >= 4
    # 上位机限位内的读数映射后都落在 URDF 限位内（否则模型会被夹住而与读数不符）。
    out = node('''
import { ARM_CONFIG as C } from "./twin/arm-config.js";
const rad = d => d * Math.PI / 180, panel = [[-90, 90], [0, 110], [-150, 0]];
console.log(JSON.stringify(C.panelMapping.map((m, i) => { const j = C.joints.find(x => x.id === m.joint); const v = panel[i].map(d => m.sign * rad(d) + m.offset); return [Math.min(...v) >= j.limit[0] - 2e-3, Math.max(...v) <= j.limit[1] + 2e-3]; })));
''')  # 容差 0.002 rad：URDF 把 π 写成 3.14
    assert out == [[True, True]] * 3


def test_mock_device_telemetry_is_accepted_by_the_device_source():
    import importlib.util
    import time
    spec = importlib.util.spec_from_file_location('mock_device', ROOT / 'scripts/mock_device.py')
    mock = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mock)
    message = mock.telemetry(7, time.monotonic() - 2.0)
    assert '\n' not in message and len(message.encode()) <= 1024
    out = node('import { parseTelemetry } from "./datasource/device-source.js";\n'
               f'console.log(JSON.stringify(parseTelemetry({json.dumps(message)})));')
    assert out['mode'] == 'sim' and out['online'] is True and len(out['angles_deg']) == 3
    for value, (lo, hi) in zip(out['angles_deg'], [(-90, 90), (0, 110), (-150, 0)]):
        assert lo <= value <= hi
    # 只监听回环地址，不对外开放。
    assert 'asyncio.run(main("127.0.0.1"' in (ROOT / 'scripts/mock_device.py').read_text()
