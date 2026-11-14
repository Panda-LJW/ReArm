"""后端适配：R61 样本、假 fetch/时钟及现有 Node/JSDOM 宿主，无硬件请求。"""
import json
from pathlib import Path

import pytest

from tests.test_console_shell import DOM
from tests.test_trainer_views import jsdom_script, node

SAMPLE = json.loads((Path(__file__).parent / 'fixtures/backend_state_r61.json').read_text())
HARNESS = 'const sample = ' + json.dumps(SAMPLE, ensure_ascii=False) + ';\n' + r'''
const {createBackendSource}=await import('./datasource/backend-source.js');
const {createStore}=await import('./console/state/store.js');
const {PARTS}=await import('./datasource/fixtures/parts.js');
const {productionSummary,startReason,trainReason,statusWord}=await import('./console/state/selectors.js');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const response=(body=sample,status=200)=>({ok:status>=200&&status<300,status,json:async()=>structuredClone(body)});
function setup(handler=()=>response()) {
  let clockNow=0,nextTimer=0;const scheduled=new Map(),requests=[],messages=[],store=createStore();
  const source=createBackendSource({now:()=>clockNow,
    setTimer(fn,ms){const id=++nextTimer;scheduled.set(id,{fn,ms,at:clockNow+ms});return id;},
    clearTimer:id=>scheduled.delete(id),
    fetch:async(url,options)=>{requests.push({url,...options});return handler(url,options);}});
  source.subscribe(message=>{messages.push(message);store.dispatch(message);});
  async function advance(ms) {
    const end=clockNow+ms;
    while(true){
      const next=[...scheduled.values()].filter(timer=>timer.at<=end).sort((a,b)=>a.at-b.at)[0];
      if(!next)break;clockNow=next.at;next.at+=next.ms;next.fn();await flush();
    }
    clockNow=end;await flush();
  }
  return {source,requests,messages,store,advance,scheduled,last:type=>messages.filter(m=>m.type===type).at(-1)};
}
'''
BASE = "import assert from 'node:assert/strict';\n" + HARNESS


@pytest.mark.parametrize('q7,refs,expected', [
    (9.3326, {'touch': 9.3326, 'open': 2.7266, 'mm_per_rad': 16.6515}, 0),
    # 截短后的参考值算得 109.999809 mm，显示为 110.0 mm。
    (2.7266, {'touch': 9.3326, 'open': 2.7266, 'mm_per_rad': 16.6515}, 109.999809),
    # 按给定公式，(9.3326 - 6.0) × 16.6515 = 55.4927889 mm。
    (6.0, {'touch': 9.3326, 'open': 2.7266, 'mm_per_rad': 16.6515}, 55.4927889),
    (6.0, None, None),
    (2.4, {'touch': 9.3326, 'open': 2.7266, 'mm_per_rad': 16.6515}, None),
    (9.64, {'touch': 9.3326, 'open': 2.7266, 'mm_per_rad': 16.6515}, None),
])
def test_gripper_converts_only_current_torque_refs(q7, refs, expected):
    node(BASE + 'const state=structuredClone(sample);' +
         f'state.telemetry.q_rad[6]={json.dumps(q7)};state.gripper_refs={json.dumps(refs)};' +
         f'const expected={json.dumps(expected)};' + r'''
const h=setup(()=>response(state));h.source.start();await flush();
const joint=h.last('joint_state');
assert.equal(joint.gripper_valid,expected!==null);
if(expected===null)assert.equal(joint.gripper_mm,null);
else assert.ok(Math.abs(joint.gripper_mm-expected)<1e-6);
assert.equal(joint.gripper_source,state.gripper_refs?'当次力矩标定':'未标定');
assert.equal(joint.q.length,6);h.source.stop();
''')


def test_gripper_tolerance_both_directions_and_invalid_or_expired_references():
    node(BASE + r'''
const state=structuredClone(sample),refs={touch:9.3326,open:2.7266,mm_per_rad:16.6515};
state.gripper_refs=refs;const h=setup(()=>response(state));h.source.start();await flush();
async function check(q7,valid,expected) {
  state.telemetry.q_rad[6]=q7;await h.advance(200);const joint=h.last('joint_state');
  assert.equal(joint.gripper_valid,valid);assert.equal(joint.gripper_mm!==null,valid);
  if(valid)assert.ok(Math.abs(joint.gripper_mm-expected)<1e-6);
}
await check(refs.open-.3,true,110);await check(refs.touch+.3,true,.3*refs.mm_per_rad);
await check(refs.open-.30001,false);await check(refs.touch+.30001,false);
state.gripper_refs={touch:refs.open,open:refs.touch,mm_per_rad:refs.mm_per_rad};
await check(refs.open,true,0);await check(refs.touch,true,109.999809);
await check(refs.open-.3,true,.3*refs.mm_per_rad);await check(refs.touch+.3,true,110);
for(const bad of [null,{}, {touch:9,open:2}, {...refs,touch:null}, {...refs,open:'2'},
  {...refs,mm_per_rad:0}, {...refs,mm_per_rad:-1}, {...refs,mm_per_rad:NaN}, {...refs,open:refs.touch}]) {
  state.gripper_refs=bad;await check(6,false);assert.equal(h.last('joint_state').gripper_source,'未标定');
}
state.gripper_refs=refs;
for(const bad of [null,undefined,NaN,Infinity,'6'])await check(bad,false);
state.stale=true;await check(6,false);state.stale=false;await check(6,true,55.4927889);
delete state.gripper_refs;await check(6,false); // 不继承上一帧标定。
state.gripper_refs=refs;state.telemetry=null;await h.advance(200);
assert.equal(h.last('joint_state').gripper_mm,null);assert.equal(h.last('joint_state').gripper_valid,false);
h.source.stop();
''')


def test_sample_maps_six_joints_device_last_pick_and_composes_mock_library():
    node(BASE + r'''
const h=setup(),{source,store,last,requests}=h;source.start();await flush();
assert.equal(source.kind,'backend');assert.equal(last('hello').source,'后端面板');assert.equal(last('hello').sim,false);
assert.equal(last('hello').address,'/backend');assert.equal(last('link').online,true);
const joint=last('joint_state');
for(const [key,backend] of [['q','q_rad'],['dq','dq_rad_s'],['temp','t_rotor_c'],['current','tau_nm']])
  assert.deepEqual(joint[key],sample.telemetry[backend].slice(0,6));
assert.equal(joint.q.length,6);assert.ok(!joint.q.includes(sample.telemetry.q_rad[6]));
assert.deepEqual(joint.valid,Array(6).fill(true));assert.equal(joint.gripper_mm,null);assert.equal(joint.gripper_valid,false);
assert.equal(joint.temp_unit,'°C');assert.equal(joint.current_unit,'N·m');
assert.equal(last('device_state').enabled,false);assert.equal(last('device_state').connected,true);
assert.equal(last('device_state').pose_error_deg,null);
assert.equal(last('device_state').camera.url,'/backend/api/camera/color.mjpg');
assert.deepEqual(store.getState().lastPick,sample.last_pick);
assert.equal(productionSummary(store.getState()).sets,0);assert.equal(store.getState().runs.length,0);
assert.deepEqual(store.getState().workspace.image,{width:640,height:480});assert.deepEqual(store.getState().workspace.props,[]);
assert.equal(store.getState().library.parts.length,PARTS.length);assert.equal(store.getState().archivedTrains.length,5);
for(const [cmd,key,list] of [['part_get','partDocs','parts'],['recipe_get','recipeDocs','recipes']]) {
  const id=store.getState().library[list][0].id;assert.equal((await source.send(cmd,{id})).ok,true);
  assert.equal(store.getState()[key][id].id,id);
}
assert.equal((await source.send('library_get')).ok,true);assert.equal(requests.length,1);
assert.match(startReason(store.getState()),/第一档只读/);assert.match(trainReason(store.getState()),/第一档只读/);
assert.equal(statusWord(store.getState()),'已连接 · 未使能');
assert.equal(h.scheduled.size,1);assert.equal([...h.scheduled.values()][0].ms,200);
source.start();await h.advance(400);assert.equal(requests.length,3);assert.equal(h.messages.filter(m=>m.type==='hello').length,1);
assert.ok(h.messages.every((m,i,all)=>m.v===1&&(!i||m.seq>all[i-1].seq)));
source.stop();assert.equal(h.scheduled.size,0);
''')


def test_stale_missing_partial_telemetry_never_fills_zero_or_claims_valid():
    node(BASE + r'''
let state=structuredClone(sample);const h=setup(()=>response(state));h.source.start();await flush();
state.stale=true;await h.advance(200);
assert.deepEqual(h.last('joint_state').valid,Array(6).fill(false));
assert.deepEqual(h.last('joint_state').q,sample.telemetry.q_rad.slice(0,6));
state.telemetry=null;await h.advance(200);
for(const key of ['q','dq','temp','current'])assert.deepEqual(h.last('joint_state')[key],Array(6).fill(null));
assert.equal(h.last('joint_state').settled,false);
state.stale=false;state.telemetry={q_rad:[0,null,1],dq_rad_s:[null]};await h.advance(200);
assert.deepEqual(h.last('joint_state').q,[0,null,1,null,null,null]);
assert.deepEqual(h.last('joint_state').valid,[true,false,true,false,false,false]);
h.source.stop();
''')


def test_recognition_rotation_unknown_null_confidence_and_bad_geometry():
    node(BASE + r'''
let state=structuredClone(sample);const h=setup(()=>response(state));h.source.start();await flush();
const targets=h.last('recognition').targets;assert.deepEqual(targets.map(t=>t.id),[1,0]);
assert.deepEqual(targets.map(t=>t.name),['薄片','未知物体']);assert.ok(targets.every(t=>t.confidence===null));
const width=(48*Math.cos(Math.PI/15)+48*Math.sin(Math.PI/15))/.687;
const expected=[[220-width/2,260-width/2,width,width],[435-48/.687/2,245-62/.687/2,48/.687,62/.687]];
targets.forEach((target,i)=>target.box_px.forEach((v,j)=>assert.ok(Math.abs(v-expected[i][j])<1e-9)));
state.vision.last.detections[0].mm_per_px=0;state.vision.last.detections[1].center_px=null;
await h.advance(200);assert.ok(h.last('recognition').targets.every(t=>t.box_px===null));
state.vision=null;state.last_pick=null;await h.advance(200);
assert.deepEqual(h.last('recognition').targets,[]);assert.equal(h.store.getState().lastPick,null);
h.source.stop();
''')


def test_three_failures_and_recovery_reset_failure_count():
    node(BASE + r'''
let fail=false;const h=setup(()=>response(sample,fail?502:200));h.source.start();await flush();
fail=true;await h.advance(400);assert.equal(h.last('link').online,true);
await h.advance(200);assert.equal(h.last('link').online,false);
fail=false;await h.advance(200);assert.equal(h.last('link').online,true);
fail=true;await h.advance(400);assert.equal(h.last('link').online,true);
await h.advance(200);assert.equal(h.last('link').online,false);
assert.equal(h.messages.filter(m=>m.type==='hello').length,1);h.source.stop();
''')


def test_hanging_poll_times_out_without_overlap_and_ignores_late_response():
    node(BASE + r'''
let count=0,late;const h=setup(()=>++count===1?response():count===2?new Promise(resolve=>late=resolve):new Promise(()=>{}));
h.source.start();await flush();await h.advance(2800);assert.equal(h.last('link').online,true);assert.equal(count,2);
await h.advance(200);assert.equal(h.last('link').online,false);assert.match(h.last('link').reason,/3 秒/);
await h.advance(200);assert.equal(count,3);assert.equal(h.requests[1].signal.aborted,true);
const messages=h.messages.length;late(response());await flush();assert.equal(h.messages.length,messages);
h.source.stop();assert.equal(h.requests[2].signal.aborted,true);assert.equal(h.scheduled.size,0);
''')


@pytest.mark.parametrize('failure', ["response({},404)", "Promise.reject(new Error('断网'))", "response({})"])
def test_initial_unavailable_state_is_offline_without_mock_pose(failure):
    node(BASE + 'const h=setup(()=>'+failure+');' + r'''
h.source.start();await h.advance(400);assert.equal(h.last('link').online,false);
assert.equal(h.last('hello'),undefined);assert.equal(h.last('joint_state'),undefined);
assert.equal(h.store.getState().joint,null);assert.equal(h.store.getState().library.parts.length,PARTS.length);
h.source.stop();
''')


def test_estop_is_only_post_reset_is_local_and_all_other_writes_are_rejected():
    node(BASE + r'''
const h=setup(url=>response(url.endsWith('/cmd')?{ok:true}:sample));h.source.start();await flush();
for(const cmd of ['run_start','train_start','part_capture','reset_demo','enable','jog','unknown']) {
  const count=h.requests.length,reply=await h.source.send(cmd,{recipe_id:'plate-tube'});
  assert.equal(reply.ok,false);assert.equal(reply.msg,'第一档只读：生产指令由后端第二档提供');assert.equal(h.requests.length,count);
}
const result=await h.source.send('estop',{action:'enable'});assert.equal(result.ok,true);assert.match(result.msg,/已送达/);
const post=h.requests.at(-1);assert.equal(post.url,'/backend/api/cmd');assert.equal(post.method,'POST');
assert.equal(post.headers['Content-Type'],'application/json');assert.deepEqual(JSON.parse(post.body),{action:'estop'});
assert.equal(h.store.getState().phase,'estop');await h.advance(200);assert.equal(h.store.getState().phase,'estop');
assert.equal(h.store.getState().recognition.targets.length,2);
const requests=h.requests.length,reset=await h.source.send('reset_estop');
assert.equal(reset.ok,true);assert.match(reset.msg,/请在后端面板重新使能/);assert.equal(h.requests.length,requests);
assert.equal(h.store.getState().phase,'idle');assert.equal(h.store.getState().device.enabled,false);
assert.equal(h.store.getState().runs.length,0);assert.equal(h.source.commands.at(-1).cmd,'reset_estop');
h.source.stop();assert.equal((await h.source.send('estop')).code,'offline');
''')


@pytest.mark.parametrize('failure', ["response({detail:'后端不可达'},502)", "response({ok:false,msg:'拒绝急停'})", "Promise.reject(new Error('断网'))"])
def test_estop_failures_leave_phase_unchanged_and_return_chinese_feedback(failure):
    node(BASE + "const h=setup(url=>url.endsWith('/cmd')?"+failure+':response());' + r'''
h.source.start();await flush();const reply=await h.source.send('estop');assert.equal(reply.ok,false);
assert.match(reply.msg,/急停失败/);assert.equal(h.store.getState().phase,'idle');h.source.stop();
''')


def test_pending_estop_timeout_stop_and_restart_ignore_old_responses():
    node(BASE + r'''
const resolvers=[];const h=setup(url=>url.endsWith('/cmd')?new Promise(resolve=>resolvers.push(resolve)):response());
h.source.start();await flush();const timed=h.source.send('estop');await h.advance(3000);
assert.match((await timed).msg,/急停失败.*3 秒/);assert.equal(h.store.getState().phase,'idle');
resolvers[0](response({ok:true}));await flush();assert.equal(h.store.getState().phase,'idle');
const stopped=h.source.send('estop');h.source.stop();h.source.start();await flush();
assert.equal((await stopped).ok,false);resolvers[1](response({ok:true}));await flush();
assert.equal(h.store.getState().phase,'idle');assert.equal(h.scheduled.size,1);h.source.stop();
let late;const a=setup(()=>new Promise(resolve=>late=resolve));a.source.start();a.source.stop();
late(response());await flush();assert.equal(a.last('hello'),undefined);assert.equal(a.last('link').online,false);
''')


UI = DOM + HARNESS + r'''
const h=setup();h.source.start();await flush();
const ctx={store:h.store,send:(cmd,args)=>h.source.send(cmd,args)};
const createRoot=id=>{const el=doc.createElement('section');el.dataset.page=id;doc.body.append(el);return el;};
'''


def test_settings_gripper_reading_calibration_source_and_invalid_readings():
    jsdom_script(UI + r'''
const {mount}=await import('./console/pages/settings/index.js');
const rootView=createRoot('settings'),view=mount(rootView,ctx);
const off=h.store.subscribe(state=>view.render(state));tick(32);
const opening=()=>rootView.querySelector('[data-setting="opening"]').textContent;
assert.equal(opening(),'—（来源：未标定）');
sample.gripper_refs={touch:9.3326,open:2.7266,mm_per_rad:16.6515};
for(const [q7,label] of [[6,'55.5 mm'],[9.3326,'0.0 mm'],[2.7266,'110.0 mm'],[20,'—']]) {
  sample.telemetry.q_rad[6]=q7;await h.advance(200);tick(32);
  assert.equal(opening(),`${label}（来源：当次力矩标定）`);
}
sample.telemetry.q_rad[6]=6;sample.stale=true;await h.advance(200);tick(32);
assert.equal(opening(),'—（来源：当次力矩标定）');
sample.stale=false;await h.advance(200);tick(32);assert.match(opening(),/^55.5 mm/);
h.source.stop();tick(32);assert.equal(opening(),'—（来源：当次力矩标定）');
h.source.start();await flush();tick(32);assert.match(opening(),/^55.5 mm/);
sample.gripper_refs=null;await h.advance(200);tick(32);assert.equal(opening(),'—（来源：未标定）');
off();view.dispose();h.source.stop();dom.window.close();
''')


def test_pages_show_backend_details_demo_data_disabled_actions_and_last_pick_without_counts():
    jsdom_script(UI + r'''
const views=[],roots={};
for(const id of ['production','parts','records','settings']) {
  const {mount}=await import(`./console/pages/${id}/index.js`);roots[id]=createRoot(id);views.push(mount(roots[id],ctx));
}
const off=h.store.subscribe(state=>views.forEach(view=>view.render(state)));tick(64);await flush();tick(32);
const setting=key=>roots.settings.querySelector(`[data-setting="${key}"]`).textContent;
assert.equal(setting('source'),'后端面板');assert.equal(setting('address'),'/backend');assert.equal(setting('connection'),'已连接');
assert.equal(setting('arm_connection'),'已连接');assert.equal(setting('enabled'),'未使能');assert.equal(setting('pose_error'),'—');
assert.equal(setting('camera'),'已接入');assert.equal(setting('opening'),'—（来源：未标定）');
for(const id of ['production','parts','records'])assert.match(roots[id].textContent,/演示数据/);
const start=roots.production.querySelector('[data-action="start"]');assert.equal(start.getAttribute('aria-disabled'),'true');
assert.match(start.dataset.reason,/第一档只读/);
const add=[...roots.parts.querySelectorAll('button')].find(el=>el.textContent==='新增零件');
assert.equal(add.getAttribute('aria-disabled'),'true');assert.match(add.dataset.reason,/第一档只读/);
start.click();add.click();assert.ok(!h.source.commands.some(cmd=>['run_start','part_capture','train_start'].includes(cmd.cmd)));
const pick=key=>roots.production.querySelector(`[data-last-pick="${key}"]`).textContent;
assert.equal(pick('held'),'未夹到');assert.equal(pick('reason'),sample.last_pick.reason);
assert.equal(pick('errors'),'17.9 → 6.5 mm');assert.equal(pick('retry'),'是');
assert.equal(roots.production.querySelector('[data-count="sets"]').textContent,'0');
assert.equal(h.store.getState().runs.length,0);
const last=h.last('device_state');h.store.dispatch({...last,seq:last.seq+100,pose_error_deg:1.25,busy:true,busy_action:'pick',enabled:true});
tick(32);assert.equal(setting('pose_error'),'1.25°');assert.equal(setting('busy'),'忙：pick');assert.equal(setting('enabled'),'已使能');
h.source.stop();tick(32);assert.equal(setting('connection'),'未连接');assert.equal(setting('enabled'),'—');
assert.match(roots.production.textContent,/最近抓取（离线前）/);
off();views.forEach(view=>view.dispose());dom.window.close();
''')


@pytest.mark.parametrize('manual', ['', '?camera=%2Fmanual.mjpg', '?camera='])
def test_camera_automatic_freshness_manual_priority_and_null_confidence_labels(manual):
    jsdom_script(UI + 'win.history.replaceState(null,"",'+json.dumps('/'+manual)+');' + r'''
const {mount}=await import('./console/pages/production/views/observe-view.js');
const rootView=createRoot('production');
win.HTMLElement.prototype.getBoundingClientRect=function(){
  if(this.classList.contains('production-camera'))return {width:420,height:300};
  if(this.tagName==='LI')return {width:90,height:26};return {width:100,height:20};
};
const view=mount(rootView),off=h.store.subscribe(state=>view.render(state));tick(64);
const feed=()=>rootView.querySelector('.production-camera-feed img'),status=()=>rootView.querySelector('.production-camera-status').textContent;
const hasManual=win.location.search.includes('camera=');
assert.equal(feed()?.getAttribute('src')??null,hasManual?(win.location.search.endsWith('=')?null:'/manual.mjpg'):'/backend/api/camera/color.mjpg');
const labels=[...rootView.querySelectorAll('.production-targets li')];assert.deepEqual(labels.map(el=>el.textContent),['薄片','未知物体']);
assert.ok(labels.every(el=>!el.textContent.includes('%')));assert.equal(rootView.querySelectorAll('[data-target-box]').length,2);
if(feed())feed().dispatchEvent(new win.Event('load'));tick(32);
assert.equal(rootView.querySelectorAll('[data-object]').length,0);
const old=feed(),device=h.last('device_state');
view.render({...h.store.getState(),device:{...device,camera:{...device.camera,url:null,fresh:false}}});tick(32);
if(hasManual)assert.equal(feed(),old);else {assert.equal(feed(),null);assert.equal(status(),'未接入摄像头');assert.equal(old.hasAttribute('src'),false);}
view.render(h.store.getState());tick(32);if(!hasManual){assert.ok(feed());const active=feed();view.render(h.store.getState());tick(32);assert.equal(feed(),active);}
view.setCameraSource('/explicit.mjpg');view.render(h.store.getState());tick(32);assert.equal(feed().getAttribute('src'),'/explicit.mjpg');
off();view.dispose();h.source.stop();dom.window.close();
''')


def test_main_selects_backend_and_shows_estop_success_failure_and_local_release_feedback():
    jsdom_script(DOM + HARNESS + r'''
win.history.replaceState(null,'','?arm=backend');const requests=[];let fail=false;
globalThis.fetch=async(url,options)=>{requests.push({url,...options});return response(url.endsWith('/cmd')?{ok:!fail,msg:fail?'后端拒绝':''}:sample);};
await import('./console/main.js');await flush();tick(64);
assert.equal(doc.querySelector('[data-setting="source"]').textContent,'后端面板');
assert.match(doc.querySelector('[data-status]').textContent,/已连接.*未使能/);
fail=true;doc.querySelector('[data-action="estop"]').click();await flush();tick(32);
assert.match(doc.querySelector('.console-toasts').textContent,/急停失败.*后端拒绝/);
assert.equal(doc.querySelector('.console-estop-banner').hidden,true);
fail=false;doc.querySelector('[data-action="estop"]').click();await flush();tick(32);
assert.equal(doc.querySelector('.console-estop-banner').hidden,false);
assert.match(doc.querySelector('.console-toasts').textContent,/急停指令已送达后端/);
const posts=requests.filter(r=>r.method==='POST').length;
doc.querySelector('[data-action="reset-estop"]').click();tick(32);
doc.querySelector('dialog [data-action="confirm"]').click();await flush();tick(32);
assert.equal(doc.querySelector('.console-estop-banner').hidden,true);
assert.match(doc.querySelector('.console-toasts').textContent,/请在后端面板重新使能/);
assert.equal(requests.filter(r=>r.method==='POST').length,posts);
assert.ok(requests.every(r=>r.url.startsWith('/backend/api/')));
assert.ok(requests.filter(r=>r.method==='POST').every(r=>JSON.parse(r.body).action==='estop'));
win.dispatchEvent(new win.PageTransitionEvent('pagehide'));dom.window.close();
''')
