"""T7：同帧状态、输入方式、真实量级时长、观察避让和抓放 FK 回归。"""
from tests.test_console_data import BASE
from tests.test_console_production import SETUP
from tests.test_console_shell import DOM
from tests.test_trainer_views import node, jsdom_script


def test_status_and_step_highlight_change_in_same_frame_and_ignore_late_steps():
    jsdom_script(SETUP + r'''
await begin();
for (let ms=0;ms<38000;ms+=50) {
  source.advance(50);tick(16);
  const state=store.getState(),current=$('.production-stepper [aria-current="step"]');
  const label={to_observe:'到观察位',recognize:'识别',pick:'抓取',place:'放置',inspect:'检查',done:'完成',to_fold:'收回'}[state.phase];
  if(label)assert.ok(current?.textContent.startsWith(label),JSON.stringify({ms,phase:state.phase,current:current?.textContent}));
  if(['pick','place'].includes(state.phase))assert.ok(current.textContent.endsWith(state.library.parts.find(p=>p.id===state.run.part_id).name));
}
await ctx.reset();await flush();await begin();source.advance(14500);tick(16);
const before=store.getState();assert.equal(before.phase,'place');assert.equal(before.step.action,'place');
store.dispatch({v:1,type:'step_state',run_id:before.run.run_id,index:1,part_id:'plate',action:'pick',status:'done',t:before.run.t+1,seq:99999});
assert.equal(store.getState(),before);tick(16);
assert.equal($('[data-status]').textContent,'放置中');assert.equal($('.production-stepper [aria-current="step"]').textContent,'放置 · 薄片');
cleanup();
''')


def test_tooltip_only_keyboard_focus_or_hover_and_expires_after_four_seconds():
    jsdom_script(DOM + r'''
const {mount,setUnavailable}=await import('./console/shell/tooltip.js');
const button=doc.createElement('button');doc.body.append(button);setUnavailable(button,'正在生产，完成后可再次开始');
const view=mount(doc),tip=doc.querySelector('[data-tip]');
const matches=button.matches.bind(button);let visibleFocus=false;
button.matches=selector=>selector===':focus-visible'?visibleFocus:matches(selector);
pointer(button,'pointerdown');button.focus();tick(6000);assert.equal(tip.hidden,true);
pointer(button,'pointerenter');tick(799);assert.equal(tip.hidden,true);tick(51);assert.equal(tip.hidden,false);
tick(3999);assert.equal(tip.hidden,false);tick(1);assert.equal(tip.hidden,true);tick(6000);assert.equal(tip.hidden,true);
assert.equal(button.hasAttribute('aria-describedby'),false);
pointer(button,'pointerleave');button.blur();key(doc.body,'Tab');visibleFocus=true;button.focus();
tick(850);assert.equal(tip.hidden,false);tick(4000);assert.equal(tip.hidden,true);
button.blur();visibleFocus=false;button.focus();tick(850);assert.equal(tip.hidden,true);
// 对话框关闭后由鼠标操作归还的焦点，也不能重新显示提示。
pointer(button,'pointerdown');button.blur();visibleFocus=true;button.focus();tick(6000);assert.equal(tip.hidden,true);
view.dispose();assert.equal(doc.querySelector('[data-tip]'),null);dom.window.close();
''')


def test_training_clock_fixtures_progress_archive_and_formats_agree():
    node(BASE + r'''
import {duration,time} from './console/widgets/format.js';
import {duration as docDuration} from './console/pages/parts/views/format.js';
const docs=[...PARTS,...RECIPES];
assert.equal(new Set(docs.map(d=>d.training.elapsed_ms)).size,5);
assert.equal(new Set(docs.map(d=>d.collected_at)).size,5);
assert.equal(new Set(docs.map(d=>time(d.collected_at))).size,5);
for(const doc of docs){
  const tr=doc.training;
  assert.ok(tr.elapsed_ms>=30*60000 && tr.elapsed_ms<=50*60000);
  assert.equal(tr.recorded_at,doc.collected_at);assert.equal(tr.images,tr.elapsed_ms/500);
  for(const round of tr.rounds)assert.equal(round.images,round.elapsed_ms/500);
}
for(const [ms,expected] of [[0,'0:00'],[59999,'0:59'],[60000,'1:00'],[3599999,'59:59'],[3600000,'1:00:00'],[3661000,'1:01:01'],[90061000,'25:01:01'],[-1,'—'],[NaN,'—'],[null,'—']]){
  assert.equal(duration(ms),expected);assert.equal(docDuration(ms),expected);
}
await host.send('train_start',{target:'part',draft:{id:'plate'}});const started=last('train_progress').t;
for(let round=1;round<=8;round++){
  host.advance(1200);const p=last('train_progress');
  assert.equal(p.round,round);assert.equal(p.elapsed_ms,round*300000);assert.equal(p.images,round*600);
  assert.equal(p.t-started,round*1200);
}
const progress=messages.filter(m=>m.type==='train_progress'&&m.round>0);
const archive=last('part_doc').training,record=store.getState().trains[0];
assert.equal(record.elapsed_ms,2400000);assert.equal(archive.elapsed_ms,2400000);
assert.equal(record.images,4800);assert.equal(archive.images,4800);
assert.deepEqual(archive.rounds,progress.map(({round,deviation_mm,grasp_ok,images,elapsed_ms})=>({round,deviation_mm,grasp_ok,images,elapsed_ms})));
assert.equal(last('train_done').t-started,9600);
''')


def test_pick_place_fk_within_five_mm_and_held_mesh_follows_tcp_then_stacks():
    node(BASE + r'''
import * as THREE from '../vendor/three.module.min.js';
import {createPropsLayer} from './twin/props.js';
const world=new THREE.Group(),material=new THREE.MeshBasicMaterial(),edge=new THREE.LineBasicMaterial();
const layer=createPropsLayer(THREE,world,{body:material,plate:material},edge);
const fk=q=>{const m=endPoses(ARM_PARAMS,q).tcp;return [m[3],m[7],m[11]];};
const distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
const mesh=id=>world.getObjectByName(id),center=id=>{const e=mesh(id).matrix.elements;return [e[12],e[13],e[14]];};
for(const part of PARTS){
  const prop=WORKSPACE.props.find(p=>p.id===part.id);
  assert.ok(distance(fk(POSES.parts[part.id].contact),prop.pose)<=0.005,part.id);
}
let workspace,checks=0,placedPlate;
const sync=()=>{const s=store.getState();layer.update(endPoses(ARM_PARAMS,s.joint.q).tcp);
  if(workspace!==s.workspace){workspace=s.workspace;layer.setProps(workspace.props);}};
sync();await host.send('run_start',{recipe_id:'plate-tube'});
for(let ms=50;ms<=38000;ms+=50){
  host.advance(50);sync();const s=store.getState(),tcp=fk(s.joint.q);
  for(const prop of s.workspace.props.filter(p=>p.held))assert.ok(distance(center(prop.id),tcp)<=0.005,`held ${ms}`);
  const contact={14000:'plate',19000:'plate',24000:'tube',29000:'tube'}[ms];
  if(contact){
    checks++;const error=distance(tcp,center(contact));
    assert.ok(error<=0.005,JSON.stringify({ms,tcp,part:center(contact),error_mm:error*1000}));
    if(ms===19000)placedPlate=[...center('plate')];
    if(ms===29000){
      const plate=s.workspace.props.find(p=>p.id==='plate'),tube=s.workspace.props.find(p=>p.id==='tube');
      const post=s.workspace.props.find(p=>p.id==='post');
      assert.deepEqual(tube.pose.slice(0,2),post.pose.slice(0,2));
      assert.ok(Math.abs(tube.pose[2]-tube.size_m[2]/2-plate.pose[2]-plate.size_m[2]/2)<1e-12);
      assert.ok(tube.pose[2]+tube.size_m[2]/2<post.pose[2]+post.size_m[2]/2);
    }
  }
  if(placedPlate)assert.deepEqual(center('plate'),placedPlate);
}
assert.equal(checks,4);assert.ok(store.getState().workspace.props.every(p=>!p.held));
''')


def test_observation_labels_are_outside_objects_without_overlap_at_target_sizes():
    node(r'''
import assert from 'node:assert/strict';
import {observationLayout,imageTransform} from './console/pages/production/views/observation-layout.js';
import {initialWorkspace,workspaceBox} from './console/state/workspace.js';
const workspace=initialWorkspace();
const separated=(a,b)=>a.left+a.width<=b.left||b.left+b.width<=a.left||a.top+a.height<=b.top||b.top+b.height<=a.top;
for(const width of [320,378,400,520])for(const count of [4,6]){
  const height=width*2/3,sizes=Array.from({length:count},(_,i)=>({width:(width-24)/2,height:i%2?44:26}));
  const {plot,labels}=observationLayout(width,height,sizes,4),t=imageTransform(plot,workspace.image);
  const objects=workspace.props.map(p=>{const [x,y,w,h]=workspaceBox(workspace,p);
    return{left:t.x+x*t.scale,top:t.y+y*t.scale,width:w*t.scale,height:h*t.scale};});
  assert.ok(plot.height>=60);
  for(const [i,a] of labels.entries()){
    assert.ok(a.left>=0&&a.top>=0&&a.left+a.width<=width&&a.top+a.height<=height);
    assert.ok(objects.every(b=>separated(a,b)),JSON.stringify({width,count,a,objects}));
    assert.ok(labels.slice(i+1).every(b=>separated(a,b)));
  }
}
''')


def test_recent_deviation_single_point_has_value_and_all_points_stay_inside_chart():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/widgets/sparkline.js');
const trendRoot=doc.createElement('div');doc.body.append(trendRoot);const view=mount(trendRoot);
for(const values of [[],[0.4],[0.4,0.3,1.9],[0.0],[],[1.0]]){
  view.render(values);tick(16);
  const chart=trendRoot.querySelector('svg'),value=trendRoot.querySelector('.production-trend-value'),dot=chart.querySelector('circle');
  assert.equal(chart.style.display,values.length?'':'none');
  assert.equal(value.hidden,values.length!==1);
  assert.equal(value.textContent,values.length===1?`${values[0].toFixed(1)} mm`:'');
  if(!values.length)continue;
  const [, ,width,height]=chart.getAttribute('viewBox').split(' ').map(Number),radius=Number(dot.getAttribute('r'));
  const x=Number(dot.getAttribute('cx')),y=Number(dot.getAttribute('cy'));
  assert.ok(x-radius>0&&x+radius<width&&y-radius>0&&y+radius<height);
  if(values.length===1){assert.equal(y,height/2);assert.equal(chart.querySelector('polyline').style.display,'none');}
  else for(const point of chart.querySelector('polyline').getAttribute('points').split(' ')){
    const [px,py]=point.split(',').map(Number);assert.ok(px>0&&px<width&&py>0&&py<height);
  }
}
view.dispose();assert.equal(trendRoot.childElementCount,0);dom.window.close();
''')
