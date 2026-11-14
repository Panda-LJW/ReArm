"""T5 区域契约与 Node 集成：只使用本地 mock、虚拟时钟和 DOM 宿主。"""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'rearm/ui/static'
TRAINER = STATIC / 'modules/trainer'
NODE = shutil.which('node')

# 接口文档测试的面板字段清单。包括 store 原样保留的 v1 消息字段，
# 不把 DOM 属性、视图汇总字段或 ARM_PARAMS 参数误当成通信协议字段。
USED_FIELDS = {
    'v', 'type', 'seq', 't', 'cmd', 'ok', 'code', 'msg', 'online', 'reason',
    'proto', 'host_version', 'arm', 'model', 'joints', 'threshold_mm', 'camera',
    'url', 'format', 'sim', 'laser_ttl_ms', 'node_timeout_ms',
    'mode', 'q', 'dq', 'current', 'temp', 'valid', 'gripper_mm', 'gripper_valid',
    'pass', 'node', 'settled', 'fault', 'on', 'source', 'remaining_ms', 'ttl_ms',
    'demo_id', 'samples', 'nodes', 'id', 'gripper_state', 'ref_spot_base_mm',
    'ref_spot_px', 'end_base_mm', 'spot_px', 'depth_mm', 'spot_base_mm',
    'dev_mm', 'dev_norm_mm', 'invalid_reason', 'image_url', 'max_mm', 'mean_mm',
    'valid_nodes', 'total_nodes', 'below_threshold', 'applied', 'items',
    'target', 'delta', 'unit', 'note', 'llm_text', 'name', 'text', 'level',
}


def node(script, cwd=None):
    if NODE is None:
        pytest.skip('node not installed')
    run = subprocess.run([NODE, '--input-type=module', '-e', script],
                         cwd=cwd or STATIC / 'modules', text=True, capture_output=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return run.stdout


def test_claim_seams_and_unclaimed_controls_remain_independent():
    text = (STATIC / 'app.js').read_text()
    assert 'const claimed=region=>' in text
    assert 'trainer' not in text and 'modules/' not in text
    render = text.split('function render(){', 1)[1].split('function toPx', 1)[0]
    for region in ['kpis', 'joints', 'feed', 'errchart', 'diag', 'cam']:
        assert f'if(!claimed("{region}"))' in render
    for start in ['function refreshCamera(){', 'function showCameraFrame(source){']:
        assert text.split(start)[1].lstrip().startswith('if(claimed("cam")){stopCamera();return;}')
    controls = text.split('function syncControls(){')[1].split('function connectionState')[0]
    assert 'claimed' not in controls and 'name!=="estop"' in controls
    assert 'if(claimed("errchart"))return;' in text
    assert 'if(!claimed("errchart"))$("errchart").setAttribute' in text


def test_main_gates_guide_and_trainer_and_restores_claim_on_failure():
    text = (STATIC / 'modules/main.js').read_text()
    assert 'params.get("legacy") === "1"' in text
    assert 'if (legacy) await optional("guide"' in text
    assert 'if (!legacy) await optional("trainer"' in text
    assert text.index('optional("twin"') < text.index('optional("trainer"')
    assert 'legacy ? sourceFromParams(params) : null' in text
    assert 'initTrainer({ twin, params })' in text
    failure = text.split('optional("trainer"')[1].split('// 解说条')[0]
    assert 'delete document.documentElement.dataset.claim' in failure
    assert 'CustomEvent("rearm:theme")' in failure
    assert 'loadCss("trainer/trainer.css")' in failure


def test_static_mounts_and_old_action_nodes_are_preserved():
    html = (STATIC / 'index.html').read_text()
    for name in ['k-err', 'joints', 'feed', 'errchart', 'diag', 'cam', 'estop']:
        assert f'id="{name}"' in html
    assert 'data-cmd="selfcheck"' in html
    assert 'trainerslot' not in html


ALLOWED_IDS = {
    'kpis.js': set(),
    'joints.js': {'joints'},
    'feed.js': set(),
    'deviation-chart.js': {'errchart'},
    'corrections.js': {'diag', 'diagtitle', 'diagaside'},
    'camera.js': {'camimg', 'overlay', 'chipstate', 'chiplaser', 'chipver', 'chiperr'},
    'controls.js': {'toast', 'toastmsg', 'mode'},
    'canvas.js': set(), 'format.js': set(),
}


@pytest.mark.parametrize('name,allowed', ALLOWED_IDS.items())
def test_each_view_queries_only_its_region(name, allowed):
    text = (TRAINER / 'views' / name).read_text()
    ids = set(re.findall(r'getElementById\(["\']([^"\']+)', text))
    ids |= set(re.findall(r'querySelector(?:All)?\(["\']#([\w-]+)', text))
    assert ids <= allowed, ids - allowed
    if name not in ['canvas.js', 'format.js', 'controls.js']:
        assert 'document.querySelector' not in text
        assert 'document.getElementById' not in text
        assert 'export function mount(root)' in text and 'render(state' in text


def test_button_states_interlock_offline_estop_fault_and_automatic_laser():
    node('''
import assert from 'node:assert/strict';
import { buttonStates } from './trainer/views/controls.js';
import { initialState } from './trainer/store.js';
const base = {...initialState(), link:{online:true}, hello:{sim:true}};
for(const mode of ['idle','demo','practice','estop','fault']) {
  const b=buttonStates({...base,mode});
  assert.equal(b.demo.disabled, ['practice','estop','fault'].includes(mode));
  assert.equal(b.practice.disabled, ['demo','estop','fault'].includes(mode));
  assert.equal(b.laser.disabled, ['practice','estop','fault'].includes(mode));
  assert.equal(b.demo.pressed,mode==='demo'); assert.equal(b.practice.pressed,mode==='practice');
}
for(const state of [initialState(), {...base,hello:null}, {...base,link:{online:false}},
  {...base,ui:{pending:true}}, {...base,ui:{panelEstop:true}}, {...base,ui:{active:false}}, {...base,joint:{fault:'driver'}}])
  assert.ok(Object.values(buttonStates(state)).every(b=>b.disabled));
assert.match(buttonStates({...base,mode:'practice'}).laser.text,/自动/);
assert.equal(buttonStates({...base,laser:{on:true}}).laser.text,'激光 开');
''')


def test_untrusted_llm_text_is_never_html_and_chart_uses_computed_probe():
    text = (TRAINER / 'views/corrections.js').read_text()
    assert 'explanation.textContent = last.llm_text' in text
    assert 'innerHTML' not in text
    canvas = (TRAINER / 'views/canvas.js').read_text()
    assert 'getComputedStyle(probe).fontSize' in canvas
    assert 'probe.style.fontSize = `var(${name})`' in canvas
    chart = (TRAINER / 'views/deviation-chart.js').read_text()
    assert 'px("--fs-chart")' in chart and 'aria-label' in chart
    for color in ['--data', '--geo', '--warn']:
        assert color in chart


@pytest.mark.parametrize('max_value,threshold,expected', [
    (18, 5, {'top': 20, 'step': 5, 'ticks': [0, 5, 10, 15, 20]}),
    (4.3, 5, {'top': 6, 'step': 2, 'ticks': [0, 2, 4, 6]}),
    (120, 5, {'top': 150, 'step': 50, 'ticks': [0, 50, 100, 150]}),
    (0, 5, {'top': 6, 'step': 2, 'ticks': [0, 2, 4, 6]}),
])
def test_deviation_nice_ticks_examples(max_value, threshold, expected):
    node(f'''
import assert from 'node:assert/strict';
import {{ niceTicks }} from './trainer/views/deviation-chart.js';
assert.deepEqual(niceTicks({max_value}, {threshold}), {json.dumps(expected)});
''')


def test_deviation_nice_ticks_boundaries_and_finite_fallback():
    node('''
import assert from 'node:assert/strict';
import { niceTicks } from './trainer/views/deviation-chart.js';
for (const max of [0, 2, 4, 4.01, 5, 8, 8.01, 18, 20, 20.01, 40, 40.01, 100, 120, 1e6]) {
 for (const threshold of [5, 20, 120]) {
  const {top, step, ticks} = niceTicks(max, threshold), limit = Math.max(max, threshold);
  assert.ok(top >= limit && top - step < limit);
  assert.ok(Number.isInteger(step) && step >= 1);
  assert.ok([1, 2, 5].includes(step / 10 ** Math.floor(Math.log10(step))));
  assert.ok(ticks.length >= 3 && ticks.length <= 5);
  assert.equal(ticks[0], 0); assert.equal(ticks.at(-1), top);
  ticks.forEach((value, i) => assert.equal(value, i * step));
 }
}
for (const value of [NaN, Infinity, undefined, null]) {
 assert.deepEqual(niceTicks(value, 5), niceTicks(0, 5));
 assert.deepEqual(niceTicks(18, value), niceTicks(18, 0));
}
assert.deepEqual(niceTicks(0, 0), {top:2, step:1, ticks:[0, 1, 2]});
''')


@pytest.mark.parametrize('font', [14, 18, 24])
def test_deviation_chart_integer_labels_threshold_line_and_token_font(font):
    jsdom_script(r'''
import assert from 'node:assert/strict';
const dom = new JSDOM('<section><h3></h3><div class="legendline"></div><canvas id="errchart" aria-label="original"></canvas></section>');
globalThis.document = dom.window.document;
globalThis.getComputedStyle = () => ({fontSize:'FONTpx', getPropertyValue:name=>name==='--sans'?'sans-serif':name});
const labels = [], strokes = [];
let path = [];
const context = new Proxy({
 measureText:s=>({width:s.length * FONT * .6}),
 fillText(text,x,y) { labels.push({text,x,y,font:this.font}); },
 beginPath() { path = []; }, moveTo(x,y) { path.push([x,y]); }, lineTo(x,y) { path.push([x,y]); },
 stroke() { strokes.push({color:this.strokeStyle, path:[...path], dash:this.dash}); },
 setLineDash(dash) { this.dash = dash; },
}, {get:(o,p)=>o[p]??(()=>{})});
const canvas = document.querySelector('canvas');
canvas.getContext = () => context;
canvas.getBoundingClientRect = () => ({width:500, height:250});
const {mount, niceTicks} = await import('./trainer/views/deviation-chart.js');
const view = mount(document.querySelector('section'));
for (const [max, threshold] of [[18,5], [4.3,5], [120,5], [0,5], [20,20], [5,0]]) {
 labels.length = strokes.length = 0;
 view.render({link:{online:true},hello:{},passes:[{result:{pass:1,mean_mm:max/2,max_mm:max}}]},
   {lastMeanMm:max/2,lastMaxMm:max,thresholdMm:threshold});
 const {top,ticks} = niceTicks(max,threshold);
 assert.deepEqual(labels.filter(l=>l.x===0).map(l=>l.text), ticks.filter(v=>v!==threshold).map(String));
 assert.equal(labels.filter(l=>l.text===`阈值 ${threshold}`).length,1);
 assert.ok(labels.every(l=>l.font==='FONTpx sans-serif'));
 const line = strokes.find(s=>s.color==='--warn');
 assert.equal(line.path.length,2); assert.equal(line.path[0][1],line.path[1][1]);
 assert.ok(Math.abs(line.path[0][1]-(FONT*1.4+(250-FONT*3.2)*(1-threshold/top)))<1e-9);
 assert.ok(line.dash.length>0);
 assert.equal(strokes.filter(s=>s.color==='--grid').length,ticks.length);
}
view.dispose(); assert.equal(canvas.getAttribute('aria-label'),'original'); dom.window.close();
'''.replace('FONT', str(font)))


def test_protocol_field_manifest_tracks_accesses_and_t4_payloads():
    text = '\n'.join(p.read_text() for p in TRAINER.rglob('*.js'))
    # 包括 ?. 访问和图表遍历时的动态字段名；排除已知的 UI / store 槽位。
    accessed = set(re.findall(r'(?:message|joint|node|result|correction|item|reply|first|last|row|expected|actual)\??\.(\w+)', text))
    # received_at 由面板调用方注入，是本地状态字段，不是主机协议字段。
    accessed -= {'nodes', 'result', 'correction', 'parentNode', 'append', 'classList', 'title', 'received_at'}
    assert accessed <= USED_FIELDS | {'want'}, accessed - USED_FIELDS - {'want'}
    assert {'q', 'pass', 'valid', 'llm_text', 'delta', 'unit', 'spot_px', 'ref_spot_px', 'dev_norm_mm'} <= set(re.findall(r'\??\.(\w+)', text))
    mock = (STATIC / 'modules/datasource/mock-host.js').read_text()
    # v1 协议透传字段也必须纳入后续接口文档核对。
    assert {'proto', 'host_version', 'dq', 'remaining_ms', 'image_url', 'valid_nodes', 'mean_mm'} <= USED_FIELDS
    for field in USED_FIELDS - {'cmd', 'ttl_ms', 'reason', 'url', 'format'}:
        assert re.search(r'\b' + field + r'\b', text + mock), field


def test_trainer_css_has_token_fonts_and_no_decorative_effects():
    css = (TRAINER / 'trainer.css').read_text()
    assert not re.search(r'font(?:-size)?\s*:[^;}]*\d(?:\.\d+)?px', css)
    assert 'gradient' not in css and 'box-shadow' not in css
    for selector in re.findall(r'([^{}]+)\{', css):
        if not selector.lstrip().startswith(('@media', '/*')):
            assert 'html[data-trainer="on"]' in selector


def test_all_new_modules_parse():
    if NODE is None:
        pytest.skip('node not installed')
    for path in list(TRAINER.rglob('*.js')) + [STATIC / 'modules/main.js', STATIC / 'app.js']:
        run = subprocess.run([NODE, '--check', str(path)], text=True, capture_output=True)
        assert run.returncode == 0, run.stderr


def jsdom_script(script):
    # 使用已有的测试宿主，不安装包；纯逻辑/文本契约不依赖它。
    candidates = list((Path.home() / '.npm/_npx').glob('*/node_modules/jsdom/lib/api.js'))
    if not candidates:
        pytest.skip('optional jsdom host not installed')
    prelude = 'import { JSDOM } from ' + json.dumps(candidates[0].as_uri()) + ';\n'
    prelude += 'const root = ' + json.dumps(str(ROOT)) + ';\n'
    return node(prelude + script)


def test_trainer_mock_closed_loop_lifecycle_and_dom_rollback():
    jsdom_script(INTEGRATION)


def test_display_numbers_round_before_sign_and_identify_correction_nodes():
    node(r'''
import assert from 'node:assert/strict';
import {number, correctionValue, correctionTarget, correctionText} from './trainer/views/format.js';
for(const value of [-0, -0.0001, -0.004, 0, 0.004]) {
 assert.equal(number(value,2,true),'0.00');
 assert.equal(correctionValue({delta:value,unit:'deg'}),'0.00°');
}
assert.equal(number(-0.006,2),'−0.01');
assert.equal(correctionValue({delta:-1.23,unit:'deg'}),'−1.23°');
assert.equal(correctionValue({delta:1.23,unit:'deg'}),'+1.23°');
assert.equal(correctionValue({delta:-1.23,unit:'mm'}),'−1.23 mm');
assert.equal(correctionTarget({target:'J1',note:''}),'J1');
assert.equal(correctionTarget({target:'J1',note:'节点 2 的下一遍目标角修正'}),'J1 · 节点 2');
assert.equal(correctionText({applied:true,items:[{target:'J1',delta:-0.001,unit:'deg'}]}),'J1 0.00°');
''')


def test_improvement_kpi_baseline_better_worse_equal_and_offline():
    jsdom_script(r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const dom=new JSDOM(fs.readFileSync(root+'/rearm/ui/static/index.html','utf8'));
globalThis.document=dom.window.document;
const {mount}=await import('./trainer/views/kpis.js');
const {initialState}=await import('./trainer/store.js');
const {summarize}=await import('./trainer/metrics.js');
const view=mount(document.querySelector('.kpis')), cell=document.querySelectorAll('.kpi')[2];
const render=values=>{
 const state={...initialState(),link:{online:true},hello:{sim:true},passes:values.map((v,i)=>({pass:i+1,result:{mean_mm:v,max_mm:v},nodes:{}}))};
 view.render(state,{...summarize(state),thresholdMm:5});
 return {value:cell.querySelector('.v').childNodes[0].textContent,detail:cell.querySelector('.d').textContent};
};
assert.deepEqual(render([18]),{value:'—',detail:'第 1 遍是基准'});
assert.equal(cell.querySelector('small'),null);
assert.deepEqual(render([18,2.6]),{value:'86',detail:'↓ 18.0 → 2.6 mm'});
assert.equal(cell.querySelector('small').textContent,'%');
assert.deepEqual(render([18,20.2]),{value:'12',detail:'▲ 变差 · 18.0 → 20.2 mm'});
assert.equal(cell.dataset.level,'bad');assert.ok(cell.querySelector('.v').classList.contains('badc'));
assert.equal(render([18,18]).value,'0');assert.ok(!cell.querySelector('.v').classList.contains('badc'));
assert.equal(render([18,17.9999]).value,'0');assert.equal(render([18,18.0001]).value,'0');
view.render(initialState(),{});assert.equal(cell.querySelector('.v').textContent,'—');assert.equal(cell.querySelector('.d').textContent,'离线');
dom.window.close();
''')


KPI_FIXTURE = r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const dom = new JSDOM(fs.readFileSync(root+'/rearm/ui/static/index.html','utf8'));
globalThis.document = dom.window.document;
const {mount} = await import('./trainer/views/kpis.js');
const {initialState, reduce} = await import('./trainer/store.js');
const {summarize} = await import('./trainer/metrics.js');
const base = {...initialState(), link:{online:true}, hello:{sim:true}};
const view = mount(document.querySelector('.kpis'));
const render = state => {
 view.render(state, {...summarize(state), thresholdMm:5});
 return [...document.querySelectorAll('.kpi')].map(cell => ({
  value:cell.querySelector('.v').firstChild.textContent,
  unit:cell.querySelector('.v small')?.textContent ?? '',
  detail:cell.querySelector('.d').textContent,
  level:cell.dataset.level,
 }));
};
'''


@pytest.mark.parametrize('demo,detail', [
    (None, '点“示范”，手扶机械臂做一遍'),
    ({'nodes': []}, '点“练习”开始'),
])
def test_kpi_idle_next_step_only_in_first_cell(demo, detail):
    jsdom_script(KPI_FIXTURE + f'''
const cells = render({{...base, demo:{json.dumps(demo)}}});
assert.equal(cells[0].detail, {json.dumps(detail)});
assert.ok(cells.every(cell => cell.value === '—' && cell.unit === '' && cell.level === 'none'));
assert.ok(cells.slice(1).every(cell => cell.detail === ''));
view.dispose(); dom.window.close();
''')


@pytest.mark.parametrize('completed,current,detail', [
    (None, 1, '第 1 遍进行中'),
    (4, 5, '第 4 遍已完成 · 练习中'),
])
def test_kpi_practice_distinguishes_current_pass_from_completed_result(completed, current, detail):
    jsdom_script(KPI_FIXTURE + f'''
let state = {{...base, mode:'practice', joint:{{pass:{current}}}}};
if ({json.dumps(completed)} !== null) {{
 state = reduce(state, {{type:'pass_result', pass:4, mean_mm:3, max_mm:4, valid_nodes:4, total_nodes:4}});
 // 迟到的旧结果、当前遍的节点和修正都不能被当成最新完成结果。
 state = reduce(state, {{type:'pass_result', pass:1, mean_mm:12, max_mm:15, valid_nodes:4, total_nodes:4}});
 state = reduce(state, {{type:'correction', pass:5, applied:true, items:[]}});
}}
state = reduce(state, {{type:'node_result', pass:{current}, node:1, valid:true, dev_norm_mm:2}});
const cells = render(state);
assert.equal(cells[0].value, '{current}'); assert.equal(cells[0].unit, '遍');
assert.equal(cells[0].detail, {json.dumps(detail)});
assert.equal(summarize(state).lastCompletedPass, {json.dumps(completed)});
assert.equal(cells[1].value, {json.dumps('3.0' if completed else '—')});
assert.equal(cells[2].value, {json.dumps('75' if completed else '—')});
if ({json.dumps(completed)} === null) assert.ok(cells.slice(1).every(cell => cell.detail === ''));
view.dispose(); dom.window.close();
''')


@pytest.mark.parametrize('mode,detail', [('idle', '空闲'), ('demo', '示范中'),
                                       ('estop', '已急停'), ('fault', '故障')])
def test_kpi_outside_practice_shows_mode(mode, detail):
    jsdom_script(KPI_FIXTURE + f'''
const cells = render({{...base, mode:'{mode}', passes:[{{pass:4, result:{{mean_mm:3, max_mm:4}}}}]}});
assert.equal(cells[0].detail, {json.dumps(detail)});
view.dispose(); dom.window.close();
''')


def test_kpi_correction_summary_groups_targets_and_keeps_signed_maximum_unit():
    jsdom_script(KPI_FIXTURE + r'''
const items = [
 {target:'J1', delta:-.15, unit:'deg'}, {target:'夹爪', delta:-.4, unit:'mm'},
 {target:'J1', delta:-.20, unit:'deg'}, {target:'J2', delta:.3, unit:'deg'},
 {target:'J1', delta:.19, unit:'deg'}, {target:'夹爪', delta:.6, unit:'mm'},
 {target:'J1', delta:-.12, unit:'deg'}, {target:'J2', delta:-.25, unit:'deg'},
];
let state = reduce(base, {type:'correction', pass:4, applied:true, items});
state = reduce(state, {type:'correction', pass:1, applied:true, items:[{target:'J6', delta:9, unit:'deg'}]});
const before = JSON.stringify(state), cells = render(state);
assert.equal(cells[3].value, '2'); assert.equal(cells[3].unit, '次');
assert.equal(cells[3].detail, '第 4 遍：J1 4 处，最大 −0.20°；夹爪 2 处，最大 +0.60 mm；J2 2 处，最大 +0.30°');
assert.equal(JSON.stringify(state), before);
view.dispose(); dom.window.close();
''')


@pytest.mark.parametrize('items', ['[]', 'undefined'])
def test_kpi_correction_without_items_needs_no_correction(items):
    jsdom_script(KPI_FIXTURE + f'''
const state = reduce(base, {{type:'correction', pass:4, applied:false, items:{items}}});
const cells = render(state);
assert.equal(cells[3].value, '0'); assert.equal(cells[3].unit, '次');
assert.equal(cells[3].detail, '第 4 遍：无需修正');
view.dispose(); dom.window.close();
''')


@pytest.mark.parametrize('offline', ["link:{online:false}", 'hello:null'])
def test_kpi_offline_clears_all_values_details_units_and_levels(offline):
    jsdom_script(KPI_FIXTURE + f'''
const state = reduce(base, {{type:'pass_result', pass:4, mean_mm:12, max_mm:15, valid_nodes:4, total_nodes:4}});
render(state);
assert.deepEqual(render({{...state, {offline}}}), Array.from({{length:4}}, () => ({{value:'—', unit:'', detail:'离线', level:'none'}})));
assert.equal(document.querySelector('.kpi .v.badc'), null);
view.dispose(); dom.window.close();
''')


FEED_FIXTURE = r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const dom = new JSDOM(fs.readFileSync(root+'/rearm/ui/static/index.html','utf8'));
globalThis.document = dom.window.document;
const {mount} = await import('./trainer/views/feed.js');
const {initialState, reduce} = await import('./trainer/store.js');
const feed = document.querySelector('#feed'), view = mount(feed);
let state = {...initialState(), link:{online:true}, hello:{sim:true}};
const result = {type:'pass_result', pass:4, t:4000, mean_mm:4.3, max_mm:6, valid_nodes:4, total_nodes:4};
const correction = {type:'correction', pass:4, t:4100, applied:true,
 items:[-.15, -.20, .19, -.12].map(delta => ({target:'J1', delta, unit:'deg'}))};
const finished = {type:'event', name:'pass_finished', t:4200, text:'第 4 遍结束，4/4 个节点测量有效。', level:'info'};
const render = () => view.render(state);
const receive = message => { state = reduce(state, message); render(); };
const rows = () => [...feed.querySelectorAll('.ev')];
const texts = () => rows().map(row => row.querySelector('span').textContent);
'''


@pytest.mark.parametrize('order', ['rcf', 'rfc', 'crf', 'cfr', 'frc', 'fcr'])
def test_feed_merges_pass_result_correction_and_host_finished_in_any_order(order):
    jsdom_script(FEED_FIXTURE + f'''
const messages = {{r:result, c:correction, f:finished}};
for (const key of '{order}') receive(messages[key]);
assert.deepEqual(texts(), ['第 4 遍：平均 4.3 mm · 修正 J1 4 处，最大 −0.20°']);
assert.equal(rows()[0].querySelector('i').className, 'busy');
receive({{...finished, pass:4, t:4300, text:'主机确认完成'}});
assert.equal(rows().length, 1);
const {{mount:mountKpis}} = await import('./trainer/views/kpis.js');
const {{summarize}} = await import('./trainer/metrics.js');
const kpis = mountKpis(document.querySelector('.kpis'));
kpis.render(state, summarize(state));
assert.equal(document.querySelectorAll('.kpi .d')[3].textContent,
 '第 4 遍：' + texts()[0].split(' · 修正 ')[1]);
kpis.dispose(); view.dispose(); dom.window.close();
''')


def test_feed_late_correction_updates_existing_row_without_changing_time_or_order():
    jsdom_script(FEED_FIXTURE + r'''
receive(result);
const original = rows()[0], time = original.querySelector('time').textContent;
assert.deepEqual(texts(), ['第 4 遍：平均 4.3 mm']);
receive({type:'event', t:4500, text:'已急停', level:'bad'});
receive({...correction, t:6000});
assert.equal(rows().length, 2); assert.equal(rows()[1], original);
assert.equal(original.querySelector('time').textContent, time);
assert.deepEqual(texts(), ['已急停', '第 4 遍：平均 4.3 mm · 修正 J1 4 处，最大 −0.20°']);
assert.equal(rows()[0].querySelector('i').className, 'bad');
render(); assert.equal(rows()[1], original);
view.dispose(); dom.window.close();
''')


def test_feed_two_passes_keep_independent_results_corrections_and_icons():
    jsdom_script(FEED_FIXTURE + r'''
receive(result); receive(finished);
receive({...result, pass:5, t:5000, mean_mm:2, max_mm:3});
receive({...correction, pass:5, t:5100, applied:false, items:[]});
receive({...finished, pass:5, t:5200, text:'第 5 遍结束'});
const latest = rows()[0];
receive({...correction, t:6000});
assert.deepEqual(texts(), ['第 5 遍：平均 2.0 mm · 无需修正', '第 4 遍：平均 4.3 mm · 修正 J1 4 处，最大 −0.20°']);
assert.deepEqual(rows().map(row => row.querySelector('i').className), ['ok', 'busy']);
assert.equal(rows()[0], latest);
view.dispose(); dom.window.close();
''')


def test_feed_preserves_other_events_and_unmatched_host_finished():
    jsdom_script(FEED_FIXTURE + r'''
receive(result); receive(correction); receive(finished);
const events = [
 {text:'示范开始', level:'busy'}, {text:'示范结束', level:'ok'},
 {text:'练习开始', level:'busy'}, {text:'练习停止', level:'ok'},
 {text:'已急停', level:'bad'}, {text:'连接断开', level:'bad'},
 {text:'连接恢复', level:'ok'}, {text:'激光状态不一致', level:'warning'},
 {name:'custom', pass:4, text:'第 4 遍主机其它事件', level:'info'},
 {name:'pass_finished', pass:3, text:'第 3 遍结束', level:'info'},
 {name:'pass_finished', text:'主机未标明遍号', level:'info'},
 {type:'error', name:'pass_finished', pass:4, msg:'主机出错'},
 {name:'custom', text:'<img src=x onerror=alert(1)>', level:'error'},
];
events.forEach((event, i) => receive({type:'event', t:5000+i, ...event}));
assert.equal(rows().length, events.length + 1);
assert.deepEqual(texts().slice(0, -1), events.map(event => event.text || event.msg).reverse());
assert.deepEqual(rows().slice(0, -1).map(row => row.querySelector('i').className),
 events.map(event => event.type === 'error' || ['error','warning'].includes(event.level) ? 'bad' : event.level).reverse());
assert.equal(feed.querySelector('img'), null);
receive({...finished, t:7000, text:'第 3 遍结束，4/4 个节点测量有效。'});
assert.ok(texts().includes('第 3 遍结束，4/4 个节点测量有效。'));
view.dispose(); dom.window.close();
''')


@pytest.mark.parametrize('fields,hello,expected', [
    ({'max_mm': 5}, {}, 'ok'),
    ({'max_mm': 5.1}, {}, 'busy'),
    ({'max_mm': 4, 'valid_nodes': 3}, {}, 'busy'),
    ({'mean_mm': None, 'max_mm': None, 'valid_nodes': 0}, {}, 'busy'),
    ({'max_mm': 4, 'below_threshold': False}, {}, 'busy'),
    ({'max_mm': 8, 'below_threshold': True}, {}, 'ok'),
    ({'max_mm': 6}, {'threshold_mm': 7}, 'ok'),
])
def test_feed_status_reuses_pass_threshold_rules(fields, hello, expected):
    jsdom_script(FEED_FIXTURE + f'''
state.hello = {{...state.hello, ...{json.dumps(hello)}}};
receive({{...result, ...{json.dumps(fields)}}});
assert.equal(rows()[0].querySelector('i').className, '{expected}');
view.dispose(); dom.window.close();
''')


@pytest.mark.parametrize('size', [(640, 480), (320, 240), (900, 360)])
def test_camera_html_label_avoids_all_corner_chips_and_uses_letterboxing(size):
    jsdom_script(r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const dom=new JSDOM(fs.readFileSync(root+'/rearm/ui/static/index.html','utf8'));
for(const name of ['document','window'])globalThis[name]=dom.window[name];
const [width,height]=SIZE;
const rect=(left,top,width,height)=>({left,top,width,height,right:left+width,bottom:top+height});
dom.window.Element.prototype.getBoundingClientRect=function(){
 if(this.classList.contains('trainer-spot-label'))return rect(0,0,70,24);
 const boxes={chipstate:[0,0,120,40],chiplaser:[width-100,0,100,40],chipver:[0,height-40,80,40],chiperr:[width-120,height-40,120,40]};
 return boxes[this.id]?rect(...boxes[this.id]):rect(0,0,width,height);
};
const ctx=new Proxy({measureText:t=>({width:t.length*10})},{get:(o,p)=>o[p]??(()=>{})});
dom.window.HTMLCanvasElement.prototype.getContext=()=>ctx;
globalThis.getComputedStyle=()=>({fontSize:'18px',getPropertyValue:()=> '#888888'});
const {mount}=await import('./trainer/views/camera.js');
const {initialState}=await import('./trainer/store.js');
const view=mount(document.querySelector('#cam'));
const intersects=(a,b)=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;
for(const [x,y] of [[15,15],[width-15,15],[15,height-15],[width-15,height-15],[width/2,height*.56]]){
 const s={...initialState(),link:{online:true},hello:{sim:true,camera:{width,height}},demo:{nodes:[{id:1,ref_spot_px:[x,y]}]},
  passes:[{nodes:{1:{node:1,valid:true,t:1,spot_px:[x,y],dev_norm_mm:2.6}}}]};
 view.render(s,{thresholdMm:5});
 const label=document.querySelector('.trainer-spot-label');assert.equal(label.hidden,false);
 assert.equal(document.querySelector('#overlay text'),null);assert.equal(document.querySelector('#overlay').getAttribute('viewBox'),`0 0 ${width} ${height}`);
 const actual=rect(parseFloat(label.style.left),parseFloat(label.style.top),70,24);
 assert.ok(actual.left>=0&&actual.right<=width&&actual.top>=0&&actual.bottom<=height);
 for(const id of ['chipstate','chiplaser','chipver','chiperr'])assert.ok(!intersects(actual,document.getElementById(id).getBoundingClientRect()),id);
 if(x!==width/2)assert.ok([...document.querySelectorAll('#overlay circle')].every(el=>el.getAttribute('visibility')==='hidden'));
}
view.render(initialState(),{});assert.equal(document.querySelector('.trainer-spot-label').hidden,true);
view.dispose();assert.equal(document.querySelector('.trainer-spot-label'),null);
dom.window.close();
'''.replace('SIZE', json.dumps(size)))


def test_show_joint_columns_and_fonts_are_not_limited_to_short_screens():
    css = (TRAINER / 'trainer.css').read_text()
    assert '@media(min-width:1081px) and (max-height:800px)' not in css
    assert 'html[data-trainer="on"][data-mode="show"] #joints{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))' in css
    show_joint = re.search(r'html\[data-trainer="on"\]\[data-mode="show"\] \.joint\{([^}]+)', css).group(1)
    assert 'margin:0' in show_joint and 'font-size:var(--fs-sm)' in show_joint
    label = re.search(r'\.trainer-spot-label\{([^}]+)', css).group(1)
    assert 'font-size:var(--fs-sm)' in label and 'position:absolute' in label


INTEGRATION = r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const html=fs.readFileSync(root+'/rearm/ui/static/index.html','utf8');
const dom=new JSDOM(html,{url:'http://localhost/#home',pretendToBeVisual:true});
for(const name of ['window','document','location','CustomEvent','Event','HTMLElement'])globalThis[name]=dom.window[name];
let now=1700000000000, serial=0, tasks=new Map(), frames=new Map();
Date.now=()=>now;
globalThis.setInterval=(fn,ms)=>{const id=++serial;tasks.set(id,{fn,ms,at:now+ms});return id;};
globalThis.clearInterval=id=>tasks.delete(id);
globalThis.requestAnimationFrame=fn=>{const id=++serial;frames.set(id,fn);return id;};
globalThis.cancelAnimationFrame=id=>frames.delete(id);
function flush(){const queue=[...frames.values()];frames.clear();queue.forEach(fn=>fn());}
function advance(ms){const end=now+ms;while(true){const first=[...tasks].sort((a,b)=>a[1].at-b[1].at)[0];if(!first||first[1].at>end)break;const [id,task]=first;now=task.at;task.at+=task.ms;task.fn();flush();}now=end;flush();}
const context=new Proxy({measureText:s=>({width:s.length*10})},{get:(o,p)=>o[p]??(()=>{})});
dom.window.HTMLCanvasElement.prototype.getContext=()=>context;
dom.window.HTMLElement.prototype.getBoundingClientRect=()=>({width:500,height:300});
globalThis.getComputedStyle=()=>({getPropertyValue:name=>name==='--sans'?'sans-serif':'#888888',fontSize:'18px'});
globalThis.WebSocket=class{constructor(){throw Error('No real sockets');}};
globalThis.fetch=()=>{throw Error('No real fetch');};
const { initTrainer }=await import(root+'/rearm/ui/static/modules/trainer/trainer.js');
const calls=[],overlays=[];
const trainer=initTrainer({twin:{update:f=>calls.push(f),setOverlay:o=>overlays.push(o)},params:new URLSearchParams()});
assert.equal(calls.length,0);flush();assert.equal(calls.length,1);assert.equal(document.querySelectorAll('#joints .joint').length,7);assert.equal(document.querySelector('.trainer-source').textContent,'模拟');
const click=action=>document.querySelector(`[data-trainer-action="${action}"]`).click();
click('demo');await Promise.resolve();await Promise.resolve();flush();assert.equal(trainer.state().mode,'demo');
advance(3000);click('demo');await Promise.resolve();await Promise.resolve();flush();assert.equal(trainer.state().mode,'idle');
click('practice');await Promise.resolve();await Promise.resolve();flush();assert.equal(trainer.state().mode,'practice');
advance(40000);await Promise.resolve();await Promise.resolve();flush();
const completed=trainer.state().passes.filter(p=>p.result);assert.ok(completed.length>=5);assert.ok(completed.at(-1).result.mean_mm<completed[0].result.mean_mm);
assert.equal(calls.at(-1).q_rad.length,6);assert.equal(calls.at(-1).mode,'sim');assert.ok(overlays.at(-1).demoPath.length);assert.ok(overlays.at(-1).nodes.length===4);assert.ok(overlays.at(-1).runPath.length);
assert.ok(document.querySelector('#feed').textContent.includes('遍：平均'));
assert.ok(document.querySelector('#diag').textContent.includes('目标角'));
assert.deepEqual([...document.querySelectorAll('.trainer-correction-items li span:first-child')].map(el=>el.textContent),[1,2,3,4].map(n=>`J1 · 节点 ${n}`));
assert.ok(!document.querySelector('#diag').textContent.includes('deg'));
assert.equal(document.querySelector('[data-trainer-action="laser"]').disabled,true);
assert.equal(document.querySelector('#errchart').getAttribute('aria-label').includes('偏差'),true);

click('practice');await Promise.resolve();await Promise.resolve();flush();
click('laser');await Promise.resolve();await Promise.resolve();flush();assert.equal(trainer.state().laser.on,true);assert.equal(document.querySelector('.trainer-laser-banner').hidden,false);
let cmdCount=trainer.source.commands().length;
window.dispatchEvent(new Event('pagehide'));await Promise.resolve();flush();assert.ok(trainer.source.commands().slice(cmdCount).some(c=>c.cmd==='laser_off'));assert.equal(trainer.state().laser.on,false);
click('laser');await Promise.resolve();flush();assert.equal(trainer.state().laser.on,true);
now+=250;cmdCount=trainer.source.commands().length;
Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));await Promise.resolve();flush();
assert.ok(trainer.source.commands().slice(cmdCount).some(c=>c.cmd==='laser_off'));
Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));flush();
click('laser');await Promise.resolve();flush();assert.equal(trainer.state().laser.on,true);
now+=250;cmdCount=trainer.source.commands().length;location.hash='overview';window.dispatchEvent(new Event('hashchange'));await Promise.resolve();flush();assert.ok(trainer.source.commands().slice(cmdCount).some(c=>c.cmd==='laser_off'));
assert.equal(document.querySelector('[data-trainer-action="demo"]').disabled,true);
location.hash='home';window.dispatchEvent(new Event('hashchange'));flush();
now+=250;document.getElementById('estop').disabled=false;document.getElementById('estop').click();await Promise.resolve();flush();assert.equal(trainer.state().mode,'estop');assert.equal(trainer.state().laser.on,false);
for(const estop of [true,false])document.dispatchEvent(new CustomEvent('rearm:state',{detail:{state:{estop}}}));await Promise.resolve();flush();assert.equal(trainer.state().mode,'idle');
trainer.dispose();assert.equal(document.documentElement.dataset.claim,undefined);assert.equal(document.querySelector('[data-cmd="selfcheck"]').hidden,false);assert.equal(document.getElementById('diagtitle').textContent,'诊断候选');assert.equal(document.querySelectorAll('.trainer-controls').length,0);assert.equal(tasks.size,0);

// no twin still works; an unreachable host never selects the mock
let requests=[];globalThis.fetch=async(...args)=>{requests.push(args);return {json:async()=>({ok:false,code:'network'})};};
const offline=initTrainer({twin:null,params:new URLSearchParams({backend:'ws://example.invalid'})});flush();assert.equal(offline.source.kind,'host');assert.equal(offline.state().link.online,false);assert.ok([...document.querySelectorAll('.trainer-controls button')].every(b=>b.disabled));assert.match(document.querySelector('#cam').textContent,/离线/);offline.dispose();

dom.window.close();
'''


def test_app_and_trainer_claims_coexist_and_legacy_still_renders():
    jsdom_script(r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const dom=new JSDOM(fs.readFileSync(root+'/rearm/ui/static/index.html','utf8'), {url:'http://localhost/?legacy=1#home',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window, queue=[];
const ctx=new Proxy({measureText:t=>({width:t.length*8})},{get:(o,p)=>o[p]??(()=>{})});
w.HTMLCanvasElement.prototype.getContext=()=>ctx;
w.HTMLElement.prototype.getBoundingClientRect=()=>({width:600,height:300});
w.matchMedia=()=>({matches:false,addEventListener(){}});
w.requestAnimationFrame=fn=>{queue.push(fn);return queue.length;};
w.setInterval=()=>1;w.clearInterval=()=>{};
w.fetch=()=>new Promise(()=>{});let socket;
w.WebSocket=class{constructor(){socket=this;}};
w.eval(fs.readFileSync(root+'/rearm/ui/static/app.js','utf8'));
const state={simulation:true,recent:[],versions:[],head:{},stats:{history:[]},events:[],estop:false,state:'正常',shots:0};
const snapshot=()=>{socket.onmessage({data:JSON.stringify({kind:'snapshot',data:{snapshot:state}})});const q=queue.splice(0);q.forEach(fn=>fn());};
snapshot();
assert.equal(w.document.querySelectorAll('#joints .joint').length,3);
assert.match(w.document.getElementById('k-comp-d').textContent,/重训补偿/);
assert.equal(w.document.getElementById('estop').disabled,false);
const originalLabel=w.document.getElementById('errchart').getAttribute('aria-label');
w.document.documentElement.dataset.claim='kpis joints feed errchart diag cam actions';
for(const id of ['k-err','joints','feed','diag','chipstate','chiplaser','chipver','chiperr'])w.document.getElementById(id).textContent='owned:'+id;
w.document.getElementById('errchart').setAttribute('aria-label','owned chart');
const calls=[];ctx.clearRect=(...a)=>calls.push(a);snapshot();
for(const id of ['k-err','joints','feed','diag','chipstate','chiplaser','chipver','chiperr'])assert.equal(w.document.getElementById(id).textContent,'owned:'+id);
assert.equal(w.document.getElementById('errchart').getAttribute('aria-label'),'owned chart');
assert.equal(w.document.getElementById('estop').disabled,false);
const before=calls.length;w.document.getElementById('errchart').onmouseleave();assert.equal(calls.length,before);
socket.onclose();for(const fn of queue.splice(0))fn();assert.equal(w.document.getElementById('chipstate').textContent,'owned:chipstate');
delete w.document.documentElement.dataset.claim;snapshot();assert.equal(w.document.querySelectorAll('#joints .joint').length,3);
assert.equal(w.document.getElementById('errchart').getAttribute('aria-label'),originalLabel);
dom.window.close();
''')


def test_views_escape_corrections_invalid_axes_and_camera_overlay():
    jsdom_script(r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const dom=new JSDOM(fs.readFileSync(root+'/rearm/ui/static/index.html','utf8'));
for(const name of ['document','window','CustomEvent'])globalThis[name]=dom.window[name];
const ctx=new Proxy({measureText:t=>({width:t.length*10})},{get:(o,p)=>o[p]??(()=>{})});
dom.window.HTMLCanvasElement.prototype.getContext=()=>ctx;
dom.window.HTMLElement.prototype.getBoundingClientRect=()=>({width:640,height:480});
globalThis.getComputedStyle=()=>({fontSize:'18px',getPropertyValue:()=> '#888888'});
const {mount:corrections}=await import(root+'/rearm/ui/static/modules/trainer/views/corrections.js');
const {mount:joints}=await import(root+'/rearm/ui/static/modules/trainer/views/joints.js');
const {mount:camera}=await import(root+'/rearm/ui/static/modules/trainer/views/camera.js');
const {initialState}=await import(root+'/rearm/ui/static/modules/trainer/store.js');
const s={...initialState(),link:{online:true},hello:{sim:true,camera:{url:null}},joint:{q:[0,-1,-1,0,0,0],valid:[true,true,false,true,true,true],temp:[30,40,28],current:[.2,-.7,.3],gripper_mm:28.5},
 demo:{nodes:[{id:1,ref_spot_px:[310,240]}]},passes:[{pass:1,nodes:{1:{node:1,valid:true,t:2,spot_px:[320,250],dev_norm_mm:3.2}},
 correction:{pass:1,applied:true,llm_text:'<img src=x onerror=alert(1)>',items:[{target:'J1',delta:-.1,unit:'deg'}]}}]};
corrections(document.querySelector('#diag').closest('.card')).render(s);
assert.equal(document.querySelector('#diag img'),null);assert.match(document.querySelector('#diag').textContent,/<img src=x/);
joints(document.querySelector('.jointcard')).render(s);
assert.match(document.querySelectorAll('#joints .joint')[2].textContent,/无效/);
assert.match(document.querySelector('.envrow').textContent,/40.0 °C/);assert.match(document.querySelector('.envrow').textContent,/0.70 A/);
const view=camera(document.querySelector('#cam'));view.render(s,{thresholdMm:5,laserMismatch:true});
assert.equal(document.querySelectorAll('#overlay circle').length,2);assert.equal(document.querySelector('#overlay rect'),null);
assert.match(document.querySelector('.trainer-spot-label').textContent,/3.2 mm/);assert.equal(document.querySelector('#overlay text'),null);assert.match(document.querySelector('#chiplaser').textContent,/不一致/);
view.render({...s,link:{online:false}},{thresholdMm:5});assert.equal(document.querySelector('#overlay').children.length,0);
dom.window.close();
''')


def test_loader_legacy_missing_twin_and_failed_trainer_use_actual_main():
    jsdom_script(r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const html=fs.readFileSync(root+'/rearm/ui/static/index.html','utf8');
const code=fs.readFileSync(root+'/rearm/ui/static/modules/main.js','utf8').replaceAll('import.meta.url',JSON.stringify('http://localhost/static/modules/main.js')).replaceAll('import(', 'load(');
for(const scenario of [{query:'legacy=1'}, {query:''}, {query:'twin=off'}, {query:'',fail:true}]){
 const dom=new JSDOM(html,{url:'http://localhost/?'+scenario.query});
 for(const name of ['document','window','location','CustomEvent'])globalThis[name]=dom.window[name];
 const append=document.head.appendChild.bind(document.head);document.head.appendChild=link=>{const value=append(link);queueMicrotask(()=>link.onload?.());return value;};
 const imported=[],twin={update(){},refreshTheme(){},dispose(){}}, calls=[];let received=null,themes=0;
 document.addEventListener('rearm:theme',()=>themes++);
 const load=async path=>{
  imported.push(path);
  if(path.includes('twin/twin'))return {createTwin:async()=>twin};
  if(path.includes('datasource'))return {sourceFromParams:()=>{calls.push('source');return {subscribe(){},start(){calls.push('start');}};}};
  if(path.includes('trainer/trainer'))return {initTrainer:args=>{received=args;document.documentElement.dataset.claim='kpis';if(scenario.fail)throw Error('expected trainer failure');return {};}};
  if(path.includes('guide'))return {initGuide(){}};
  if(path.includes('presentation'))return {initPresentation(){}};
  throw Error(path);
 };
 const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
 await new AsyncFunction('load',code)(load);
 if(scenario.query==='legacy=1'){
  assert.equal(imported.some(p=>p.includes('trainer')),false);assert.ok(imported.some(p=>p.includes('guide')));assert.deepEqual(calls,['source','start']);
 }else{
  assert.equal(imported.some(p=>p.includes('guide')),false);assert.deepEqual(calls,[]);assert.equal(received.twin,scenario.query==='twin=off'?null:twin);
  if(scenario.fail){assert.equal(document.documentElement.dataset.claim,undefined);assert.ok(themes>=2);}
 }
 dom.window.close();
}
''')


def test_kpi_threshold_uses_summary_result_keeps_mean_and_handles_no_valid_nodes():
    jsdom_script(r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const dom=new JSDOM(fs.readFileSync(root+'/rearm/ui/static/index.html','utf8'));
globalThis.document=dom.window.document;
const {mount}=await import('./trainer/views/kpis.js');
const {initialState}=await import('./trainer/store.js');
const {summarize}=await import('./trainer/metrics.js');
const view=mount(document.querySelector('.kpis')),cell=document.querySelectorAll('.kpi')[1];
for(const [result,text,level,value] of [
 [{mean_mm:2,max_mm:6.9,valid_nodes:4,total_nodes:4},'▲ 未达标（最大 6.9 mm）','bad','2.0'],
 [{mean_mm:2,max_mm:5,valid_nodes:4,total_nodes:4},'✓ 达标（最大 ≤ 5 mm）','ok','2.0'],
 [{mean_mm:2,max_mm:4,valid_nodes:3,total_nodes:4},'▲ 未达标（最大 4.0 mm）','bad','2.0'],
 [{mean_mm:null,max_mm:null,valid_nodes:0,total_nodes:4,below_threshold:false},'▲ 未达标（最大 — mm）','bad','—'],
 [{mean_mm:2,max_mm:4,valid_nodes:4,total_nodes:4,below_threshold:false},'▲ 未达标（最大 4.0 mm）','bad','2.0'],
 [{mean_mm:2,max_mm:6.9,valid_nodes:3,total_nodes:4,below_threshold:true},'✓ 达标（最大 ≤ 5 mm）','ok','2.0'],
]) {
 const s={...initialState(),link:{online:true},hello:{sim:true},passes:[{pass:1,nodes:{},result}]};
 view.render(s,{...summarize(s),thresholdMm:5});
 assert.equal(cell.querySelector('.d').textContent,text);assert.equal(cell.dataset.level,level);
 assert.equal(cell.querySelector('.v').childNodes[0].textContent,value);
 assert.equal(cell.querySelector('.v').classList.contains('badc'),level==='bad');
}
view.render({...initialState(),link:{online:true},hello:{sim:true}},{...summarize(initialState()),thresholdMm:5});
assert.equal(cell.dataset.level,'none');assert.ok(!cell.textContent.includes('达标'));
view.dispose();dom.window.close();
''')


@pytest.mark.parametrize('reason,text', [('spot_not_found', '未找到光点'), ('depth_invalid', '深度无效'),
                                       ('timeout', '测量超时'), ('other', '测量无效'), (None, '测量无效'),
                                       ('toString', '测量无效'), ('__proto__', '测量无效')])
def test_camera_invalid_current_node_hides_all_marks_and_clears_on_next_node(reason, text):
    jsdom_script(INTEGRATION.split('const calls=[],overlays=[];')[0] + r'''
const {mount}=await import('./trainer/views/camera.js');
const {initialState,reduce}=await import('./trainer/store.js');
const view=mount(document.querySelector('#cam'));
let s={...initialState(),link:{online:true},hello:{sim:true,camera:{width:640,height:480}},
 demo:{nodes:[{id:1,ref_spot_px:[320,274]},{id:2,ref_spot_px:[320,274]}]}};
const receive=m=>{s=reduce(s,m,now);view.render(s,{thresholdMm:5});};
receive({type:'joint_state',pass:1,node:1,t:1,mode:'practice'});
receive({type:'node_result',pass:1,node:1,t:2,valid:true,spot_px:[330,270],dev_norm_mm:3});
assert.equal(document.querySelectorAll('#overlay circle').length,2);
// 即使无效载荷仍残留坐标，也必须隐藏整套光点、连线、箭头与偏差标签。
receive({type:'node_result',pass:1,node:1,t:3,valid:false,spot_px:[330,270],dev_norm_mm:3,invalid_reason:REASON});
const notice=document.querySelector('.trainer-measurement-status');
assert.equal(notice.hidden,false);assert.equal(notice.textContent,TEXT);
assert.equal(document.querySelector('#overlay').children.length,0);
assert.equal(document.querySelector('.trainer-spot-label').hidden,true);
assert.match(document.querySelector('#chiperr').textContent,/无效/);
// 别处晚到的有效结果不能掩盖当前节点无效；同节点旧结果也不能覆盖。
receive({type:'node_result',pass:2,node:1,t:99,valid:true,spot_px:[330,270]});
receive({type:'node_result',pass:1,node:1,t:2,valid:true,spot_px:[330,270]});
assert.equal(notice.hidden,false);assert.equal(document.querySelector('#overlay').children.length,0);
receive({type:'joint_state',pass:1,node:2,t:4,mode:'practice'});
assert.equal(notice.hidden,true);assert.equal(notice.textContent,'');
assert.equal(document.querySelector('#overlay').children.length,0);
assert.equal(document.querySelector('#chiperr').textContent,'等待测量');
receive({type:'node_result',pass:1,node:2,t:5,valid:true,spot_px:[321,275],dev_norm_mm:1});
assert.equal(document.querySelectorAll('#overlay circle').length,2);
receive({type:'link',online:false});assert.equal(notice.hidden,true);
view.dispose();assert.equal(document.querySelector('.trainer-measurement-status'),null);dom.window.close();
'''.replace('REASON', json.dumps(reason)).replace('TEXT', json.dumps(text)))


def test_trainer_local_laser_clock_hello_delivery_and_guard_recreation():
    jsdom_script(INTEGRATION.split('const calls=[],overlays=[];')[0] + r'''
let socket,seq=0;const requests=[];const hostTime=now+86400000;
globalThis.WebSocket=class{constructor(){socket=this;} close(){}};
globalThis.fetch=async(url,options)=>{requests.push(JSON.parse(options.body));return {json:async()=>({ok:true})};};
const trainer=initTrainer({params:new URLSearchParams({backend:'ws://example.invalid/ws'})});
socket.onopen();
const emit=data=>{socket.onmessage({data:JSON.stringify({v:1,seq:++seq,t:hostTime+seq,...data})});flush();};
emit({type:'hello',sim:false,laser_ttl_ms:900,node_timeout_ms:650});
emit({type:'joint_state',mode:'idle',q:[0,0,0,0,0,0]});
emit({type:'laser_state',on:false});
assert.equal(trainer.state().laser.received_at,now);
const click=()=>document.querySelector('[data-trainer-action="laser"]').click();
const commandAt=now;click();await Promise.resolve();await Promise.resolve();flush();
assert.equal(trainer.state().laserCommand.t,commandAt);
assert.equal(requests.at(-1).ttl_ms,900);
advance(299);assert.equal(requests.filter(r=>r.cmd==='laser_renew').length,0);
advance(1);assert.equal(requests.at(-1).cmd,'laser_renew');assert.equal(requests.at(-1).ttl_ms,900);
assert.equal(trainer.state().laserCommand.t,commandAt);
advance(700);emit({type:'laser_state',on:false});assert.ok(!document.querySelector('#chiplaser').textContent.includes('不一致'));
advance(1);emit({type:'laser_state',on:false});assert.match(document.querySelector('#chiplaser').textContent,/不一致/);
window.dispatchEvent(new Event('pagehide'));await Promise.resolve();flush();
advance(250);click();await Promise.resolve();await Promise.resolve();flush();
// 生命周期重建 guard 后仍使用已归并 hello；旧 hello 不能重新配置。
assert.equal(requests.at(-1).cmd,'laser_on');assert.equal(requests.at(-1).ttl_ms,900);
emit({type:'hello',t:hostTime-1,laser_ttl_ms:6000,node_timeout_ms:9000});
advance(300);assert.equal(requests.at(-1).cmd,'laser_renew');assert.equal(requests.at(-1).ttl_ms,900);
emit({type:'joint_state',mode:'practice',pass:1,node:1,settled:true,q:[0,0,0,0,0,0]});
advance(649);assert.notEqual(requests.at(-1).cmd,'laser_off');advance(1);
assert.equal(requests.at(-1).cmd,'laser_off');trainer.dispose();dom.window.close();
''')


def test_trainer_mock_disabling_laser_mid_practice_clears_twin_and_camera_spots():
    jsdom_script(INTEGRATION.split('const calls=[],overlays=[];')[0] + r'''
const overlays=[];
const trainer=initTrainer({twin:{update(){},setOverlay:o=>overlays.push(o)}});flush();
await trainer.source.send('demo_start');advance(3000);await trainer.source.send('demo_stop');
await trainer.source.send('practice_start');flush();
let elapsed=0;
while(!overlays.at(-1).spots.measured){advance(50);elapsed+=50;assert.ok(elapsed<10000);}
assert.equal(document.querySelectorAll('#overlay circle').length,2);
const send=trainer.source.send.bind(trainer.source);
trainer.source.send=(cmd,args)=>['laser_on','laser_renew'].includes(cmd)?Promise.resolve({ok:true}):send(cmd,args);
await send('laser_off');
while(document.querySelector('.trainer-measurement-status').hidden){advance(50);elapsed+=50;assert.ok(elapsed<20000);}
assert.equal(document.querySelector('.trainer-measurement-status').textContent,'未找到光点');
assert.deepEqual(overlays.at(-1).spots,{});assert.equal(document.querySelector('#overlay').children.length,0);
assert.equal(document.querySelector('.trainer-spot-label').hidden,true);
const failed=trainer.state().passes.flatMap(p=>Object.values(p.nodes)).find(n=>n.valid===false);
assert.ok(failed);let next=false;
while(!next){advance(50);elapsed+=50;assert.ok(elapsed<30000);
 const current=trainer.state().currentNode;next=current&&(current.pass!==failed.pass||current.node!==failed.node);
}
assert.equal(document.querySelector('.trainer-measurement-status').hidden,true);
assert.equal(document.querySelector('.trainer-measurement-status').textContent,'');
assert.deepEqual(overlays.at(-1).spots,{});trainer.dispose();assert.equal(tasks.size,0);dom.window.close();
''')
