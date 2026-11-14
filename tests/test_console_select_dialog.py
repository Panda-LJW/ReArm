"""自绘 select 与紧凑确认框：真实视图、原生数据源及命令边界。"""
import pytest

from tests.test_console_shell import DOM, CONSOLE
from tests.test_console_production import SETUP
from tests.test_trainer_views import jsdom_script


SELECT = DOM + r'''
const {enhanceSelect}=await import('./console/widgets/select.js');
const select=doc.createElement('select');select.setAttribute('aria-label','工装');
for(const [value,label] of [['a','Alpha'],['b','Beta'],['c','Charlie']]) {
  const option=doc.createElement('option');option.value=value;option.textContent=label;select.append(option);
}
doc.body.append(select);let changes=0;
select.addEventListener('change',()=>changes++);
const view=enhanceSelect(select,{meta:option=>option.value==='a'?'2 步':''});
const trigger=doc.querySelector('[role="combobox"]');
const list=()=>doc.getElementById(trigger.getAttribute('aria-controls'));
const active=()=>doc.getElementById(trigger.getAttribute('aria-activedescendant'));
function finish(){view.dispose();dom.window.close();}
'''


@pytest.mark.parametrize('opening', ['Enter', ' ', 'ArrowDown'])
def test_select_keyboard_commits_native_value_and_bubbling_change(opening):
    jsdom_script(SELECT + f'const opening={opening!r};' + r'''
let bubbled=0;doc.body.addEventListener('change',()=>bubbled++);
assert.equal(select.getAttribute('aria-hidden'),'true');assert.equal(select.tabIndex,-1);
trigger.focus();key(trigger,opening);assert.equal(trigger.getAttribute('aria-expanded'),'true');
assert.equal(list().getAttribute('role'),'listbox');assert.equal(active().textContent,'Alpha2 步✓');
key(trigger,'ArrowDown');assert.equal(active().getAttribute('aria-selected'),'false');
assert.equal(select.value,'a');key(trigger,'Enter');
assert.equal(select.value,'b');assert.equal(changes,1);assert.equal(bubbled,1);
assert.equal(trigger.getAttribute('aria-expanded'),'false');assert.equal(doc.activeElement,trigger);
assert.equal(trigger.querySelector('.c-select-name').textContent,'Beta');
assert.equal(trigger.querySelector('.c-select-meta').hidden,true);finish();
''')


def test_select_mouse_and_typeahead_skip_disabled_options_and_restore_focus():
    jsdom_script(SELECT + r'''
select.options[1].disabled=true;view.render();trigger.focus();trigger.click();
key(trigger,'End');assert.match(active().textContent,/Charlie/);
key(trigger,'Home');assert.match(active().textContent,/Alpha/);
key(trigger,'ArrowDown');assert.match(active().textContent,/Charlie/);
key(trigger,'ArrowUp');assert.match(active().textContent,/Alpha/);
key(trigger,'c');assert.match(active().textContent,/Charlie/);
key(trigger,'Escape');assert.equal(trigger.getAttribute('aria-expanded'),'false');
assert.equal(doc.activeElement,trigger);assert.equal(select.value,'a');assert.equal(changes,0);
trigger.click();list().querySelectorAll('[role="option"]')[1].click();assert.equal(select.value,'a');
list().querySelectorAll('[role="option"]')[2].click();assert.equal(select.value,'c');assert.equal(changes,1);
trigger.click();assert.equal(key(trigger,'Tab').defaultPrevented,false);
assert.equal(trigger.getAttribute('aria-expanded'),'false');trigger.click();
doc.body.dispatchEvent(new win.Event('pointerdown',{bubbles:true}));
assert.equal(trigger.getAttribute('aria-expanded'),'false');finish();
''')


def test_select_mutations_render_sync_native_guard_and_dispose():
    jsdom_script(SELECT + r'''
select.value='c';view.render();assert.equal(trigger.querySelector('.c-select-name').textContent,'Charlie');
select.options[2].textContent='New Charlie';await Promise.resolve();
assert.equal(trigger.querySelector('.c-select-name').textContent,'New Charlie');
const option=doc.createElement('option');option.value='d';option.textContent='Delta';
select.replaceChildren(option);await Promise.resolve();assert.equal(trigger.querySelector('.c-select-name').textContent,'Delta');
let guards=0;const guard=event=>{guards++;event.preventDefault();};
select.addEventListener('mousedown',guard);trigger.click();assert.equal(guards,1);
assert.equal(trigger.getAttribute('aria-expanded'),'false');select.removeEventListener('mousedown',guard);
select.addEventListener('keydown',guard);key(trigger,'Enter');assert.equal(guards,2);
assert.equal(trigger.getAttribute('aria-expanded'),'false');select.removeEventListener('keydown',guard);
trigger.click();assert.equal(trigger.getAttribute('aria-expanded'),'true');view.dispose();
assert.equal(doc.querySelector('.c-select-list'),null);assert.equal(select.getAttribute('aria-hidden'),null);
assert.equal(select.getAttribute('tabindex'),null);assert.equal(doc.querySelector('[role="combobox"]'),null);
assert.equal(doc.body.contains(select),true);dom.window.close();
''')


def test_select_tracks_external_selection_while_open_and_closes_on_disable():
    jsdom_script(SELECT + r'''
trigger.click();key(trigger,'ArrowDown');assert.match(active().textContent,/Beta/);
select.value='c';view.render();assert.match(active().textContent,/Charlie/);
assert.equal(active().getAttribute('aria-selected'),'true');assert.equal(changes,0);
select.setAttribute('aria-disabled','true');await Promise.resolve();
assert.equal(trigger.getAttribute('aria-expanded'),'false');assert.equal(trigger.hasAttribute('aria-activedescendant'),false);
select.setAttribute('aria-disabled','false');await Promise.resolve();
select.addEventListener('mousedown',event=>event.preventDefault());
const down=new win.MouseEvent('mousedown',{bubbles:true,cancelable:true});trigger.dispatchEvent(down);
assert.equal(down.defaultPrevented,true);trigger.click();assert.equal(trigger.getAttribute('aria-expanded'),'false');finish();
''')


@pytest.mark.parametrize('native_disabled', [False, True])
def test_select_disabled_cannot_expand_and_keeps_existing_reason_tooltip(native_disabled):
    jsdom_script(SELECT + f'const nativeDisabled={str(native_disabled).lower()};' + r'''
const {mount:mountTips}=await import('./console/shell/tooltip.js');const tips=mountTips(doc);
select.dataset.reason='运行中不能切换配方';
if(nativeDisabled)select.disabled=true;else select.setAttribute('aria-disabled','true');
await Promise.resolve();assert.equal(trigger.getAttribute('aria-disabled'),'true');
trigger.click();key(trigger,'ArrowDown');assert.equal(trigger.getAttribute('aria-expanded'),'false');
pointer(trigger,'pointerenter');tick(850);assert.equal(doc.querySelector('[data-tip]').hidden,false);
assert.equal(doc.querySelector('[data-tip]').textContent,'运行中不能切换配方');
assert.equal(changes,0);tips.dispose();finish();
''')


def test_select_flips_up_closes_when_hidden_and_cleans_detached_popup():
    jsdom_script(SELECT + r'''
trigger.getBoundingClientRect=()=>({left:40,top:740,bottom:772,width:240});
Object.defineProperty(win,'innerHeight',{value:800});
Object.defineProperty(list(),'scrollHeight',{value:108});
trigger.click();assert.equal(list().dataset.side,'up');assert.equal(list().style.width,'240px');
assert.equal(list().style.bottom,'64px');
const wrapper=trigger.parentElement;wrapper.hidden=true;await Promise.resolve();
assert.equal(trigger.getAttribute('aria-expanded'),'false');wrapper.hidden=false;trigger.click();
wrapper.remove();await Promise.resolve();assert.equal(trigger.getAttribute('aria-expanded'),'false');
assert.equal(doc.querySelector('.c-select-list'),null);finish();
''')


def test_start_dialog_shows_recipe_safety_reason_and_sends_only_after_check():
    jsdom_script(SETUP + r'''
const start=$('[data-action="start"]');start.click();
const panel=$('dialog'),check=$('[data-confirm-check]'),confirm=$('[data-action="confirm"]');
assert.equal(panel.querySelector('.console-dialog-safety').textContent,'安全确认');
assert.equal(panel.querySelector('.c-confirm-name').textContent,'薄片 + 空心圆柱配套件');
assert.equal(panel.querySelector('.c-confirm-meta').textContent,'2 个零件 · 2 步');
assert.equal(confirm.textContent,'开始生产');assert.equal(confirm.getAttribute('aria-disabled'),'true');
assert.equal(panel.querySelector('.console-dialog-reason').textContent,'请先确认工作区附近无人');
assert.equal(doc.activeElement,check);confirm.click();key(check,'Enter');await flush();
assert.equal(source.commands.filter(c=>c.cmd==='run_start').length,0);
check.click();assert.equal(confirm.getAttribute('aria-disabled'),'false');
assert.equal(panel.querySelector('.console-dialog-reason').hidden,true);key(check,'Enter');await flush();
assert.equal(source.commands.filter(c=>c.cmd==='run_start').length,1);
assert.equal(source.commands.find(c=>c.cmd==='run_start').recipe_id,'plate-tube');
assert.equal(panel.open,false);assert.equal(doc.activeElement,start);cleanup();
''')


def test_production_select_rechecks_running_state_before_render_and_shows_reason():
    jsdom_script(SETUP + r'''
const trigger=pageRoot.querySelector('[role="combobox"]');trigger.focus();trigger.click();
assert.equal(trigger.getAttribute('aria-expanded'),'true');key(trigger,'Escape');
assert.equal(doc.activeElement,trigger);
await ctx.send('run_start',{recipe_id:'plate-tube'}); // 尚未刷新视图，也必须拦截。
trigger.click();assert.equal(trigger.getAttribute('aria-expanded'),'false');
assert.equal(trigger.getAttribute('aria-disabled'),'true');assert.match(trigger.dataset.reason,/正在生产/);
cleanup();
''')


def test_dialog_without_safety_tag_and_missing_metadata_does_not_invent_counts():
    jsdom_script(DOM + r'''
const {mount:mountDialog}=await import('./console/shell/dialog.js');
const {mount:mountRecipe}=await import('./console/pages/production/views/recipe-pick.js');
const {initialState}=await import('./console/state/store.js');
const rootEl=doc.createElement('div');doc.body.append(rootEl);const dialog=mountDialog(doc.body);
const state={...initialState(),link:{online:true},hello:{proto:1,sim:true},library:{parts:[],recipes:[{id:'x',name:'仅有名称'}]}};
const ctx={store:{getState:()=>state},selection:{id:'x'},dialog,send:()=>({ok:true})};
const view=mountRecipe(rootEl,ctx);view.render(state);tick(16);rootEl.querySelector('[data-action="start"]').click();
assert.equal(doc.querySelector('.c-confirm-name').textContent,'仅有名称');assert.equal(doc.querySelector('.c-confirm-meta'),null);
assert.ok(doc.querySelector('.console-dialog-safety'));key(doc.querySelector('[data-confirm-check]'),'Escape');
assert.equal(doc.querySelector('dialog').open,false);
dialog.open({title:'重置未完成',content:'请检查连接'});
assert.equal(doc.querySelector('.console-dialog-safety'),null);assert.doesNotMatch(doc.querySelector('dialog').textContent,/安全确认/);
assert.equal(doc.querySelector('.console-dialog-content').textContent,'请检查连接');
assert.equal(doc.querySelector('[data-action="confirm"]').textContent,'确认');
view.dispose();dialog.dispose();dom.window.close();
''')


def test_recipe_fields_uses_enhanced_fixture_select_and_keeps_draft_source():
    jsdom_script(DOM + r'''
const {recipeFields}=await import('./console/pages/parts/views/recipe-fields.js');
const rootEl=doc.createElement('div');doc.body.append(rootEl);let changed=0;
const fields=recipeFields(rootEl,{workspace:{props:[{id:'f1',name:'工装一',kind:'fixture'},
  {id:'f2',name:'工装二',kind:'fixture'},{id:'p',name:'定位柱',kind:'post'}]},library:{parts:[]}},()=>changed++);
const trigger=rootEl.querySelector('[role="combobox"]');key(trigger,'Enter');key(trigger,'End');key(trigger,'Enter');
assert.equal(rootEl.querySelector('select').value,'f2');assert.equal(fields.draft().fixture_id,'f2');assert.equal(changed,1);
rootEl.querySelector('select').value='f1';fields.reason();assert.equal(trigger.querySelector('.c-select-name').textContent,'工装一');
rootEl.remove();await Promise.resolve();assert.equal(doc.querySelector('.c-select-list'),null);dom.window.close();
''')


def test_controls_styles_use_monochrome_focus_and_reduced_motion():
    css = (CONSOLE / 'console.css').read_text()
    assert 'var(--focus)' not in css
    assert 'width: min(440px,' in css
    assert '.c-confirm-check:has(:focus-visible)' in css
    assert '.c-focus-row :focus-visible { outline: none' in css
    assert 'stroke-dashoffset: 0' in css
    assert 'prefers-reduced-motion: reduce' in css
