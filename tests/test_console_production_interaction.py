"""生产页交互：真实视图、共享工具和虚拟时钟，不触碰设备。"""
import json
import re

import pytest

from tests.test_console_shell import DOM, CONSOLE
from tests.test_console_production import SETUP
from tests.test_trainer_views import jsdom_script


RECIPE_SETUP = DOM + r'''
const {initialState}=await import('./console/state/store.js');
const {mount:mountSteps}=await import('./console/pages/production/views/steps.js');
const {mount:mountChips}=await import('./console/pages/production/views/stage-chips.js');
const stepsRoot=doc.createElement('section'),stageRoot=doc.createElement('div');
doc.body.append(stepsRoot,stageRoot);
const recipe={id:'selected',name:'当前配方',steps:[{part_id:'plate'},{part_id:'tube'}]};
const ctx={selection:{id:recipe.id}},base={...initialState(),link:{online:true},hello:{proto:1,sim:true},
  library:{parts:[{id:'plate',name:'薄片'},{id:'tube',name:'圆柱'}],recipes:[recipe]}};
const steps=mountSteps(stepsRoot,ctx),chips=mountChips(stageRoot,ctx);
function draw(state){steps.render(state);chips.render(state);tick(16);}
function finish(){steps.dispose();chips.dispose();dom.window.close();}
'''


@pytest.mark.parametrize('phase,run', [
    ('idle', None), ('estop', None),
    ('estop', {'run_id': 'interrupted'}),
    ('pick', {'run_id': 'active', 'step_index': 1}),
])
def test_recipe_fallback_keeps_pick_place_steps_and_chip_without_recipe_doc(phase, run):
    jsdom_script(RECIPE_SETUP + f'const state={{...base,phase:{json.dumps(phase)},run:{json.dumps(run)}}};' + r'''
draw(state);
assert.equal(stepsRoot.querySelectorAll('li').length,10,'配方文档未到达时仍保留抓取/放置步骤');
assert.match(stepsRoot.textContent,/抓取 · 薄片.*放置 · 薄片.*抓取 · 圆柱.*放置 · 圆柱/);
assert.equal(stageRoot.querySelector('.tr').textContent,'当前配方','缺少运行配方 ID 时回退当前选择');
finish();
''')


def test_missing_run_recipe_id_uses_selected_document_in_both_views():
    jsdom_script(RECIPE_SETUP + r'''
draw({...base,phase:'estop',run:{run_id:'interrupted'},recipeDocs:{selected:recipe}});
assert.equal(stageRoot.querySelector('.tr').textContent,'当前配方');
assert.equal(stepsRoot.querySelectorAll('li').length,10);
finish();
''')


def test_running_recipe_wins_and_documents_override_library_without_mutating_state():
    jsdom_script(RECIPE_SETUP + r'''
const {productionRecipe}=await import('./console/state/selectors.js');
const running={id:'running',name:'运行配方',steps:[{part_id:'tube'}]},detail={...running,name:'运行配方详情'};
const state={...base,phase:'estop',run:{recipe_id:running.id},library:{...base.library,recipes:[recipe,running]}};
const before=JSON.stringify(state);
assert.equal(productionRecipe(state,recipe.id),running);
draw(state);assert.equal(stepsRoot.querySelectorAll('li').length,8);
assert.equal(stageRoot.querySelector('.tr').textContent,'运行配方');
const documented={...state,recipeDocs:{running:detail}};
assert.equal(productionRecipe(documented,recipe.id),detail);
draw(documented);tick(160);assert.equal(stageRoot.querySelector('.tr').textContent,'运行配方详情');
assert.equal(JSON.stringify(state),before);
assert.equal(productionRecipe({...state,run:{recipe_id:'missing'}},recipe.id),undefined);
assert.equal(productionRecipe({...state,run:{recipe_id:''}},recipe.id),recipe);
finish();
''')


@pytest.mark.parametrize('reduced', [False, True])
def test_step_scroll_tracks_changes_only_and_respects_reduced_motion(reduced):
    jsdom_script(RECIPE_SETUP + f'const reduced={json.dumps(reduced)};' + r'''
win.matchMedia=()=>({matches:reduced});
const calls=[];
win.HTMLElement.prototype.scrollIntoView=function(options){calls.push({label:this.textContent,options});};
const state={...base,phase:'pick',run:{run_id:'r1',recipe_id:'selected',step_index:1}};
draw(state);assert.equal(calls.length,1);assert.equal(calls[0].label,'抓取 · 薄片');
assert.deepEqual(calls[0].options,{block:'nearest',behavior:reduced?'auto':'smooth'});
draw({...state,joint:{q:[0]}});draw(state);assert.equal(calls.length,1);
draw({...state,phase:'place'});assert.equal(calls.length,2);assert.equal(calls[1].label,'放置 · 薄片');
draw({...state,phase:'selfcheck'});assert.equal(calls.length,2);
stepsRoot.hidden=true;draw(state);assert.equal(calls.length,2);
stepsRoot.hidden=false;draw(state);assert.equal(calls.length,3);
draw({...state,phase:'estop'});assert.equal(calls.length,3);
steps.render(state);steps.dispose();tick(32);assert.equal(calls.length,3);
chips.dispose();dom.window.close();
''')


def test_step_progress_matches_current_step_total_and_completed_run():
    jsdom_script(RECIPE_SETUP + r'''
const bar=stepsRoot.querySelector('[role="progressbar"]'),count=stepsRoot.querySelector('.production-steps-count');
const run={run_id:'r1',recipe_id:'selected',step_index:1};
for(const [phase,value] of [['idle',0],['selfcheck',1],['recognize',3],['pick',4],['place',5],['inspect',8],['done',9],['to_fold',10]]){
  draw({...base,phase,run});
  assert.equal(count.textContent,`${value} / 10`);
  assert.equal(bar.getAttribute('aria-valuenow'),String(value));
  assert.equal(bar.getAttribute('aria-valuemax'),'10');
  assert.equal(bar.firstElementChild.style.width,`${value*10}%`);
}
draw({...base,phase:'idle',run,runs:[{run_id:'r1'}]});assert.equal(count.textContent,'10 / 10');
draw(base);assert.equal(count.textContent,'0 / 10');
assert.equal(bar.classList.contains('c-progress'),true);assert.equal(bar.previousElementSibling.tagName,'H2');
draw({...base,phase:'pick',run});
assert.equal(stepsRoot.querySelectorAll('.production-step-dot.c-pulse').length,1);
assert.equal(stepsRoot.querySelector('.production-step-dot').getAttribute('aria-hidden'),'true');
finish();
''')


def test_start_checkbox_initial_focus_and_enter_share_confirm_guards():
    jsdom_script(SETUP + r'''
const start=$('[data-action="start"]');start.focus();start.click();
let check=$('[data-confirm-check]');assert.equal(doc.activeElement,check);
key(check,'Enter');assert.equal(source.commands.filter(c=>c.cmd==='run_start').length,0);
assert.equal($('dialog').open,true);
check.checked=true;check.dispatchEvent(new win.Event('change'));
check.dispatchEvent(new win.KeyboardEvent('keydown',{key:'Enter',repeat:true,bubbles:true}));
assert.equal($('dialog').open,true);
key(check,'Enter');await flush();
assert.equal(source.commands.filter(c=>c.cmd==='run_start').length,1);
assert.equal($('dialog').open,false);assert.equal(doc.activeElement,start);
await ctx.reset();await flush();start.click();check=$('[data-confirm-check]');
check.checked=true;check.dispatchEvent(new win.Event('change'));
await ctx.send('estop'); // 不等待下一帧；按回车时仍须重新核对最新状态。
key(check,'Enter');await flush();
assert.equal(source.commands.filter(c=>c.cmd==='run_start').length,1);
assert.equal($('dialog').open,true);cleanup();
''')


def test_kpi_flash_only_on_display_changes_and_keeps_rate_animation_class():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/pages/production/views/key-number.js');
const rootEl=doc.createElement('section');doc.body.append(rootEl);const view=mount(rootEl);
view.render({runs:[]});tick(16);assert.equal(rootEl.querySelectorAll('.c-flash').length,0);
const runs=[{run_id:'r1',ok:true,deviation_mm:0.4,duration_ms:32000}];
view.render({runs});tick(16);assert.equal(rootEl.querySelectorAll('.c-flash').length,4);
assert.equal(rootEl.querySelector('[data-count="pass-rate"]').classList.contains('c-flash'),true);
for(const el of rootEl.querySelectorAll('.c-flash'))el.dispatchEvent(new win.Event('animationend'));
view.render({runs:[...runs]});tick(16);assert.equal(rootEl.querySelectorAll('.c-flash').length,0);
view.render({runs:[...runs,{...runs[0],run_id:'r2'}]});tick(16);
assert.equal(rootEl.querySelectorAll('.c-flash').length,1);
assert.equal(rootEl.querySelector('.c-flash').dataset.count,'sets');
view.dispose();dom.window.close();
''')


@pytest.mark.parametrize('reduced', [False, True])
def test_completion_chip_returns_to_live_step_once_and_ignores_history(reduced):
    jsdom_script(RECIPE_SETUP + f'const reduced={json.dumps(reduced)};' + r'''
win.matchMedia=()=>({matches:reduced});
const run={run_id:'r1',recipe_id:'selected'},record={run_id:'r1',ok:true};
draw({...base,phase:'inspect',run});
const done={...base,phase:'done',run,runs:[record]};
draw(done);tick(160);assert.equal(stageRoot.querySelector('.br').textContent,'完成 ✓');
draw({...done,phase:'to_fold'});tick(600);draw({...done,phase:'to_fold',runs:[record]});
tick(1200);assert.equal(stageRoot.querySelector('.br').textContent,'收回');
draw(done);tick(160);assert.equal(stageRoot.querySelector('.br').textContent,'完成');
chips.dispose();tick(2000);assert.equal(stageRoot.querySelector('.br'),null);
const history=mountChips(stageRoot,ctx);history.render(done);tick(16);
assert.equal(stageRoot.querySelector('.br').textContent,'完成');
history.dispose();steps.dispose();dom.window.close();
''')


@pytest.mark.parametrize('replacement', ['estop', 'reset', 'next_run', 'offline'])
def test_completion_clears_on_interrupt_reset_or_next_run(replacement):
    jsdom_script(RECIPE_SETUP + f'const replacement={json.dumps(replacement)};' + r'''
draw(base);
const done={...base,phase:'done',run:{run_id:'r1'},runs:[{run_id:'r1'}]};
draw(done);
let state={...done,phase:'estop'},expected='急停';
if(replacement==='reset'){state=base;expected='等待开始';}
if(replacement==='next_run'){state={...done,phase:'selfcheck',run:{run_id:'r2'}};expected='自检';}
if(replacement==='offline'){state={...done,link:{online:false}};expected='完成';}
draw(state);
if(replacement==='estop')assert.equal(stageRoot.querySelector('.br').textContent,'急停');
tick(160);assert.equal(stageRoot.querySelector('.br').textContent,expected);
tick(2000);assert.equal(stageRoot.querySelector('.br').textContent,expected);
finish();
''')


def test_both_viewports_follow_busy_state_including_link_changes_and_dispose():
    jsdom_script(RECIPE_SETUP + r'''
const {mount:mountObserve}=await import('./console/pages/production/views/observe-view.js');
const observeRoot=doc.createElement('section');doc.body.append(observeRoot);const observe=mountObserve(observeRoot);
const camera=observeRoot.querySelector('.c-viewport');
for(const [phase,busy] of [['idle',false],['selfcheck',true],['recognize',true],['pick',true],['inspect',true],['to_fold',true],['estop',false]]){
  const state={...base,phase};draw(state);observe.render(state);tick(16);
  assert.equal(stageRoot.dataset.busy,String(busy));assert.equal(camera.dataset.busy,String(busy));
}
const offline={...base,phase:'pick',link:{online:false}};draw(offline);observe.render(offline);tick(16);
assert.equal(stageRoot.dataset.busy,'false');assert.equal(camera.dataset.busy,'false');
draw(base);draw({...base,runs:[{run_id:'r1'}],phase:'done'});tick(160);
observe.dispose();finish();assert.equal(timers.size,0);
''')


def test_page_uses_shared_stagger_and_has_no_duplicate_keyframes():
    jsdom_script(SETUP + r'''
const elements=[pageRoot.querySelector('.production-viewport'),...pageRoot.querySelectorAll('.production-section')];
assert.deepEqual(elements.map(el=>el.style.getPropertyValue('--i')),['0','2','1','3','4']);
assert.ok(elements.every(el=>el.classList.contains('c-enter')));cleanup();
''')
    css = (CONSOLE / 'pages/production/production-motion.css').read_text()
    assert '@keyframes' not in css
    assert 'prefers-reduced-motion: reduce' in css
    assert 'animation: none !important' in css and 'transition: none !important' in css
    assert not re.search(r'\.(?:c-enter|c-flash|c-swap-out|c-swap-in|c-pulse|c-progress)\s*\{', css)
