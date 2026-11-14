"""T4：用真实 store/主机与虚拟时间测页面动作；不启动服务或浏览器。"""
from tests.test_console_shell import DOM, CONSOLE
from tests.test_trainer_views import jsdom_script
import re


SETUP = DOM + r'''
const {createStore}=await import('./console/state/store.js');
const {createMockConsole}=await import('./datasource/mock-console.js');
const {mount:mountPage}=await import('./console/pages/production/index.js');
const {mount:mountTopbar}=await import('./console/shell/topbar.js');
const {mount:mountTips}=await import('./console/shell/tooltip.js');
const {mount:mountDialog}=await import('./console/shell/dialog.js');
const {createReset}=await import('./console/shell/reset.js');
const source=createMockConsole({now:()=>0,setTimer:()=>1,clearTimer:()=>{}}),store=createStore();
const off=source.subscribe(m=>store.dispatch(m));source.start();
const ctx={store,send:(cmd,args)=>source.send(cmd,args)};
ctx.dialog=mountDialog(doc.body);ctx.reset=createReset(ctx);
const tips=mountTips(doc),topbar=mountTopbar(doc.querySelector('[data-topbar]'),ctx);
const pageRoot=doc.createElement('section');pageRoot.dataset.page='production';doc.body.append(pageRoot);
const page=mountPage(pageRoot,ctx);
const unsubscribe=store.subscribe(state=>{topbar.render(state);page.render(state);});
const $=s=>doc.querySelector(s);
const flush=async()=>{for(let i=0;i<6;i++){await Promise.resolve();tick(16);}};
await flush();
async function begin(){
  $('[data-action="start"]').click();
  const check=$('[data-confirm-check]');check.checked=true;check.dispatchEvent(new win.Event('change'));
  $('[data-action="confirm"]').click();await flush();
}
function advance(ms){for(let t=0;t<ms;t+=50){source.advance(Math.min(50,ms-t));tick(64);}}
function cleanup(){unsubscribe();off();source.stop();page.dispose();topbar.dispose();ctx.dialog.dispose();tips.dispose();dom.window.close();}
'''


def test_confirmation_guards_mouse_keyboard_rechecks_and_cancels():
    jsdom_script(SETUP + r'''
const start=$('[data-action="start"]');assert.equal(start.textContent,'开始');
assert.equal($('[data-recipe]').value,'plate-tube');start.focus();start.click();
const confirm=$('[data-action="confirm"]'),check=$('[data-confirm-check]');
assert.equal(check.checked,false);assert.equal(confirm.getAttribute('aria-disabled'),'true');
assert.equal(confirm.hasAttribute('disabled'),false);
const count=source.commands.length;confirm.click();key(confirm,'Enter');key(confirm,' ');await flush();
assert.equal(source.commands.length,count);assert.equal($('dialog').open,true);
check.checked=true;check.dispatchEvent(new win.Event('change'));assert.equal(confirm.getAttribute('aria-disabled'),'false');
check.checked=false;check.dispatchEvent(new win.Event('change'));assert.equal(confirm.getAttribute('aria-disabled'),'true');
key(confirm,'Escape');assert.equal($('dialog').open,false);assert.equal(doc.activeElement,start);
start.click();assert.equal($('[data-confirm-check]').checked,false);
await ctx.send('estop');await flush();
$('[data-confirm-check]').checked=true;$('[data-confirm-check]').dispatchEvent(new win.Event('change'));
confirm.click();await flush();assert.equal(source.commands.filter(c=>c.cmd==='run_start').length,0);
cleanup();
''')


def test_production_exact_status_sequence_result_count_and_selfcheck():
    jsdom_script(SETUP + r'''
assert.equal($('[data-count="sets"]').textContent,'0');assert.equal($('[data-count="pass-rate"]').textContent,'—');
assert.equal($('[data-result]').textContent,'—');assert.equal($('.production-trend span').textContent,'—');
await begin();const phases=[];
for(let t=0;t<=38000;t+=50){
  const word=$('[data-status]').textContent;if(phases.at(-1)!==word)phases.push(word);
  if(t===2700){assert.equal(doc.querySelectorAll('[data-check-item][data-ok="true"]').length,9);}
  if(t===7500){assert.equal(doc.querySelectorAll('[data-target-box]').length,4);
    assert.match($('.production-targets').textContent,/圆盘定位工装97%定位柱97%薄片97%空心圆柱97%/);}
  if(t===9500){assert.equal($('[data-action="start"]').getAttribute('aria-disabled'),'true');
    assert.equal($('[data-action="start"]').dataset.reason,'正在生产，完成后可再次开始');
    assert.equal($('[data-angle]').textContent,'0.0°');}
  if(t===14500){assert.equal($('[data-angle]'),null);assert.equal(doc.querySelectorAll('[data-target-box]').length,0);}
  if(t<38000)advance(50);
}
assert.deepEqual(phases.filter(p=>p!=='就绪'),['自检中','识别中','抓取中','放置中','抓取中','放置中','检查中','完成','待命']);
assert.equal($('[data-count="sets"]').textContent,'1');assert.equal($('[data-count="pass-rate"]').textContent,'100%');
assert.equal($('[data-result]').textContent,'到位');assert.match($('.production-sparkline').getAttribute('aria-label'),/0.4/);
assert.equal($('[data-action="start"]').getAttribute('aria-disabled'),'false');
assert.equal(doc.querySelectorAll('[data-progress="done"]').length,10);
assert.ok(!JSON.stringify(store.getState().runs).includes('angle'));
assert.ok(source.commands.every(c=>!c.cmd.startsWith('laser_')));cleanup();
''')


def test_estop_freezes_held_part_and_one_reset_allows_second_run():
    jsdom_script(SETUP + r'''
const original=structuredClone(store.getState().workspace);
await begin();advance(14000);assert.equal(store.getState().workspace.props.find(p=>p.id==='plate').held,true);
$('[data-action="estop"]').click();await flush();
const frozen=structuredClone(store.getState());advance(5000);
assert.equal($('[data-status]').textContent,'急停');assert.deepEqual(store.getState().joint.q,frozen.joint.q);
assert.deepEqual(store.getState().workspace,frozen.workspace);assert.equal($('[data-angle]'),null);
const from=source.commands.length;$('[data-action="reset"]').click();await flush();
assert.deepEqual(source.commands.slice(from).map(c=>c.cmd),['reset_demo','reset_estop']);
assert.equal($('dialog').open,false);assert.equal($('[data-status]').textContent,'待命');
assert.equal($('[data-count="sets"]').textContent,'0');assert.deepEqual(store.getState().workspace,original);
await begin();advance(38000);assert.equal($('[data-count="sets"]').textContent,'1');
await begin();advance(38000);assert.equal($('[data-count="sets"]').textContent,'2');
assert.equal(store.getState().runs.length,2);
$('[data-action="reset"]').click();await flush();assert.equal($('[data-count="sets"]').textContent,'0');
assert.equal($('[data-count="pass-rate"]').textContent,'—');assert.equal($('[data-result]').textContent,'—');
assert.deepEqual(store.getState().workspace,original);cleanup();
''')


def test_props_follow_done_events_and_reset_is_immutable():
    jsdom_script(SETUP + r'''
const {WORKSPACE}=await import('./datasource/fixtures/workspace.js');const seed=structuredClone(WORKSPACE);
const original=store.getState();await begin();advance(13950);
assert.equal(store.getState().workspace.props.find(p=>p.id==='plate').held,false);
advance(50);assert.equal(store.getState().workspace.props.find(p=>p.id==='plate').held,true);
advance(5000);
const workspace=store.getState().workspace,plate=workspace.props.find(p=>p.id==='plate');
assert.equal(plate.held,false);assert.deepEqual(plate.pose,workspace.props.find(p=>p.kind==='post').pose);
assert.deepEqual(original.workspace.props,seed.props);assert.deepEqual(WORKSPACE,seed);
advance(19000);assert.equal(store.getState().workspace.props.find(p=>p.id==='tube').held,false);
assert.deepEqual(store.getState().workspace.props.find(p=>p.id==='tube').pose,plate.pose);cleanup();
''')


def test_observation_annotations_stay_in_frame_and_keep_target_leaders():
    jsdom_script(SETUP + r'''
const rect=win.HTMLElement.prototype.getBoundingClientRect;
win.HTMLElement.prototype.getBoundingClientRect=function(){
  if(this.classList.contains('production-camera'))return{width:192,height:144};
  if(this.dataset.target)return{width:84,height:40};
  return rect.call(this);
};
await begin();advance(7500);
const labels=[...doc.querySelectorAll('.production-targets [data-target]')];
assert.equal(labels.length,4);assert.equal(doc.querySelectorAll('[data-target-leader]').length,4);
const boxes=labels.map(el=>({x:parseFloat(el.style.left),y:parseFloat(el.style.top)}));
for(const [i,a] of boxes.entries()){
  assert.ok(a.x>=0&&a.y>=0&&a.x+84<=192&&a.y+40<=144);
  for(const b of boxes.slice(i+1))assert.ok(a.x+84<=b.x||b.x+84<=a.x||a.y+40<=b.y||b.y+40<=a.y);
}
advance(2000);assert.equal($('[data-angle]').closest('[data-target]').dataset.target,'plate');
advance(4500);assert.equal($('[data-angle]'),null);
win.HTMLElement.prototype.getBoundingClientRect=rect;cleanup();
''')


def test_real_link_reset_requires_confirmation_and_never_resets_demo():
    jsdom_script(SETUP + r'''
let state={...store.getState(),hello:{proto:1,sim:false},phase:'estop'},commands=[];
const reset=createReset({store:{getState:()=>state},send:async cmd=>{commands.push(cmd);return{ok:true};},dialog:ctx.dialog});
reset();assert.equal($('dialog').open,true);assert.match($('dialog').textContent,/确认解除急停/);assert.deepEqual(commands,[]);
key($('[data-action="confirm"]'),'Escape');assert.deepEqual(commands,[]);
reset();$('[data-action="confirm"]').click();await flush();assert.deepEqual(commands,['reset_estop']);
state={...state,phase:'idle'};reset();await flush();assert.deepEqual(commands,['reset_estop']);
state={...state,phase:'estop',hello:{proto:1}};reset();assert.equal($('dialog').open,true);cleanup();
''')


def test_reset_rejection_does_not_clear_counts_or_release_estop():
    jsdom_script(SETUP + r'''
await begin();advance(38000);let sent=[];
const reset=createReset({...ctx,send:async cmd=>{sent.push(cmd);return{ok:false,msg:'连接已关闭'};}});
await reset();await flush();assert.deepEqual(sent,['reset_demo']);
assert.equal($('dialog').open,true);
assert.equal($('[data-count="sets"]').textContent,'1');assert.match($('dialog').textContent,/重置未完成.*连接已关闭/);
cleanup();
''')


def test_training_offline_and_command_failure_disable_without_fake_start():
    jsdom_script(SETUP + r'''
await ctx.send('train_start',{target:'part',draft:{id:'plate'}});await flush();
assert.equal($('[data-action="start"]').getAttribute('aria-disabled'),'true');
assert.match($('[data-action="start"]').dataset.reason,/正在训练/);$('[data-action="start"]').click();assert.equal($('dialog').open,false);
await ctx.reset();await flush();ctx.send=async()=>({ok:false,msg:'请求未完成'});
// page 上下文保存了原 send；另挂同一视图验证拒绝应答。
page.dispose();const second=mountPage(pageRoot,ctx);second.render(store.getState());await flush();
await begin();assert.match($('.production-message').textContent,/请求未完成/);assert.equal($('[data-status]').textContent,'待命');
store.dispatch({type:'link',online:false});second.render(store.getState());await flush();
assert.equal($('[data-action="start"]').getAttribute('aria-disabled'),'true');
assert.equal($('[data-action="estop"]').getAttribute('aria-disabled'),'true');second.dispose();cleanup();
''')


def test_twin_public_adapter_options_coalescing_props_and_disposal():
    jsdom_script(SETUP + r'''
const {mount}=await import('./console/pages/production/views/twin-stage.js');
let options,updates=[],props=[],disposed=0;
const view=await mount($('[data-twin-stage]'),{createTwin:async(root,opts)=>{options=opts;return{
  update:value=>updates.push(value),setProps:value=>props.push(structuredClone(value)),dispose:()=>disposed++};}});
const state=store.getState();view.render(state);view.render(state);tick(16);
assert.deepEqual(options,{status:false,labels:'hover'});assert.equal(updates.length,1);assert.equal(props.length,1);
assert.deepEqual(updates[0].q_rad,state.joint.q);assert.equal(updates[0].gripper_mm,state.joint.gripper_mm);
view.render(state);tick(16);assert.equal(props.length,1);
await begin();advance(14000);view.render(store.getState());tick(16);
assert.equal(props.at(-1).find(p=>p.id==='plate').held,true);
view.render(state);view.dispose();tick(16);assert.equal(disposed,1);assert.equal(updates.length,3);cleanup();
''')


def test_production_styles_are_scoped_token_based_and_old_modules_not_loaded():
    css = (CONSOLE / 'pages/production/production.css').read_text()
    assert not re.search(r'#[\da-fA-F]{3,8}\b|(?:rgb|hsl)a?\(|\d+px|gradient\(|shadow:', css)
    assert not re.search(r'--fs-(?:2xs|xs|chart)\b', css)
    for selector in re.findall(r'([^{}]+)\{', css):
        assert selector.strip().startswith(('[data-page="production"]', '@media'))
    main = (CONSOLE / 'main.js').read_text()
    assert 'optional("twin"' in main and 'import("../twin/twin.js")' in main
    assert 'createReset(ctx)' in main
