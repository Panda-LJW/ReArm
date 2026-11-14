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


def test_protocol_field_manifest_tracks_accesses_and_t4_payloads():
    text = '\n'.join(p.read_text() for p in TRAINER.rglob('*.js'))
    # 包括 ?. 访问和图表遍历时的动态字段名；排除已知的 UI / store 槽位。
    accessed = set(re.findall(r'(?:message|joint|node|result|correction|item|reply|first|last|row|expected|actual)\??\.(\w+)', text))
    accessed -= {'nodes', 'result', 'correction', 'parentNode', 'append', 'classList', 'title'}
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
assert.ok(document.querySelector('#feed').textContent.includes('遍结束：平均'));
assert.ok(document.querySelector('#diag').textContent.includes('目标角'));
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
assert.match(document.querySelector('#overlay text').textContent,/3.2 mm/);assert.match(document.querySelector('#chiplaser').textContent,/不一致/);
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
