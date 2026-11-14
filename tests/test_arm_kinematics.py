"""六轴参数、URDF FK、原始轨迹与 JointFrame 契约；不连接硬件。"""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

MODULES = Path(__file__).resolve().parents[1] / 'rearm/ui/static/modules'
NODE = shutil.which('node')
PRELUDE = '''
import { ARM_PARAMS as P } from './arm/arm-params.js';
import { ARM_CONFIG as C } from './twin/arm-config.js';
import { checkJoints, forwardUrdf, endPoses, laserRay } from './arm/fk.js';
import { identity, multiply, fromOrigin, fromAxisAngle, forward, position } from './twin/kinematics.js';
const middle = [0, -1.57, -1.57, 0, 0, 0];
const legacy = q => Object.fromEntries(P.joints.map((j, i) => [j.id, q[i]]));
'''


def node(script):
    if NODE is None:
        pytest.skip('node not installed')
    result = subprocess.run([NODE, '--input-type=module', '-e', PRELUDE + script],
                            cwd=MODULES, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# 调研 4.1/4.2：独立于参数文件保存的官方 SDK 对照值，单位 mm。
SAMPLES = [
    ([0, 0, 0, 0, 0, 0], [260.306, 0.000, 191.701]),
    ([0, -1.57, -1.57, 0, 0, 0], [524.096, 0.001, 455.701]),
    ([2.79, -3.13, -0.01, 1.56, 1.56, 3.13], [23.092, 186.835, 164.363]),
    ([-2.79, -0.01, -3.13, -1.86, -1.56, -3.13], [503.188, -10.719, 15.999]),
    ([0.7, -2.4, -2.5, 1.2, -0.8, 0.9], [329.708, 449.792, 211.675]),
    ([-1.2, -0.4, -0.2, -0.9, 0.6, -1.1], [-23.154, -226.438, 393.781]),
    ([0.3, -1.1, -0.7, 0.4, -1.2, 1.5], [182.386, 235.370, 225.154]),
]


@pytest.mark.parametrize('q,expected', SAMPLES)
def test_fk_matches_report_and_legacy_in_range(q, expected):
    out = node(f'''
const q = {json.dumps(q)};
const actual = forwardUrdf(P, q), old = forward(C, legacy(q));
console.log(JSON.stringify({{
  ok: checkJoints(P, q).ok, mm: position(actual.end_link).map(v => v * 1000),
  same: JSON.stringify(actual.frames) === JSON.stringify(old.frames)
    && JSON.stringify(actual.end_link) === JSON.stringify(old.end_link),
  alias: old.tool === old.end_link,
}}));
''')
    assert out['ok'] and out['same'] and out['alias']
    assert out['mm'] == pytest.approx(expected, abs=0.0006)
    assert sum((a - b) ** 2 for a, b in zip(out['mm'], expected)) ** 0.5 < 0.001


@pytest.mark.parametrize('expression,joint,kind', [
    ('[0,-1,-1,0,0]', 'joint6', 'missing'),
    ('[0,-1,NaN,0,0,0]', 'joint3', 'nan'),
    ('[0,-1,0.1,0,0,0]', 'joint3', 'out_of_range'),
    ('[0,-1,null,0,0,0]', 'joint3', 'missing'),
    ('[0,-1,"0",0,0,0]', 'joint3', 'nan'),
])
def test_check_joints_rejects_without_mutating(expression, joint, kind):
    out = node(f'''
const q = {expression}, before = q.slice(), result = checkJoints(P, q);
console.log(JSON.stringify({{ ...result, unchanged: q.every((v, i) => Object.is(v, before[i])) }}));
''')
    assert not out['ok'] and out['unchanged']
    assert out['issues'][0]['joint'] == joint
    assert out['issues'][0]['kind'] == kind


def test_fk_does_not_clamp_or_fill_missing_angles():
    out = node('''
const q = [0,-1,0.5,0,0,0];
// 手工连乘 URDF 固定变换和原始旋转，J3 故意超过上限 0。
let manual = identity();
P.joints.forEach((j, i) => { manual = multiply(multiply(manual, fromOrigin(j.xyz, j.rpy)), fromAxisAngle(j.axis, q[i])); });
manual = multiply(manual, fromOrigin(P.end_link.xyz, P.end_link.rpy));
const actual = forwardUrdf(P, q).end_link, clamped = forward(C, legacy(q)).end_link;
const malformed = [[], middle.slice(0,5), [...middle, 0], new Array(6), [0,-1,NaN,0,0,0], [0,-1,null,0,0,0]];
console.log(JSON.stringify({actual, manual, clamped,
  rejected: malformed.map(q => { try { forwardUrdf(P,q); return false; } catch (e) { return e instanceof TypeError; } }),
  checked: malformed.map(q => checkJoints(P,q).ok),
  bounds: [P.joints.map(j => j.limit[0]), P.joints.map(j => j.limit[1])].map(q => checkJoints(P,q).ok),
}));
''')
    assert out['actual'] == pytest.approx(out['manual'], abs=1e-14)
    assert max(abs(a - b) for a, b in zip(out['actual'], out['clamped'])) > 0.1
    assert all(out['rejected']) and not any(out['checked'])
    assert out['bounds'] == [True, True]


def test_end_poses_are_right_multiplied_and_camera_height_is_local_positive_z():
    out = node('''
const rows = [middle, [0.3,-1.1,-0.7,0.4,-1.2,1.5]].map(q => {
 const p = endPoses(P,q), ray = laserRay(P,q);
 return { p, expected: Object.fromEntries(['tcp','camera','laser'].map(k => [k, multiply(p.end_link,P['T_end_'+k])])), ray };
});
const m = rows[0].p.end_link;
const center = multiply(m, fromOrigin([P.T_end_camera[3],0,0],[0,0,0]));
console.log(JSON.stringify({rows, center, tcp: P.T_end_tcp, camera: P.T_end_camera, laser: P.T_end_laser,
 up: [m[2],m[6],m[10]], cameraSpec: P.camera, gripper: P.gripper}));
''')
    for row in out['rows']:
        for name in ['tcp', 'camera', 'laser']:
            assert row['p'][name] == pytest.approx(row['expected'][name], abs=1e-14)
        m = row['p']['end_link']
        assert [row['p']['camera'][i] for i in [0, 4, 8]] == pytest.approx([m[i] for i in [0, 4, 8]])
        assert row['ray']['origin'] == [row['p']['laser'][i] for i in [3, 7, 11]]
        assert row['ray']['direction'] == pytest.approx([m[i] for i in [0, 4, 8]])
    p = out['rows'][0]['p']
    assert (p['camera'][11] - out['center'][11]) * 1000 == pytest.approx(40, abs=1e-6)
    assert (p['camera'][11] - p['laser'][11]) * 1000 == pytest.approx(20, abs=1e-6)
    assert out['up'] == pytest.approx([-0.000007346410191, 0.000099999999832, 0.999999994973], abs=1e-12)
    assert out['tcp'] == [1, 0, 0, 0.0005, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    assert [out['camera'][i] for i in [3, 7, 11]] == [-0.0695, 0, 0.04]
    assert [out['laser'][i] for i in [3, 7, 11]] == [-0.0695, 0, 0.02]
    assert out['gripper']['fingerTravel'] == [0, 0.0285] and out['gripper']['openingMm'] == [0, 57]
    assert out['gripper']['fingerLength'] == 0.0655
    assert [f['axis'] for f in out['gripper']['fingers']] == [[0, 1, 0], [0, -1, 0]]
    assert out['cameraSpec'] == {'size': [0.025, 0.090, 0.025], 'horizontalFovDeg': 87, 'verticalFovDeg': 58}


def test_path_keeps_raw_samples_and_breaks_at_invalid_frames_and_time_gaps():
    out = node('''
import { buildPath } from './arm/trajectory.js';
const t = 1700000000000, qs = [middle,[0.1,-1.5,-1.6,0.1,0,0],[0.2,-1.4,-1.7,0.2,0,0]];
const samples = qs.map((q,i) => ({t:t+i*100,q})), before = JSON.stringify(samples);
const broken = [
 {q:[0,-1]}, {q:[0,-1,NaN,0,0,0]}, {q:[0,-1,0.1,0,0,0]},
 {valid:[true,true,false,true,true,true]}, {valid:[true]},
].map(change => buildPath(P,[samples[0],{...samples[1],...change},samples[2]]));
console.log(JSON.stringify({ continuous:buildPath(P,samples), broken,
 gap:buildPath(P,[samples[0],{...samples[1],t:t+501},{...samples[2],t:t+502}]),
 exactGap:buildPath(P,[samples[0],{...samples[1],t:t+500}]),
 customGap:buildPath(P,samples,{maxGapMs:99}),
 camera:buildPath(P,samples,{point:'camera'}),
 expected:qs.map(q => position(endPoses(P,q).tcp)), cameraExpected:qs.map(q => position(endPoses(P,q).camera)),
 unchanged:JSON.stringify(samples)===before, empty:buildPath(P,[]),
}));
''')
    assert out['unchanged'] and out['empty'] == {'segments': [], 'dropped': []}
    assert len(out['continuous']['segments']) == 1 and not out['continuous']['dropped']
    assert [p['p'] for p in out['continuous']['segments'][0]] == out['expected']
    assert [p['t'] for p in out['continuous']['segments'][0]] == [1700000000000, 1700000000100, 1700000000200]
    assert [p['p'] for p in out['camera']['segments'][0]] == out['cameraExpected']
    for broken in out['broken']:
        assert [len(s) for s in broken['segments']] == [1, 1]
        assert broken['dropped'][0]['t'] == 1700000000100 and broken['dropped'][0]['reason']
    assert [len(s) for s in out['gap']['segments']] == [1, 2] and not out['gap']['dropped']
    assert [len(s) for s in out['exactGap']['segments']] == [2]
    assert [len(s) for s in out['customGap']['segments']] == [1, 1, 1]


def test_pedestal_is_display_only_and_compatibility_config_shares_parameters():
    out = node('''
const calculate = () => ({fk:forwardUrdf(P,middle), ends:endPoses(P,middle), old:forward(C,legacy(middle))});
const before = calculate(); C.scene.pedestalHeight = 123;
const same = JSON.stringify(before)===JSON.stringify(calculate());
const shared = C.joints === P.joints && C.scene === P.scene && C.shape === P.shape
 && C.panelMapping === P.legacyPanelMapping && C.restPose === P.legacyRestPose;
P.joints[0].limit[0] = -2.7;
console.log(JSON.stringify({same,shared, limit:C.joints[0].limit[0], travel:C.tool.fingerTravel,
 toolOrigin:C.tool.xyz===P.end_link.xyz, labels:P.joints.map(j=>j.label)}));
''')
    assert out['same'] and out['shared'] and out['toolOrigin']
    assert out['limit'] == -2.7 and out['travel'] == 0.0285
    assert out['labels'] == ['J1 底座', 'J2 大臂', 'J3 小臂', 'J4 腕俯仰', 'J5 腕偏摆', 'J6 腕旋转']


def test_make_frame_new_fields_are_independent_and_legacy_values_unchanged():
    out = node('''
import { makeFrame } from './datasource/frame.js';
const q = middle.slice(), valid = [true,true,false,true,true,true];
const frame = makeFrame({q_rad:q,valid,gripper_mm:57,timestamp:123.25,mode:'live',angles_deg:[1,'2',-3]});
q[0]=999; valid[2]=true;
const bad = makeFrame({q_rad:[0,-1,NaN,0,0,0]});
console.log(JSON.stringify({frame, empty:makeFrame({timestamp:1}),
 short:makeFrame({q_rad:[0,0,0]}).q_rad, long:makeFrame({q_rad:[...middle,0]}).q_rad,
 badRejected: !checkJoints(P,bad.q_rad).ok, malformedValid:makeFrame({q_rad:middle,valid:[true]}).valid,
 badGripper:makeFrame({gripper_mm:'10'}).gripper_mm,
}));
''')
    f = out['frame']
    assert f['q_rad'] == [0, -1.57, -1.57, 0, 0, 0]
    assert f['valid'] == [True, True, False, True, True, True]
    assert f['gripper_mm'] == 57 and f['timestamp'] == 123.25
    assert f['angles_deg'] == [1, 2, -3] and f['mode'] == 'live' and f['online'] is True and f['laser'] is None
    assert out['empty']['q_rad'] is None and out['empty']['valid'] == [True] * 6 and out['empty']['gripper_mm'] is None
    assert out['short'] is None and out['long'] is None and out['badRejected']
    assert out['malformedValid'] == [False] * 6 and out['badGripper'] is None


def test_arm_modules_are_pure_and_have_no_rendering_dependencies():
    for path in (MODULES / 'arm').glob('*.js'):
        assert not re.search(r'\b(document|window|three)\b', path.read_text(), re.I), path


# 只替代 DOM/画布宿主，不替代孪生、FK、回退渲染或 Three 的矩阵/几何代码。
DOM_HOST = '''
class Element {
 constructor(tag='div') {
  this.tag=tag; this.children=[]; this.style={}; this.dataset={}; this.attrs={};
  this.clientWidth=800; this.clientHeight=560; this.offsetWidth=108; this.offsetHeight=24;
  this.classList={add(){},remove(){}}; this.textContent=''; this.hidden=false;
 }
 set innerHTML(value) {
  this.html=value;
  if(value.includes('twin-stage')) this.slots=Object.fromEntries(['stage','status','labels','note'].map(s=>['.twin-'+s,new Element()]));
 }
 querySelector(s) {return this.slots[s];}
 appendChild(e) {this.children.push(e); return e;}
 append(...children) {this.children.push(...children);}
 replaceChildren(...children) {this.children=children;}
 setAttribute(k,v) {this.attrs[k]=v;}
 addEventListener() {} remove() {} setPointerCapture() {}
 getContext() {return new Proxy({}, {get:(target,key)=>target[key] || (()=>{}), set:(t,k,v)=>(t[k]=v,true)});}
}
globalThis.document={createElement:tag=>new Element(tag)};
globalThis.devicePixelRatio=1;
globalThis.getComputedStyle=()=>({getPropertyValue:()=>''});
globalThis.ResizeObserver=class {observe(){} disconnect(){}};
globalThis.matchMedia=()=>({matches:false});
let rafId=0; const queued=new Map();
globalThis.requestAnimationFrame=cb=>{queued.set(++rafId,cb);return rafId;};
globalThis.cancelAnimationFrame=id=>queued.delete(id);
function tick() {const jobs=[...queued.values()];queued.clear();jobs.forEach(f=>f());}
function settle() {let n=0;while(queued.size && n++<100) tick();if(queued.size) throw Error('animation did not settle');}
'''


def test_twin_six_axis_smoothing_invalid_hold_labels_and_legacy_reentry():
    out = node(DOM_HOST + '''
import {createTwin} from './twin/twin.js';
const container=new Element(), twin=await createTwin(container,{forceFallback:true,skin:false});
twin.update({q_rad:middle,angles_deg:[50,60,-80],mode:'live',online:true}); settle();
const first=twin.state(), beforeLabels=container.slots['.twin-labels'].children.map(e=>e.textContent);
const target=[0.2,-1.2,-1.3,0.4,0.5,0.6], source=target.slice();
twin.update({q_rad:target}); tick(); const moving=twin.state();
const bad=target.slice(); bad[2]=0.1;
twin.update({q_rad:bad,angles_deg:[20,30,-40]}); settle(); const held=twin.state(), error=container.slots['.twin-note'].textContent;
twin.update({q_rad:target,valid:[true,true,true,false,true,true]}); settle();
const invalid=container.slots['.twin-note'].textContent;
twin.update({q_rad:target}); settle(); const final=twin.state(), cleared=container.slots['.twin-note'].textContent;
const labels=container.slots['.twin-labels'].children.map(e=>({text:e.textContent,side:e.dataset.side,x:parseFloat(e.style.left),y:parseFloat(e.style.top),w:e.offsetWidth,h:e.offsetHeight}));
const copy=twin.state();copy.q_rad[0]=999;
const notAliased=twin.state().q_rad[0]!==999;
twin.update({angles_deg:[20,60,-80]});settle();const old=twin.state(), oldLabels=container.slots['.twin-labels'].children.map(e=>e.textContent);
twin.dispose();
// 首个动画帧前发生有效→无效也不能让六轴渲染拿到旧三轴数组。
const early=await createTwin(new Element(),{forceFallback:true,skin:false});
early.update({q_rad:middle});early.update({q_rad:bad});settle();const earlyState=early.state();early.dispose();
console.log(JSON.stringify({first,beforeLabels,moving,held,error,invalid,final,cleared,labels,notAliased,old,oldLabels,earlyState,unmodified:JSON.stringify(target)===JSON.stringify(source)}));
''')
    assert out['first']['axes'] == 6 and out['first']['q_rad'] == [0, -1.57, -1.57, 0, 0, 0]
    assert len(out['beforeLabels']) == 6
    target = [0.2, -1.2, -1.3, 0.4, 0.5, 0.6]
    for a, b, v in zip(out['first']['q_rad'], target, out['moving']['q_rad']):
        assert min(a, b) < v < max(a, b)
    assert out['held']['q_rad'] == out['moving']['q_rad'] and not out['held']['dirty']
    assert out['error'] == '关节数据无效：J3 越界' and out['invalid'] == '关节数据无效：J4 无效'
    assert out['final']['q_rad'] == target and out['cleared'] == '' and out['unmodified'] and out['notAliased']
    assert out['labels'][3]['text'] == 'J4 +22.9°' and out['labels'][0]['side'] == 'left'
    for i, a in enumerate(out['labels']):
        for b in out['labels'][i + 1:]:
            assert a['x'] + a['w'] <= b['x'] or b['x'] + b['w'] <= a['x'] or a['y'] + a['h'] <= b['y'] or b['y'] + b['h'] <= a['y']
    assert out['old']['axes'] == 3 and out['old']['shown'] == [20, 60, -80]
    assert out['oldLabels'] == ['J1 +20.0°', 'J2 +60.0°', 'J3 −80.0°']
    assert len(out['earlyState']['q_rad']) == 6


def test_scene_uses_supplied_matrices_and_moves_both_official_fingers():
    out = node(DOM_HOST + '''
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const base=pathToFileURL(process.cwd()+'/');
// 只替换 WebGLRenderer；使用仓库实际 vendored Three 的 Group、Mesh、Matrix4 等。
let code=await readFile(new URL('./twin/scene.js',base),'utf8');
code=code.replace('import * as THREE from "../../vendor/three.module.min.js";',`
import * as ActualThree from '${new URL('../vendor/three.module.min.js',base)}';
const THREE={...ActualThree,WebGLRenderer:class {
 constructor({canvas}){this.canvas=canvas;} setPixelRatio(){} setSize(){} dispose(){}
 render(scene,camera){scene.updateMatrixWorld();camera.updateMatrixWorld();globalThis.drawnScene=scene;}
}};`);
code=code.replace('"./kinematics.js"',JSON.stringify(new URL('./twin/kinematics.js',base).href));
const {createScene}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
globalThis.fetch=async url=>({
 json:async()=>JSON.parse(await readFile(url,'utf8')),
 arrayBuffer:async()=>{const b=await readFile(url);return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);},
});
const scene=createScene(new Element(),C), q=[0,-1,0.5,0,0,0], pose=forwardUrdf(P,q);
scene.setPoseMatrices(pose,{gripperMm:57});scene.render();
const world=drawnScene.children.find(o=>o.type==='Group');
const links=world.children.filter(o=>o.type==='Group' && !o.matrixAutoUpdate);
const rowMajor=m=>[0,1,2,3].flatMap(r=>[0,1,2,3].map(c=>m.elements[c*4+r]));
const actual=links.map(o=>rowMajor(o.matrix));
await scene.loadSkin(new URL('./twin/meshes/b601.json',base), {gripper:'official'});
const manifest=JSON.parse(await readFile(new URL('./twin/meshes/b601.json',base),'utf8'));
const parts=manifest.parts.filter(p=>p.frame==='tool'), tool=links[6];
const meshParts=tool.children.filter(o=>o.type==='Mesh' && !o.userData.simple);
const openings=[];
const record=()=>parts.flatMap((p,i)=>p.side?[{side:p.side,xyz:meshParts[i].position.toArray()}]:[]);
openings.push(record());
scene.setPoseMatrices(pose,{gripperMm:0});openings.push(record());
scene.setPoseMatrices(pose,{gripperMm:20});openings.push(record());
scene.setPoseMatrices(pose);openings.push(record());
scene.dispose();
console.log(JSON.stringify({actual,expected:[...Object.values(pose.frames),pose.end_link],openings,skinned:scene.isSkinned()}));
''')
    assert out['skinned']
    for actual, expected in zip(out['actual'], out['expected']):
        assert actual == pytest.approx(expected, abs=1e-14)
    for opening, parts in zip([57, 0, 20, 20], out['openings']):
        assert {'left', 'right'} == {p['side'] for p in parts}
        for p in parts:
            sign = 1 if p['side'] == 'left' else -1
            assert p['xyz'] == pytest.approx([0, sign * opening / 2000, 0], abs=1e-14)


def test_manual_demo_builds_six_joint_sliders_and_gripper_from_parameters():
    out = node(DOM_HOST + '''
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const url=pathToFileURL(process.cwd()+'/twin/demo.html');
const html=await readFile(url,'utf8');
let code=html.split('<script type="module">')[1].split('</script>')[0];
code=code.replace(/from "([^"]+)"/g,(_,relative)=>'from '+JSON.stringify(new URL(relative,url).href));
const nodes=Object.fromEntries(['stage','sliders','src'].map(id=>[id,new Element()]));
document.getElementById=id=>nodes[id];
globalThis.window={};globalThis.location={search:'?source=manual&render=2d&skin=simple'};
await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));settle();
const sliders=nodes.sliders.children.map(label=>label.children[0]);
const limits=sliders.map(s=>[s.min,s.max]);
const initial=window.demo.twin.state().q_rad, separate=[];
for(let i=0;i<6;i++) {
 const before=window.demo.twin.state().q_rad;sliders[i].value=Number(sliders[i].value)+0.1;
 nodes.sliders.oninput();settle();const after=window.demo.twin.state().q_rad;
 separate.push(after.every((v,j)=>Math.abs(v-before[j]-(i===j?0.1:0))<1e-14));
}
const edges=[];
for(const bound of ['min','max']) {
 for(let i=0;i<6;i++) sliders[i].value=sliders[i][bound];
 nodes.sliders.oninput();settle();edges.push(checkJoints(P,window.demo.twin.state().q_rad).ok && nodes.stage.slots['.twin-note'].textContent==='');
}
sliders[6].value=57;nodes.sliders.oninput();settle();
const output=nodes.sliders.children[6].children[1].textContent;
window.demo.twin.dispose();
console.log(JSON.stringify({count:sliders.length,limits,expected:[...P.joints.map(j=>j.limit),P.gripper.openingMm],initial,separate,edges,output}));
''')
    assert out['count'] == 7 and out['limits'] == out['expected']
    assert len(out['initial']) == 6 and out['separate'] == [True] * 6
    assert out['edges'] == [True, True] and out['output'] == '57.0 mm'
