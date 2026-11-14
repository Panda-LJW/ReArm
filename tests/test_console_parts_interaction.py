"""零件库交互：真实 store/命令、共享 swap、虚拟时间与键盘事件。"""
import re

from tests.test_console_shell import CONSOLE, DOM
from tests.test_trainer_views import jsdom_script

SETUP = DOM + r'''
const {createStore}=await import('./console/state/store.js');
const {createMockConsole}=await import('./datasource/mock-console.js');
const {mount}=await import('./console/pages/parts/index.js');
const source=createMockConsole({now:()=>0,setTimer:()=>1,clearTimer:()=>{}}),store=createStore();
const off=source.subscribe(message=>store.dispatch(message));source.start();
const rootEl=doc.createElement('section');rootEl.dataset.page='parts';doc.body.append(rootEl);
const view=mount(rootEl,{store,send:(cmd,args)=>source.send(cmd,args)});
const unsubscribe=store.subscribe(state=>view.render(state));
const flush=async()=>{for(let i=0;i<8;i++){await Promise.resolve();tick(16);}};
const settle=async()=>{await flush();tick(180);await flush();};
const button=text=>[...rootEl.querySelectorAll('button')].find(el=>el.textContent===text&&!el.closest('[hidden]'));
const click=async text=>{assert.ok(button(text),text);button(text).click();await settle();};
const input=(label,value)=>{const el=rootEl.querySelector(`input[aria-label="${label}"]`);el.value=value;el.dispatchEvent(new win.Event('input'));};
function styled(reduce=false){
  const style=doc.createElement('style');style.textContent='* { --t-fast:120ms; }';doc.head.append(style);
  win.matchMedia=()=>({matches:reduce});
}
const finish=()=>{unsubscribe();view.dispose();off();source.stop();dom.window.close();};
await flush();
'''


def test_rows_roving_selection_boundaries_enter_and_scroll_preferences():
    jsdom_script(SETUP + r'''
let reduce=false;win.matchMedia=()=>({matches:reduce});
const scrolls=[];win.HTMLElement.prototype.scrollIntoView=function(options){scrolls.push([this,options]);};
const rows=()=>[...rootEl.querySelectorAll('#library-parts .library-open')];
rows()[0].focus();const before=source.commands.length;
assert.equal(key(rows()[0],'ArrowDown').defaultPrevented,true);
assert.equal(doc.activeElement,rows()[1]);assert.ok(rows()[1].closest('tr').classList.contains('library-row-selected'));
assert.equal(rows().filter(row=>row.tabIndex===0).length,1);
assert.equal(source.commands.length,before); // 移动选择不读取文档。
assert.deepEqual(scrolls.at(-1)[1],{block:'nearest',inline:'nearest',behavior:'smooth'});
key(doc.activeElement,'End');assert.equal(doc.activeElement,rows().at(-1));
key(doc.activeElement,'ArrowDown');assert.equal(doc.activeElement,rows().at(-1));
reduce=true;key(doc.activeElement,'Home');key(doc.activeElement,'ArrowUp');
assert.equal(doc.activeElement,rows()[0]);assert.equal(scrolls.at(-1)[1].behavior,'auto');
assert.ok(rows().every(row=>row.closest('tr').classList.contains('c-focus-row')));
key(doc.activeElement,'Enter');await settle();
assert.equal(source.commands.filter(command=>command.cmd==='part_get').length,1);
assert.equal(rootEl.querySelector('[data-force]').textContent,'11.6 N');
assert.equal(rootEl.querySelector('.library-list-slot').hidden,false);
key(rows()[0],'ArrowDown');const selected=doc.activeElement.dataset.part;
view.render({...store.getState(),library:{...store.getState().library,parts:[...store.getState().library.parts]}});await flush();
assert.equal(doc.activeElement.dataset.part,selected);
rows()[2].closest('tr').querySelector('td').click();await settle();
assert.equal(source.commands.filter(command=>command.cmd==='part_get').at(-1).id,rows()[2].dataset.part);
await click('配方');const recipe=rootEl.querySelector('[data-recipe-doc]');recipe.focus();
key(recipe,'End');key(recipe,'ArrowDown');assert.equal(doc.activeElement,recipe);
key(recipe,'Enter');await settle();assert.ok(rootEl.querySelector('[data-part-link]'));finish();
''')


def test_detail_swap_latest_request_wins_reduced_motion_and_disposal():
    jsdom_script(SETUP + r'''
styled();const rows=[...rootEl.querySelectorAll('[data-part]')];
rows[0].click();await settle();const article=rootEl.querySelector('article');
rows[1].click();assert.ok(article.classList.contains('c-swap-out'));
assert.equal(article.querySelector('[data-force]').textContent,'11.6 N');
rows[2].click();await settle();
assert.equal(article.querySelector('h2').textContent,store.getState().library.parts[2].name);
assert.equal(source.commands.filter(c=>c.cmd==='part_get'&&c.id===rows[1].dataset.part).length,0);
// 标签切换会取消尚未显示的详情，避免旧回调发出请求。
rows[3].click();rootEl.querySelector('[data-tab="recipes"]').click();await settle();
assert.equal(article.hidden,true);assert.equal(source.commands.filter(c=>c.cmd==='part_get'&&c.id===rows[3].dataset.part).length,0);
await click('零件');rows[0].click();await settle();
win.matchMedia=()=>({matches:true});rows[1].click();await flush();
assert.equal(article.querySelector('[data-force]').textContent,'12.3 N');
win.matchMedia=()=>({matches:false});rows[3].click();const count=source.commands.length;
unsubscribe();view.dispose();tick(500);await flush();
assert.equal(rootEl.children.length,0);assert.equal(source.commands.length,count);off();source.stop();dom.window.close();
''')


def test_curve_draws_once_and_metrics_flash_only_after_value_changes():
    jsdom_script(SETUP + r'''
const {mount:record}=await import('./console/pages/parts/views/training-record.js');
const host=doc.createElement('div');rootEl.append(host);const chart=record(host);
win.matchMedia=()=>({matches:false});
const rounds=[{round:1,deviation_mm:5},{round:2,deviation_mm:2}];
chart.render({rounds,threshold_mm:1});await flush();
assert.equal(host.querySelector('polyline').getAttribute('pathLength'),'1');
assert.ok(host.querySelector('polyline').classList.contains('library-curve-draw'));
assert.equal(host.querySelectorAll('.c-flash').length,0);
const metric=host.querySelector('dd');chart.render({rounds:[...rounds,{round:3,deviation_mm:.5}],threshold_mm:1});await flush();
assert.equal(host.querySelector('dd'),metric);assert.ok(metric.classList.contains('c-flash'));
assert.equal(host.querySelectorAll('.library-curve-draw').length,0);chart.dispose();
win.matchMedia=()=>({matches:true});const reduced=record(host);reduced.render({rounds,threshold_mm:1});await flush();
assert.equal(host.querySelectorAll('.library-curve-draw').length,0);assert.ok(host.querySelector('polyline'));reduced.dispose();finish();
''')


def test_wizard_preview_swap_back_retains_draft_and_cancel_does_not_send_commands():
    jsdom_script(SETUP + r'''
styled();await click('新增零件');
const flow=rootEl.querySelector('[data-new-flow]'),preview=flow.querySelector('.c-viewport');
assert.match(preview.textContent,/等待拍照/);assert.ok(preview.querySelector('[aria-label="工作台俯视图"]'));
assert.match(flow.textContent,/轮廓完整/);assert.equal(button('上一步').getAttribute('aria-disabled'),'true');
assert.equal(button('下一步').getAttribute('aria-disabled'),'true');
await click('拍照识别');assert.equal(preview.dataset.busy,'true');
button('取消').click();assert.equal(flow.hidden,false);
source.advance(1500);await settle();assert.equal(preview.dataset.busy,'false');
input('名称','保留草稿');input('编号','P105');
button('下一步').click();assert.ok(flow.querySelector('.library-flow-content').classList.contains('c-swap-out'));
assert.equal(flow.querySelector('[aria-current]').dataset.step,'1');await settle();
assert.equal(flow.querySelector('[aria-current]').dataset.step,'2');
assert.equal(flow.querySelector('[data-step="1"]').dataset.progress,'done');
await click('上一步');assert.equal(flow.querySelector('input[aria-label="名称"]').value,'保留草稿');
assert.equal(flow.querySelector('input[aria-label="编号"]').value,'P105');
assert.equal(flow.querySelector('[data-step="1"]').dataset.progress,'current');
await click('下一步');const count=source.commands.length;await click('取消');
assert.equal(source.commands.length,count);assert.equal(flow.hidden,true);
assert.equal(doc.activeElement,button('新增零件'));assert.equal(button('查看新增流程'),undefined);finish();
''')


def test_wizard_footer_training_guards_completion_and_recipe_back_preserves_order():
    jsdom_script(SETUP + r'''
styled();await click('配方');await click('新增配方');input('名称','往返配方');
const checks=[...rootEl.querySelectorAll('input[type="checkbox"]')];
for(const checkbox of checks.slice(0,2)){checkbox.checked=true;checkbox.dispatchEvent(new win.Event('change'));}
rootEl.querySelector('[aria-label="上移空心圆柱"]').click();
await click('下一步');await click('上一步');
assert.equal(rootEl.querySelectorAll('input:checked').length,2);
await click('下一步');await click('下一步');
assert.deepEqual(source.commands.find(c=>c.cmd==='train_start').draft.steps.map(s=>s.part_id),['tube','plate']);
for(const text of ['上一步','下一步','取消']){assert.equal(button(text).getAttribute('aria-disabled'),'true');button(text).click();}
assert.equal(source.commands.filter(c=>c.cmd==='train_start').length,1);
source.advance(9600);await settle();assert.match(rootEl.querySelector('[data-new-flow]').textContent,/训练完成 · 已收录/);
assert.deepEqual([...rootEl.querySelectorAll('[data-step]')].map(el=>el.dataset.progress),['done','done','current']);
await click('下一步');assert.match(rootEl.querySelector('article').textContent,/往返配方/);finish();
''')


def test_tabs_and_css_use_one_indicator_shared_motion_and_reduced_motion_override():
    jsdom_script(SETUP + r'''
const tabs=[...rootEl.querySelectorAll('[data-tab]')];tabs[0].focus();key(tabs[0],'ArrowRight');
assert.equal(doc.activeElement,tabs[1]);assert.equal(tabs[1].getAttribute('aria-selected'),'true');
key(tabs[1],'Home');assert.equal(tabs[0].getAttribute('aria-selected'),'true');
key(tabs[0],'End');assert.equal(tabs[1].tabIndex,0);
assert.equal(rootEl.querySelectorAll('.library-tab-indicator').length,1);finish();
''')
    css = (CONSOLE / 'pages/parts/parts.css').read_text()
    assert re.findall(r'@keyframes\s+([\w-]+)', css) == ['library-curve-draw']
    assert 'stroke-dashoffset: 1' in css and 'var(--t-slow)' in css
    assert 'prefers-reduced-motion: reduce' in css and 'animation: none !important' in css
    assert '.library-flow-actions { position: sticky' in css
    assert 'translateX(calc(100% + var(--sp-3)))' in css
    assert 'library-values-a' not in css and 'library-corners-in' not in css


def test_completion_snapshot_survives_reset_during_fade_and_empty_preview_is_explicit():
    jsdom_script(SETUP + r'''
styled();await click('新增零件');await click('拍照识别');source.advance(1500);await settle();
await click('下一步');await click('开始训练');source.advance(9600);
await Promise.resolve();tick(32);
assert.ok(rootEl.querySelector('.library-flow-content').classList.contains('c-swap-out'));
await source.send('reset_demo');await settle();
assert.match(rootEl.querySelector('[data-new-flow]').textContent,/训练完成 · 已收录/);
assert.equal(rootEl.querySelector('[aria-current]').dataset.step,'3');
const {capturePreview}=await import('./console/pages/parts/views/capture-preview.js');
const empty=doc.createElement('div');empty.append(capturePreview(doc,null));
assert.equal(empty.textContent,'等待拍照');assert.equal(empty.querySelector('svg'),null);finish();
''')
