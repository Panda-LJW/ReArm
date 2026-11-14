"""T2 数据契约：虚拟时间驱动 JS，无网络、浏览器、真实硬件。"""
from pathlib import Path
import re

import pytest

from tests.test_trainer_views import node, jsdom_script
from tests.test_console_shell import DOM

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / 'rearm/ui/static/modules'
BASE = r'''
import assert from 'node:assert/strict';
import {createMockConsole} from './datasource/mock-console.js';
import {initialState,reduce,createStore} from './console/state/store.js';
import {productionSummary,statusWord,startReason,trainReason} from './console/state/selectors.js';
import {ARM_PARAMS} from './arm/arm-params.js';
import {checkJoints,endPoses} from './arm/fk.js';
import {POSES,keyPoses,tcpPosition,OPEN_MM} from './datasource/fixtures/poses.js';
import {PARTS,THRESHOLD_MM} from './datasource/fixtures/parts.js';
import {RECIPES,FIXTURE} from './datasource/fixtures/recipes.js';
import {WORKSPACE} from './datasource/fixtures/workspace.js';
globalThis.fetch=()=>{throw Error('禁止联网');};
globalThis.WebSocket=class {constructor(){throw Error('禁止联网');}};
function setup(seed=1) {
  const messages=[],store=createStore();
  const host=createMockConsole({now:()=>1794614400000,setTimer:()=>0,clearTimer:()=>{},seed});
  host.subscribe(m=>{messages.push(m);store.dispatch(m);});host.start();
  return {host,messages,store};
}
const {host,messages,store}=setup();
const last=type=>messages.filter(m=>m.type===type).at(-1);
const run=async()=>{assert.equal((await host.send('run_start',{recipe_id:'plate-tube'})).ok,true);host.advance(38000);};
'''


def test_fixtures_have_complete_docs_consistent_force_and_training():
    node(BASE + r'''
assert.deepEqual(PARTS.map(p=>p.name),['薄片','空心圆柱','短轴套','方垫块']);
assert.deepEqual(PARTS.map(p=>p.force_n),[11.6,12.3,12.1,11.8]);
for(const doc of [...PARTS,...RECIPES]) {
  const training=doc.training, rounds=training.rounds;
  assert.ok(rounds.length>=8 && rounds.length<=12);
  assert.ok(rounds.at(-1).deviation_mm<training.threshold_mm);
  assert.ok(rounds.every((r,i)=>!i || r.deviation_mm<rounds[i-1].deviation_mm));
  assert.equal(training.images,rounds.at(-1).images);
  assert.equal(training.elapsed_ms,rounds.at(-1).elapsed_ms);
  assert.equal(training.grasp_records.length,rounds.length);
  assert.ok(doc.collected_at>0 && doc.version===1);
  assert.ok(!('angle_deg' in doc) && !('trajectory' in doc) && !('video_url' in doc));
}
for(const p of PARTS) {
  const b=p.force_basis, force=b.estimated_mass_kg*b.gravity_m_s2*b.safety_factor/b.friction_coefficient/b.fingers;
  assert.ok(Math.abs(force-p.force_n)<1e-10);assert.ok(b.material);
  assert.equal(p.opening,'full');assert.ok(p.outline.length>=4);assert.equal(p.size_mm.length,3);
}
assert.deepEqual(RECIPES[0].part_ids,['plate','tube']);
assert.deepEqual(RECIPES[0].steps.map(s=>s.target_id),['post','post']);
assert.ok(RECIPES[0].training.success_rate>0.8);
''')


def test_key_poses_within_limits_workspace_uses_fk_and_camera_points_down():
    node(BASE + r'''
for(const q of keyPoses()) assert.equal(checkJoints(ARM_PARAMS,q).ok,true,JSON.stringify(q));
for(const p of PARTS) {
  assert.deepEqual(WORKSPACE.props.find(x=>x.id===p.id).pose,tcpPosition(POSES.parts[p.id].contact));
  assert.ok(tcpPosition(POSES.parts[p.id].above)[2]>tcpPosition(POSES.parts[p.id].contact)[2]);
}
assert.deepEqual(WORKSPACE.props.find(x=>x.id==='post').pose,tcpPosition(POSES.post.contact));
const camera=endPoses(ARM_PARAMS,POSES.observe).camera;
assert.ok(Math.abs(camera[0])<0.0002 && Math.abs(camera[4])<0.0002 && camera[8]<-0.99999,
  JSON.stringify([camera[0],camera[4],camera[8]]));
assert.ok(camera[11]>WORKSPACE.table_z_m);
for(let axis=0;axis<2;axis++) {
  const values=WORKSPACE.props.map(p=>p.pose[axis]);
  assert.ok(camera[axis*4+3]>=Math.min(...values)-0.08 && camera[axis*4+3]<=Math.max(...values)+0.08,
    JSON.stringify({axis,camera:[camera[3],camera[7],camera[11]],positions:WORKSPACE.props.map(p=>p.pose)}));
}
''')


def test_full_production_phase_order_duration_checks_recognition_and_result():
    node(BASE + r'''
const started=last('run_state').t;
await run();
const phases=messages.filter(m=>m.type==='run_state').map(m=>m.phase);
assert.deepEqual(phases,['idle','selfcheck','to_observe','recognize','pick','place','pick','place','inspect','done','to_fold','idle']);
assert.equal(last('run_state').t-started,38000);
assert.deepEqual(messages.filter(m=>m.type==='selfcheck_item').map(m=>m.item),['comm','j1','j2','j3','j4','j5','j6','gripper','depth_camera']);
assert.ok(messages.filter(m=>m.type==='selfcheck_item').every(m=>m.ok));
assert.deepEqual(last('recognition').targets.map(t=>t.id),['disc-fixture','post','plate','tube']);
for(const target of last('recognition').targets) {
  const [x,y,w,h]=target.box_px;assert.ok(x>=0 && y>=0 && x+w<=640 && y+h<=480);
  assert.ok(target.confidence>0 && target.confidence<=1);
}
assert.equal(last('run_done').ok,true);assert.equal(last('run_done').deviation_mm,0.4);
assert.equal(last('run_done').duration_ms,32500);
assert.equal(productionSummary(store.getState()).sets,1);
assert.equal(productionSummary(store.getState()).passRate,1);
assert.equal(store.getState().inspection.ok,true);
assert.deepEqual(last('joint_state').q,POSES.folded);
const steps=messages.filter(m=>m.type==='step_state');
assert.equal(steps.length,8);assert.deepEqual(steps.filter(m=>m.status==='done').map(m=>m.action),['pick','place','pick','place']);
assert.ok(steps.filter(m=>m.action==='place').every(m=>!('angle_deg' in m)));
assert.ok(!JSON.stringify(store.getState().runs).includes('angle_deg'));
assert.ok(host.commands.every(c=>!c.cmd.startsWith('laser_')));
''')


@pytest.mark.parametrize('elapsed', [200, 3200, 7200, 12500, 17500, 28000, 31500, 33500])
def test_estop_freezes_current_pose_and_cancels_remaining_events(elapsed):
    node(BASE + f'const elapsed={elapsed};' + r'''
await host.send('run_start',{recipe_id:'plate-tube'});host.advance(elapsed);
await host.send('estop');const frozen=last('joint_state'),from=messages.length;
host.advance(50000);
assert.equal(store.getState().phase,'estop');
assert.deepEqual(last('joint_state').q,frozen.q);assert.equal(last('joint_state').gripper_mm,frozen.gripper_mm);
assert.ok(messages.slice(from).every(m=>m.type==='joint_state' && m.mode==='estop'));
assert.deepEqual(last('joint_state').dq,[0,0,0,0,0,0]);
for(const cmd of ['estop','run_start','library_get','part_get','recipe_get','part_capture','train_start'])
  assert.equal((await host.send(cmd)).code,'estop');
await host.send('reset_estop');assert.equal(store.getState().phase,'idle');
assert.deepEqual(last('joint_state').q,frozen.q);
host.advance(50000);assert.equal(store.getState().phase,'idle');
assert.equal((await host.send('run_start',{recipe_id:'plate-tube'})).ok,true);
''')


def test_telemetry_20hz_smooth_motion_and_gripper_timing():
    node(BASE + r'''
await host.send('run_start',{recipe_id:'plate-tube'});host.advance(38000);
const frames=messages.filter(m=>m.type==='joint_state');assert.equal(frames.length,761);
for(let i=0;i<frames.length;i++) {
  const f=frames[i];assert.equal(checkJoints(ARM_PARAMS,f.q).ok,true);
  assert.ok(f.gripper_mm>=0 && f.gripper_mm<=OPEN_MM);
  if(i) {assert.equal(f.t-frames[i-1].t,50);assert.ok(Math.max(...f.q.map((v,j)=>Math.abs(v-frames[i-1].q[j])))<0.4);}
}
const at=ms=>frames.find(f=>f.t===frames[0].t+ms);
assert.equal(at(13000).gripper_mm,OPEN_MM);assert.equal(at(14000).gripper_mm,36);
assert.equal(at(18000).gripper_mm,36);assert.equal(at(19000).gripper_mm,OPEN_MM);
''')


def test_capture_train_completes_once_adds_document_and_preserves_command_array():
    node(BASE + r'''
const commands=host.commands;let pushes=0;const push=commands.push;
commands.push=function(...args){pushes+=args.length;return Reflect.apply(push,this,args);};
await host.send('part_capture');host.advance(1499);assert.equal(last('part_candidate'),undefined);
host.advance(1);const candidate=last('part_candidate');
await host.send('train_start',{target:'part',draft:{...candidate,angle_deg:30,trajectory:[1,2]}});
assert.equal(statusWord(store.getState()),'训练中');assert.ok(startReason(store.getState()));
assert.equal((await host.send('run_start',{recipe_id:'plate-tube'})).code,'busy');
host.advance(9599);assert.equal(store.getState().library.parts.length,4);host.advance(1);
assert.equal(store.getState().library.parts.length,5);assert.equal(store.getState().trains.length,1);
assert.equal(store.getState().trains[0].rounds.length,8);assert.equal(statusWord(store.getState()),'待命');
const id=last('train_done').doc_id;await host.send('part_get',{id});const doc=last('part_doc');
assert.equal(doc.name,candidate.name);assert.equal(doc.version,1);assert.equal(doc.training.rounds.length,8);
assert.ok(!('angle_deg' in doc) && !('trajectory' in doc));
host.advance(20000);assert.equal(messages.filter(m=>m.type==='train_done').length,1);
assert.equal(host.commands,commands);assert.equal(pushes,commands.length);
assert.equal(startReason(store.getState()),'');
''')


def test_recipe_training_and_retraining_update_versions_without_duplicates():
    node(BASE + r'''
const draft={name:'新配方',code:'R002',fixture_id:FIXTURE.id,steps:RECIPES[0].steps};
assert.equal((await host.send('train_start',{target:'recipe',draft})).ok,true);host.advance(9600);
assert.equal(store.getState().library.recipes.length,2);
const recipeId=last('train_done').doc_id;await host.send('recipe_get',{id:recipeId});
assert.deepEqual(last('recipe_doc').part_ids,['plate','tube']);
await host.send('train_start',{target:'recipe',draft:{id:recipeId}});host.advance(9600);
assert.equal(store.getState().library.recipes.length,2);assert.equal(last('recipe_doc').version,2);
await host.send('train_start',{target:'part',draft:{id:'plate'}});host.advance(9600);
assert.equal(store.getState().library.parts.length,4);assert.equal(last('part_doc').version,2);
assert.equal(store.getState().trains.length,3);
assert.equal((await host.send('train_start',{target:'recipe',draft})).code,'invalid_args');
''')


def test_reset_clears_session_counts_records_and_training_but_keeps_library_and_audit():
    node(BASE + r'''
await run();await host.send('train_start',{target:'part',draft:{id:'plate'}});host.advance(9600);
assert.equal(store.getState().trains.length,1);
await host.send('estop');const before=host.commands.length,commands=host.commands;
await host.send('reset_demo');
const state=store.getState();assert.equal(state.phase,'idle');assert.equal(state.runs.length,0);assert.equal(state.trains.length,0);
assert.deepEqual(productionSummary(state),{sets:0,passed:0,passRate:null,deviations:[]});
assert.equal(state.library.parts.find(p=>p.id==='plate').version,2);
assert.deepEqual(last('joint_state').q,POSES.folded);assert.equal(last('joint_state').gripper_mm,OPEN_MM);
assert.equal(host.commands,commands);assert.equal(commands.length,before+1);
await run();assert.equal(productionSummary(store.getState()).sets,1);assert.equal(last('run_done').deviation_mm,0.4);
''')


def test_estop_or_reset_cancels_capture_training_and_reentrant_completion():
    node(BASE + r'''
await host.send('part_capture');host.advance(1000);await host.send('estop');host.advance(10000);
assert.equal(last('part_candidate'),undefined);await host.send('reset_estop');
await host.send('train_start',{target:'part',draft:{id:'plate'}});host.advance(2400);
await host.send('reset_demo');host.advance(20000);assert.equal(last('train_done'),undefined);
let stopped=false;host.subscribe(m=>{if(m.type==='train_progress' && m.round===8){stopped=true;host.send('estop');}});
await host.send('train_start',{target:'part',draft:{id:'plate'}});host.advance(20000);
assert.equal(stopped,true);assert.equal(last('train_done'),undefined);
assert.equal(store.getState().library.parts.find(p=>p.id==='plate').version,1);
assert.equal(store.getState().phase,'estop');
''')


def test_seeded_results_repeat_with_roughly_ninety_percent_first_pass():
    node(BASE + r'''
async function sample(seed) {
  const {host,messages}=setup(seed);const rows=[];
  for(let i=0;i<100;i++) {await host.send('run_start',{recipe_id:'plate-tube'});host.advance(38000);
    rows.push(messages.findLast(m=>m.type==='run_done'));messages.length=0;}
  return rows.map(({ok,deviation_mm})=>({ok,deviation_mm}));
}
const rows=await sample(7);assert.deepEqual(rows,await sample(7));
assert.equal(rows[0].ok,true);assert.ok(rows[0].deviation_mm>=0.3 && rows[0].deviation_mm<=0.6);
const passed=rows.filter(r=>r.ok).length;assert.ok(passed>=80 && passed<=98,passed);
assert.ok(rows.filter(r=>!r.ok).every(r=>r.deviation_mm>=1.1 && r.deviation_mm<=1.9));
''')


def test_lifecycle_virtual_real_timer_equivalence_and_bad_commands():
    node(BASE + r'''
let now=1794614400000,callback,starts=0,cleared=[];
const real=createMockConsole({now:()=>now,setTimer:(fn,ms)=>{assert.equal(ms,50);callback=fn;starts++;return 0;},clearTimer:id=>cleared.push(id)});
assert.equal((await real.send('run_start')).code,'offline');real.start();real.start();assert.equal(starts,1);
const seen=[];real.subscribe(m=>seen.push(m));await real.send('run_start',{recipe_id:'plate-tube'});
now+=38000;callback();assert.equal(seen.findLast(m=>m.type==='run_state').phase,'idle');
assert.equal((await real.send('part_get',{id:'missing'})).code,'not_found');
assert.equal((await real.send('train_start',{target:'part',draft:{}})).code,'invalid_args');
assert.equal((await real.send('laser_on')).code,'unknown_command');
assert.equal(real.commands.at(-1).cmd,'laser_on'); // 拒绝也保留原始请求，不能为审计删掉它。
real.stop();real.stop();assert.deepEqual(cleared,[0]);const count=seen.length;callback();real.advance(10000);assert.equal(seen.length,count);
real.start();assert.equal(starts,2);await real.send('estop');real.stop();real.start();
assert.equal((await real.send('run_start',{recipe_id:'plate-tube'})).code,'estop');real.stop();
await host.send('train_start',{target:'part',draft:{id:'plate'}});assert.ok(store.getState().training);
host.stop();assert.equal(store.getState().training,null);host.start();assert.equal(statusWord(store.getState()),'待命');
assert.throws(()=>host.advance(-1),RangeError);assert.throws(()=>host.advance(NaN),RangeError);
''')


def test_reducer_is_pure_deduplicates_results_and_ignores_pre_reset_messages():
    node(BASE + r'''
const deepFreeze=x=>{if(x&&typeof x==='object'){Object.freeze(x);Object.values(x).forEach(deepFreeze);}return x;};
const original=deepFreeze(initialState()),before=JSON.stringify(original);
const result=deepFreeze({v:1,type:'run_done',seq:1,t:100,run_id:'r1',recipe_id:'plate-tube',ok:true,deviation_mm:0.4,duration_ms:32500});
let s=reduce(original,result);assert.equal(JSON.stringify(original),before);assert.equal(s.runs.length,1);
assert.equal(reduce(s,result),s);assert.equal(reduce(s,{...result,t:99,seq:2}),s);
s=reduce(s,{...result,run_id:'r2',ok:false,deviation_mm:1.4,t:200,seq:2});
assert.equal(productionSummary(s).passRate,0.5);
const snapshot=JSON.stringify(s);assert.deepEqual(reduce(s,{...result,type:'unknown'}),s);assert.equal(JSON.stringify(s),snapshot);
s=reduce(s,{v:1,type:'demo_reset',seq:3,t:300});assert.equal(s.runs.length,0);
assert.equal(reduce(s,{...result,run_id:'late'}),s);assert.equal(reduce(s,{...result,v:2}),s);
assert.equal(reduce(s,null),s);
''')


def test_main_wires_live_command_array_and_keeps_estop_and_navigation_when_page_fails():
    jsdom_script(DOM + r'''
await import('./console/main.js');tick(32);
const commands=win.__rearmMock.commands;assert.equal(Array.isArray(commands),true);
const stop=doc.querySelector('[data-action="estop"]');assert.equal(stop.getAttribute('aria-disabled'),'false');
stop.click();tick(32);assert.equal(doc.querySelector('[data-status]').textContent,'急停');
assert.equal(commands.at(-1).cmd,'estop');assert.equal(win.__rearmMock.commands,commands);
assert.equal(doc.querySelectorAll('[data-nav]').length,4);
assert.ok(commands.every(c=>!c.cmd.startsWith('laser_')));
win.dispatchEvent(new win.PageTransitionEvent('pagehide'));dom.window.close();
''')


def test_new_modules_have_no_transports_or_legacy_training_dependency():
    files = [MODULES / 'datasource/mock-console.js',
             *(MODULES / 'datasource/mock-console').glob('*.js'),
             *(MODULES / 'datasource/fixtures').glob('*.js')]
    for path in files:
        source = path.read_text()
        assert not re.search(r'\bfetch\s*\(|\bWebSocket\b|/api/|trainer/|laser_', source), path
        assert len(source.splitlines()) <= 200, path
    for path in (MODULES / 'console/state').glob('*.js'):
        assert not re.search(r'\bDate\b|performance|\bdocument\b|\bwindow\b', path.read_text()), path


def test_protocol_appendix_covers_actual_emitted_types_and_fields():
    script = BASE + r'''
await run();await host.send('part_capture');host.advance(1500);
await host.send('train_start',{target:'part',draft:last('part_candidate')});host.advance(9600);
await host.send('train_start',{target:'recipe',draft:{id:'plate-tube'}});host.advance(9600);
await host.send('reset_demo');
const keys={};for(const m of messages){keys[m.type]??=new Set();Object.keys(m).forEach(k=>keys[m.type].add(k));}
console.log(JSON.stringify(Object.fromEntries(Object.entries(keys).map(([k,v])=>[k,[...v]]))));
'''
    import json
    emitted = json.loads(node(script))
    doc = (ROOT / 'docs/接口文档.md').read_text().split('## 附录 C：控制台生产与零件库扩展', 1)[1]
    for kind, fields in emitted.items():
        assert f'`{kind}`' in doc, kind
        for field in fields:
            assert f'`{field}`' in doc, (kind, field)
