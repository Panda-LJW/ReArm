"""T2b：纯视锥数学、真实 Three 场景及孪生叠加生命周期，无浏览器依赖。"""
import json
import math
import re

import pytest

from tests.test_arm_kinematics import DOM_HOST, MODULES, node


# 只替换 GPU 宿主；几何、材质、变换、投影和实际 twin/scene 代码照常执行。
SCENE_HOST = DOM_HOST + r'''
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {frustumCorners} from './arm/fk.js';
const base=pathToFileURL(process.cwd()+'/');
const moduleUrl=code=>'data:text/javascript;base64,'+Buffer.from(code).toString('base64');
const absoluteImports=code=>code.replace(/from "([^"]+)"/g,(_,p)=>'from '+JSON.stringify(new URL(p,new URL('./twin/scene.js',base)).href));
let code=await readFile(new URL('./twin/scene.js',base),'utf8');
code=code.replace('import * as THREE from "../../vendor/three.module.min.js";',`
import * as ActualThree from '${new URL('../vendor/three.module.min.js',base)}';
const THREE={...ActualThree,WebGLRenderer:class {
 constructor({canvas}){this.canvas=canvas;} setPixelRatio(){} setSize(){} dispose(){}
 render(scene,camera){scene.updateMatrixWorld();camera.updateMatrixWorld();globalThis.drawnScene=scene;globalThis.drawnCamera=camera;}
}};`);
const sceneUrl=moduleUrl(absoluteImports(code));
const {createScene}=await import(sceneUrl);
const opts=q=>({axes:6,endPoses:endPoses(P,q),laserRay:laserRay(P,q),frustumCorners:frustumCorners(P,q,0.18)});
const rowMajor=m=>[0,1,2,3].flatMap(r=>[0,1,2,3].map(c=>m.elements[c*4+r]));
const positions=o=>Array.from(o.geometry.attributes.position.array);
const named=name=>drawnScene.getObjectByName(name);
const frame=(s,q=middle,extra={})=>{s.setPoseMatrices(forwardUrdf(P,q),{...opts(q),...extra});s.render();};
const fetchFiles=async url=>({
 json:async()=>JSON.parse(await readFile(url,'utf8')),
 arrayBuffer:async()=>{const b=await readFile(url);return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);},
});
'''


@pytest.mark.parametrize('q', [[0, -1.57, -1.57, 0, 0, 0], [0.3, -1.1, -0.7, 0.4, -1.2, 1.5]])
@pytest.mark.parametrize('fov,length', [([87, 58], 0.18), ([60, 40], 0.31)])
def test_frustum_corners_follow_camera_frame_and_combined_half_fov(q, fov, length):
    out = node(f'''
import {{frustumCorners}} from './arm/fk.js';
const params={{...P,camera:{{...P.camera,horizontalFovDeg:{fov[0]},verticalFovDeg:{fov[1]}}}}};
const q={json.dumps(q)}, before=JSON.stringify(params), pose=endPoses(params,q);
const corners=frustumCorners(params,q,{length}), origin=position(pose.camera), axis=[0,4,8].map(i=>pose.camera[i]);
const directions=corners.map(p=>p.map((v,i)=>v-origin[i]));
console.log(JSON.stringify({{directions,axis,endAxis:[0,4,8].map(i=>pose.end_link[i]),
  angles:directions.map(d=>Math.acos(d.reduce((sum,v,i)=>sum+v*axis[i],0)/Math.hypot(...d))),
  unchanged:JSON.stringify(params)===before}}));
''')
    half_h, half_v = [math.tan(math.radians(v / 2)) for v in fov]
    expected = math.atan(math.hypot(half_h, half_v))
    assert out['unchanged'] and out['angles'] == pytest.approx([expected] * 4, abs=1e-12)
    average = [sum(d[i] for d in out['directions']) / 4 / length for i in range(3)]
    assert average == pytest.approx(out['axis'], abs=1e-12)
    assert average == pytest.approx(out['endAxis'], abs=1e-12)
    assert [math.dist([0, 0, 0], d) for d in out['directions']] == pytest.approx(
        [length * math.sqrt(1 + half_h ** 2 + half_v ** 2)] * 4)


def test_overlay_contract_and_css_defaults_are_wired_to_base_world():
    scene = (MODULES / 'twin/scene.js').read_text()
    twin = (MODULES / 'twin/twin.js').read_text()
    css = (MODULES / 'twin/twin.css').read_text()
    fk = (MODULES / 'arm/fk.js').read_text()
    for group in ('demoPath', 'runPath', 'nodes', 'spots'):
        assert f'world.add({group})' in scene
    overlay_code = scene.split('function drawPath(')[1].split('// 激光束：')[0]
    assert not re.search(r'pedestalHeight|\blift\b', overlay_code)
    assert 'world.position.z = 0' in scene
    assert 'frustumCorners(config, pose, 0.18)' in twin
    for angle in ('horizontalFovDeg', 'verticalFovDeg'):
        assert f'params.camera.{angle}' in fk
    for variable in ('camera', 'frustum', 'demo-path', 'run-path', 'laser'):
        assert re.search(rf'--twin-{variable}:\s*var\(--[\w-]+\)', css)
    for label in ('twin-node-label', 'twin-dev-label'):
        assert label in css and label in twin


def test_sensors_and_laser_follow_six_axes_and_preserve_legacy_floor():
    out = node(SCENE_HOST + '''
const s=createScene(new Element(),C);
frame(s,middle,{laserOn:true});
const initial={camera:rowMajor(named('cameraHead').matrix),laser:rowMajor(named('laserHead').matrix),
  beam:positions(named('laserBeam')),frustum:positions(named('cameraFrustum')),
  body:named('cameraHead').children[0].geometry.parameters};
const measured=[0.63,0.01,0.48];s.setOverlay({spots:{measured}});frame(s,middle,{laserOn:true});
const measuredBeam=positions(named('laserBeam'));
const visible=[];
for(const extra of [{laserOn:false},{laserOn:true,dimmed:true},{laserOn:true}]) {frame(s,middle,extra);visible.push(named('laserBeam').visible);}
const q=[0.3,-1.1,-0.7,0.4,-1.2,1.5];frame(s,q);
const moved={camera:rowMajor(named('cameraHead').matrix),frustum:positions(named('cameraFrustum'))};
globalThis.fetch=fetchFiles;await s.loadSkin(new URL('./twin/meshes/b601.json',base));
const afterSkin=named('cameraHead').children.every(o=>o.visible);
s.setPose(Object.fromEntries(C.joints.map((j,i)=>[j.id,[0,-2.4434609528,-1.1772453242,-0.2278,0,0][i]])),{laserOn:false});s.render();
const old={sensors:named('sensors').visible,frustum:named('cameraFrustum').visible,
 visible:named('laserBeam').visible,beam:positions(named('laserBeam')),opacity:named('laserBeam').material.opacity};
s.dispose();
console.log(JSON.stringify({initial,expected:endPoses(P,middle),ray:laserRay(P,middle),corners:frustumCorners(P,middle,0.18),
 measured,measuredBeam,visible,moved,movedExpected:endPoses(P,q),movedCorners:frustumCorners(P,q,0.18),afterSkin,old}));
''')
    initial = out['initial']
    assert initial['camera'] == pytest.approx(out['expected']['camera'])
    assert initial['laser'] == pytest.approx(out['expected']['laser'])
    assert [initial['body'][k] for k in ('width', 'height', 'depth')] == [0.025, 0.090, 0.025]
    assert initial['beam'][:3] == pytest.approx(out['ray']['origin'], abs=1e-7)
    assert initial['beam'][3:] == pytest.approx([o + 0.6 * d for o, d in zip(out['ray']['origin'], out['ray']['direction'])], abs=1e-7)
    assert out['measuredBeam'][3:] == pytest.approx(out['measured'], abs=1e-7)
    assert out['visible'] == [False, False, True] and out['afterSkin']
    for i in range(4):
        assert initial['frustum'][i * 12 + 3:i * 12 + 6] == pytest.approx(out['corners'][i], abs=1e-7)
        assert out['moved']['frustum'][i * 12 + 3:i * 12 + 6] == pytest.approx(out['movedCorners'][i], abs=1e-7)
    assert out['moved']['camera'] == pytest.approx(out['movedExpected']['camera'])
    assert not out['old']['sensors'] and not out['old']['frustum'] and out['old']['visible']
    assert out['old']['opacity'] == 0.28 and out['old']['beam'][-1] == pytest.approx(-0.2)


def test_overlay_segments_markers_coordinates_theme_and_disposal():
    out = node(SCENE_HOST + '''
const s=createScene(new Element(),{...C,scene:{...C.scene,pedestalHeight:9}});
const samples=ps=>ps.map((p,i)=>({t:i,p}));
const demoPath=[samples([[0,0,0.1],[0.1,0,0.1]]),samples([[0.3,0,0.1],[0.4,0,0.1]]),samples([[0.8,0,0.1]])];
s.setOverlay({demoPath,runPath:[samples([[0,0.01,0.1],[0.1,0.01,0.1]])],
 nodes:[{id:1,p:[0.2,0,0.3]},{id:2,p:[0.3,0,0.4],current:true}],
 spots:{measured:[0.5,0,0.3],reference:[0.5,0,0.3032],deviation_mm:3.2}});frame(s);
const groups=['demoPath','runPath','nodes','spots'];
const rows=Object.fromEntries(groups.map(name=>[name,{parentWorld:named(name).parent===drawnScene.children.find(o=>o.type==='Group'),
 points:named(name).children.map(o=>o.isLine?positions(o):o.position.toArray()),
 types:named(name).children.map(o=>o.material.type),radii:named(name).children.map(o=>o.geometry.parameters?.radius)}]));
const materials={demo:named('demoPath').children[0].material,run:named('runPath').children[0].material,
 current:named('nodes').children[1].material,measured:named('measured').material,frustum:named('cameraFrustum').material,camera:named('cameraHead').children[1].material};
const colors={'--twin-demo-path':'#112233','--twin-run-path':'#334455','--twin-joint':'#556677',
 '--twin-laser':'#778899','--twin-frustum':'#99aabb','--twin-camera':'#bbccdd'};
globalThis.getComputedStyle=()=>({getPropertyValue:name=>colors[name]||''});s.applyTheme();
const theme=Object.fromEntries(Object.entries(materials).map(([k,v])=>[k,v.color.getHexString()]));
const faded=materials.demo.opacity<materials.run.opacity;
let freed=0,total=0;groups.forEach(name=>named(name).traverse(o=>{if(o.geometry){total++;o.geometry.addEventListener('dispose',()=>freed++);}}));
s.setOverlay({spots:{reference:[0,0,0.3]}});const single=named('spots').children.length;
s.setOverlay(null);const empty=groups.every(name=>named(name).children.length===0);
s.dispose();console.log(JSON.stringify({rows,theme,faded,freed,total,single,empty}));
''')
    assert all(row['parentWorld'] for row in out['rows'].values())
    assert len(out['rows']['demoPath']['points']) == 2
    for actual, expected in zip(out['rows']['demoPath']['points'], [[0, 0, 0.1, 0.1, 0, 0.1], [0.3, 0, 0.1, 0.4, 0, 0.1]]):
        assert actual == pytest.approx(expected, abs=1e-7)
    assert out['rows']['demoPath']['types'] == ['LineDashedMaterial'] * 2
    assert out['rows']['runPath']['types'] == ['LineBasicMaterial']
    assert out['rows']['nodes']['radii'] == [0.004, 0.006]
    assert out['rows']['nodes']['points'] == [[0.2, 0, 0.3], [0.3, 0, 0.4]]
    assert out['rows']['spots']['points'][:2] == [[0.5, 0, 0.3], [0.5, 0, 0.3032]]
    assert out['theme'] == {'demo': '112233', 'run': '334455', 'current': '556677', 'measured': '778899', 'frustum': '99aabb', 'camera': 'bbccdd'}
    assert out['faded'] and out['freed'] == out['total'] and out['single'] == 1 and out['empty']


@pytest.mark.parametrize('view', ['arm', 'gripper'])
def test_view_target_follows_tcp_and_reset_restores_distance(view):
    out = node(SCENE_HOST + f'''
const s=createScene(new Element(),C,{{view:{json.dumps(view)}}}), rows=[];
for(const q of [middle,[0.3,-1.1,-0.7,0.4,-1.2,1.5]]) {{
 frame(s,q);const expected={json.dumps(view)}==='gripper'?position(endPoses(P,q).tcp):C.scene.cameraTarget;
 const at=drawnCamera.position.toArray(), direction=drawnCamera.getWorldDirection(drawnCamera.position.clone()).toArray();
 rows.push({{expected,at,direction,projected:s.projectPoint(expected)}});
}}
s.zoom(0.5);s.resetView();s.render();const reset=drawnCamera.position.toArray();
const manual=P.joints.map(j=>(j.limit[0]+j.limit[1])/2);frame(s,manual);
const manualFrustum=frustumCorners(P,manual,0.18).map(p=>s.projectPoint(p));
s.dispose();console.log(JSON.stringify({{rows,reset,manualFrustum}}));
''')
    distance = 0.45 if view == 'gripper' else 1.5
    for row in out['rows']:
        assert math.dist(row['expected'], row['at']) == pytest.approx(distance)
        assert [a + d * distance for a, d in zip(row['at'], row['direction'])] == pytest.approx(row['expected'])
        assert row['projected'] == pytest.approx([400, 280])
    assert out['reset'] == pytest.approx(out['rows'][-1]['at'])
    if view == 'gripper':
        assert all(point is not None for point in out['manualFrustum'])


@pytest.mark.parametrize('fallback', [True, False])
def test_twin_overlay_replace_clear_counts_labels_and_online_laser(fallback):
    out = node(SCENE_HOST + f'''
// DOM 宿主补齐 remove 的父子关系，用来验证标签清理。
Element.prototype.appendChild=function(e){{e.parent=this;this.children.push(e);return e;}};
Element.prototype.remove=function(){{if(this.parent)this.parent.children=this.parent.children.filter(e=>e!==this);}};
let twinCode=await readFile(new URL('./twin/twin.js',base),'utf8');
twinCode=absoluteImports(twinCode).replace('import("./scene.js")','import('+JSON.stringify(sceneUrl)+')')
 .replace('import("./fallback2d.js")','import('+JSON.stringify(new URL('./twin/fallback2d.js',base).href)+')');
const {{createTwin}}=await import(moduleUrl(twinCode));
const container=new Element(), twin=await createTwin(container,{{forceFallback:{str(fallback).lower()},skin:false,view:'gripper'}});
const first=twin.state();twin.update({{q_rad:middle,online:true}});settle();
const p=position(endPoses(P,middle).tcp), input={{demoPath:[ [{{t:0,p}},{{t:1,p:p.map(v=>v+0.01)}}], [{{t:2,p}}] ],
 nodes:[{{id:'<b>1</b>',p,current:true}}],spots:{{measured:p,reference:p.map(v=>v+0.0032),deviation_mm:3.2}},laser:{{on:true}}}};
twin.setOverlay(input);settle();const full=twin.state();
const labelTexts=()=>container.slots['.twin-labels'].children.filter(e=>['twin-node-label','twin-dev-label'].includes(e.className)).map(e=>e.textContent);
const labels=labelTexts();input.nodes.push({{id:2,p}});input.demoPath[0].push({{t:3,p}});
const copied=twin.state().overlay;
const beam=()=>{str(fallback).lower()}?null:named('laserBeam').visible;
const visible=[beam()];twin.update({{laser:false}});settle();visible.push(beam());
twin.update({{laser:true,online:false}});settle();visible.push(beam());
twin.update({{online:true}});settle();visible.push(beam());
twin.setOverlay({{spots:{{measured:p,reference:p,deviation_mm:null}}}});settle();const noNumber=labelTexts();
const replaced=twin.state().overlay;
twin.setOverlay(null);settle();const cleared=twin.state().overlay, clearedLabels=labelTexts();
twin.setOverlay({{}});settle();const empty=twin.state().overlay;
twin.dispose();twin.setOverlay(input);console.log(JSON.stringify({{first,full,labels,copied,visible,noNumber,replaced,cleared,clearedLabels,empty}}));
''')
    empty = {'demoPoints': 0, 'runPoints': 0, 'nodes': 0, 'hasSpots': False}
    full = {'demoPoints': 3, 'runPoints': 0, 'nodes': 1, 'hasSpots': True}
    assert out['first']['overlay'] == out['cleared'] == out['empty'] == empty
    assert out['first']['view'] == 'gripper' and out['full']['mode'] == 'live'
    assert out['full']['overlay'] == out['copied'] == full and out['full']['laser']
    assert out['labels'] == ([] if fallback else ['<b>1</b>', '偏差 3.2 mm'])
    assert out['visible'] == ([None] * 4 if fallback else [True, False, False, True])
    assert out['replaced'] == {**empty, 'hasSpots': True}
    assert out['noNumber'] == out['clearedLabels'] == []


def test_manual_demo_laser_overlay_button_and_view_option():
    out = node(DOM_HOST + r'''
import {readFile} from 'node:fs/promises';import {pathToFileURL} from 'node:url';
const url=pathToFileURL(process.cwd()+'/twin/demo.html');
let code=(await readFile(url,'utf8')).split('<script type="module">')[1].split('</script>')[0];
code=code.replace(/from "([^"]+)"/g,(_,p)=>'from '+JSON.stringify(new URL(p,url).href));
const els=Object.fromEntries(['stage','sliders','src','manual-actions','laser','overlay-demo'].map(id=>[id,new Element()]));
els.laser.checked=false;document.getElementById=id=>els[id];
globalThis.window={};globalThis.location={search:'?source=manual&view=gripper&render=2d&skin=simple'};
await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));settle();
const initial=window.demo.twin.state();els.laser.checked=true;els.laser.onchange();settle();
let overlay;const setOverlay=window.demo.twin.setOverlay;window.demo.twin.setOverlay=value=>{overlay=value;setOverlay(value);};
els['overlay-demo'].onclick();settle();const state=window.demo.twin.state();
window.demo.twin.dispose();console.log(JSON.stringify({initial,state,overlay}));
''')
    assert out['initial']['view'] == 'gripper' and out['initial']['laser'] is False
    assert out['state']['laser'] is True
    assert out['state']['overlay'] == {'demoPoints': 41, 'runPoints': 41, 'nodes': 3, 'hasSpots': True}
    overlay = out['overlay']
    assert overlay['demoPath'] != overlay['runPath'] and len(overlay['demoPath']) == len(overlay['runPath']) == 1
    assert [n['current'] for n in overlay['nodes']] == [False, True, False]
    assert math.dist(overlay['spots']['measured'], overlay['spots']['reference']) * 1000 == pytest.approx(3.2)
