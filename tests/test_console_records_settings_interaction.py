"""记录排序与设置反馈：真实页面模块、共享 motion、Node/JSDOM 虚拟时钟。"""
from pathlib import Path
import re

from tests.test_console_shell import DOM
from tests.test_trainer_views import jsdom_script


SETUP = DOM + r'''
const {initialState}=await import('./console/state/store.js');
const {mount:mountRecords}=await import('./console/pages/records/index.js');
const {mount:mountSettings}=await import('./console/pages/settings/index.js');
let reduced=false;
win.matchMedia=()=>({matches:reduced});
const ctx={send(){throw new Error('只读页面不能发送指令');}};
const recordsRoot=doc.createElement('section'), settingsRoot=doc.createElement('section');
recordsRoot.dataset.page='records';settingsRoot.dataset.page='settings';doc.body.append(recordsRoot,settingsRoot);
const records=mountRecords(recordsRoot,ctx), settings=mountSettings(settingsRoot,ctx);tick(16);
const table=kind=>recordsRoot.querySelector(`[data-records="${kind}"]`);
const body=kind=>table(kind).querySelector('tbody');
const button=(kind,field)=>table(kind).querySelector(`[data-sort="${field}"]`);
const names=kind=>[...body(kind).rows].filter(row=>!row.querySelector('.records-empty')).map(row=>row.cells[1].textContent);
const sort=(kind,field)=>{button(kind,field).click();tick(140);};
const ended=el=>el.dispatchEvent(new win.Event('animationend'));
const state=(runs=[],trains=[])=>({...initialState(),runs,trains});
const render=s=>{records.render(s);tick(16);};
function finish(){records.dispose();settings.dispose();tick(1000);dom.window.close();}
'''


def test_record_headers_sort_raw_values_both_directions_and_keep_accessibility():
    jsdom_script(SETUP + r'''
const runs=[
  {recipe_id:'late',t:86401000,deviation_mm:1.04,duration_ms:3600000},
  {recipe_id:'early',t:86399000,deviation_mm:1.03,duration_ms:90000},
  {recipe_id:'middle',t:86400000,deviation_mm:0,duration_ms:0},
];
render(state(runs));
assert.deepEqual(names('production'),['late','middle','early']);
assert.equal(button('production','t').parentElement.getAttribute('aria-sort'),'descending');
const header=button('production','deviation_mm');header.focus();header.click();
assert.equal(header.tagName,'BUTTON');assert.equal(header.type,'button');
assert.equal(header.parentElement.scope,'col');assert.equal(header.parentElement.getAttribute('aria-sort'),'ascending');
assert.equal(button('production','t').parentElement.getAttribute('aria-sort'),'none');
assert.equal(body('production').classList.contains('c-swap-out'),true);
assert.deepEqual(names('production'),['late','middle','early']);tick(140);
assert.deepEqual(names('production'),['middle','early','late']);
assert.equal(body('production').classList.contains('c-swap-in'),true);
assert.equal(doc.activeElement,header);assert.equal(button('production','deviation_mm'),header);
sort('production','deviation_mm');assert.deepEqual(names('production'),['late','early','middle']);
sort('production','duration_ms');assert.deepEqual(names('production'),['middle','early','late']);
sort('production','duration_ms');assert.deepEqual(names('production'),['late','early','middle']);
sort('production','t');assert.deepEqual(names('production'),['early','middle','late']);
sort('production','t');assert.deepEqual(names('production'),['late','middle','early']);
assert.deepEqual(runs.map(row=>row.recipe_id),['late','early','middle']);
assert.equal(table('production').querySelectorAll('button').length,3);
assert.equal(table('training').querySelectorAll('button').length,4);
assert.equal(table('production').getAttribute('aria-labelledby'),'records-production-title');
assert.equal(recordsRoot.querySelector('[role="region"]').tabIndex,0);
finish();
''')


def test_training_sort_is_independent_and_includes_archives_and_new_records():
    jsdom_script(SETUP + r'''
let current={...state([], [
  {doc_id:'ten',t:20,round:10,deviation_mm:2,elapsed_ms:600000},
  {doc_id:'two',t:30,round:2,deviation_mm:10,elapsed_ms:120000},
]),archivedTrains:[{doc_id:'zero',t:10,round:0,deviation_mm:0,elapsed_ms:0}]};
render(current);assert.deepEqual(names('training'),['two','ten','zero']);
sort('training','round');assert.deepEqual(names('training'),['zero','two','ten']);
sort('training','round');assert.deepEqual(names('training'),['ten','two','zero']);
sort('training','deviation_mm');assert.deepEqual(names('training'),['zero','ten','two']);
sort('training','deviation_mm');assert.deepEqual(names('training'),['two','ten','zero']);
sort('training','elapsed_ms');assert.deepEqual(names('training'),['zero','two','ten']);
sort('training','elapsed_ms');assert.deepEqual(names('training'),['ten','two','zero']);
sort('training','t');assert.deepEqual(names('training'),['zero','ten','two']);
assert.equal(button('production','t').parentElement.getAttribute('aria-sort'),'descending');
current={...current,archivedTrains:[...current.archivedTrains,{doc_id:'archive',t:15,round:1,elapsed_ms:1000}]};
render(current);assert.deepEqual(names('training'),['zero','archive','ten','two']);
assert.equal(button('training','t').parentElement.getAttribute('aria-sort'),'ascending');
finish();
''')


def test_missing_numbers_remain_missing_and_equal_keys_keep_stable_order():
    jsdom_script(SETUP + r'''
const runs=[
  {recipe_id:'older-tie',t:1,deviation_mm:2,duration_ms:0},
  {recipe_id:'zero',t:2,deviation_mm:0,duration_ms:0},
  {recipe_id:'newer-tie',t:3,deviation_mm:2,duration_ms:0},
  {recipe_id:'missing',t:null,deviation_mm:null,duration_ms:null},
  {recipe_id:'invalid',t:4,deviation_mm:-1,duration_ms:Infinity},
];
render(state(runs));assert.equal(names('production')[0],'missing');
sort('production','deviation_mm');
assert.deepEqual(names('production'),['zero','newer-tie','older-tie','invalid','missing']);
sort('production','deviation_mm');
assert.deepEqual(names('production'),['newer-tie','older-tie','zero','invalid','missing']);
assert.equal(body('production').rows[3].cells[3].textContent,'—');
assert.equal(body('production').rows[4].cells[4].textContent,'—');
render(state([], [
  {doc_id:'fraction',round:1.5},{doc_id:'none',round:null},{doc_id:'zero',round:0},
]));
sort('training','round');assert.deepEqual(names('training'),['zero','none','fraction']);
sort('training','round');assert.deepEqual(names('training'),['zero','none','fraction']);
finish();
''')


def test_rapid_sort_and_live_updates_render_latest_data_and_preserve_scroll():
    jsdom_script(SETUP + r'''
const first=state([
  {recipe_id:'a',t:1,deviation_mm:1,duration_ms:90000},
  {recipe_id:'b',t:2,deviation_mm:2,duration_ms:1000},
]);render(first);
const scroll=table('production').parentElement;scroll.scrollTop=24;
button('production','deviation_mm').click();tick(40);
button('production','duration_ms').click();
render({...first,runs:[...first.runs,{recipe_id:'c',t:3,deviation_mm:0,duration_ms:0}]});
tick(84);assert.deepEqual(names('production'),['b','a']); // 旧 swap 不能提前替换。
tick(40);assert.deepEqual(names('production'),['c','b','a']);
assert.equal(scroll.scrollTop,24);
assert.equal(button('production','duration_ms').parentElement.getAttribute('aria-sort'),'ascending');
render({...first,runs:[...first.runs]}); // 新快照沿用当前排序。
assert.deepEqual(names('production'),['b','a']);
records.render({...first,runs:first.runs});tick(16);
const stable=body('production').rows[0];
records.render({...first,joints:{q:[1,2,3]}});tick(16);
assert.equal(body('production').rows[0],stable);
finish();
''')


def test_sort_timer_fallback_then_animation_end_does_not_rebuild_rows_again():
    jsdom_script(SETUP + r'''
render(state([{recipe_id:'a',t:1},{recipe_id:'b',t:2}]));
sort('production','t');
const first=body('production').rows[0];
assert.deepEqual(names('production'),['a','b']);
ended(body('production'));
assert.equal(body('production').rows[0],first);
finish();
''')


def test_reduced_motion_sorts_immediately_and_dispose_blocks_pending_render():
    jsdom_script(SETUP + r'''
render(state([{recipe_id:'a',t:1},{recipe_id:'b',t:2}]));
reduced=true;button('production','t').click();
assert.deepEqual(names('production'),['a','b']);
assert.equal(body('production').classList.contains('c-swap-out'),false);
assert.equal(body('production').classList.contains('c-swap-in'),false);
reduced=false;button('production','t').click();
const oldBody=body('production'), oldButton=button('production','t');
oldBody.replaceChildren=()=>{throw new Error('disposed table rendered');};
records.dispose();oldButton.click();tick(1000);
assert.equal(recordsRoot.childElementCount,0);
assert.equal([...doc.querySelectorAll('link')].some(el=>el.href.endsWith('/records.css')),false);
finish();
''')


def test_kpis_flash_only_changes_without_replacing_selected_value_nodes():
    jsdom_script(SETUP + r'''
const numbers=[...recordsRoot.querySelectorAll('.records-kpi-number')];
assert.equal(numbers.some(el=>el.classList.contains('c-flash')),false);
assert.match(body('production').textContent,/还没有生产记录/);
assert.match(body('production').textContent,/完成一次生产后这里会出现记录/);
const current=state([{recipe_id:'a',t:1,ok:true,deviation_mm:0.5}]);render(current);
assert.deepEqual(numbers.map(el=>el.textContent),['1','100.0','0.5','0']);
assert.deepEqual(numbers.map(el=>el.classList.contains('c-flash')),[true,true,true,false]);
assert.equal(recordsRoot.querySelector('.records-kpi-number'),numbers[0]);
numbers.forEach(ended);
render({...current,runs:[...current.runs]});
assert.equal(numbers.some(el=>el.classList.contains('c-flash')),false);
render(state());assert.deepEqual(numbers.map(el=>el.textContent),['0','—','—','0']);
assert.equal(numbers[0].classList.contains('c-flash'),true);
finish();
''')


def test_settings_connection_flashes_on_changes_and_values_stay_selectable_readonly():
    jsdom_script(SETUP + r'''
const connection=settingsRoot.querySelector('[data-setting="connection"]');
assert.equal(connection.classList.contains('c-flash'),false);
let current={...initialState(),link:{online:true}};
settings.render(current);tick(16);
assert.equal(connection.textContent,'等待握手');assert.equal(connection.classList.contains('c-flash'),true);
ended(connection);
current={...current,hello:{proto:1,sim:true,threshold_mm:2.75}};
settings.render(current);tick(16);
assert.equal(connection.textContent,'已连接');assert.equal(connection.dataset.online,'true');
assert.equal(connection.classList.contains('c-flash'),true);ended(connection);
settings.render({...current,joints:{q:[1,2,3]}});tick(16);
assert.equal(connection.classList.contains('c-flash'),false);
const threshold=settingsRoot.querySelector('[data-setting="threshold"]');
const range=doc.createRange();range.selectNodeContents(threshold);
win.getSelection().removeAllRanges();win.getSelection().addRange(range);
assert.equal(win.getSelection().toString(),'2.8 mm');
settings.render({...current,link:{online:false}});tick(16);
assert.equal(connection.textContent,'未连接');assert.equal(connection.dataset.online,'false');
assert.equal(connection.classList.contains('c-flash'),true);
assert.equal(win.getSelection().toString(),'2.8 mm');
assert.equal(settingsRoot.querySelector('[data-setting="threshold"]'),threshold);
assert.equal(settingsRoot.querySelectorAll('input,select,textarea,button,[contenteditable]').length,0);
finish();
''')


def test_record_settings_css_uses_shared_motion_tokens_and_reduced_motion_guard():
    static = Path(__file__).resolve().parents[1] / 'rearm/ui/static'
    tokens = set(re.findall(r'(--[\w-]+)\s*:', (static / 'tokens.css').read_text()))
    tokens |= {'--t-fast', '--t-base', '--t-slow', '--ease-out', '--ease-in-out'}
    for page in ('records', 'settings'):
        css = (static / f'modules/console/pages/{page}/{page}.css').read_text()
        assert '@keyframes' not in css
        assert not re.search(r'#[\da-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(', css)
        assert set(re.findall(r'var\((--[\w-]+)', css)) <= tokens
        assert '@media (prefers-reduced-motion: reduce)' in css
        assert 'animation: none !important' in css and 'transition: none !important' in css
    records_css = (static / 'modules/console/pages/records/records.css').read_text()
    settings_css = (static / 'modules/console/pages/settings/settings.css').read_text()
    assert 'position: sticky' in records_css and 'background-color var(--t-fast)' in records_css
    assert 'user-select: text' in settings_css and 'background-color var(--t-base)' in settings_css
