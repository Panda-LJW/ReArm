"""外壳交互：真实模块 + Node/JSDOM，虚拟时钟核对竞态、命令边界及清理。"""
from tests.test_console_shell import CONSOLE, DOM
from tests.test_trainer_views import jsdom_script


def test_busy_deduplicates_commands_and_restores_without_overwriting_business_state():
    jsdom_script(DOM + r'''
const {withBusy}=await import('./console/widgets/busy.js');
let immediate=false;const unbound=withBusy(null,()=>{immediate=true;return{ok:true};});
assert.equal(immediate,true);assert.deepEqual(await unbound,{ok:true});
const button=doc.createElement('button'), child=doc.createElement('span');button.append(child);doc.body.append(button);
let finish,calls=0;const operation=()=>{calls++;return new Promise(resolve=>finish=resolve);};
const first=withBusy(button,operation), second=withBusy(button,operation);
assert.equal(first,second);assert.equal(calls,1);assert.equal(button.getAttribute('aria-busy'),'true');
let clicks=0;button.addEventListener('click',()=>clicks++);child.click();assert.equal(clicks,0);
assert.equal(key(button,'Enter').defaultPrevented,true);assert.equal(key(button,' ').defaultPrevented,true);
assert.equal(key(button,'Tab').defaultPrevented,false);assert.equal(button.hasAttribute('disabled'),false);
// 回复期间业务层变更可用性，busy 完成不能恢复成旧状态。
button.setAttribute('aria-disabled','true');button.dataset.reason='连接已关闭';
finish({ok:true});assert.deepEqual(await first,{ok:true});
assert.equal(button.hasAttribute('aria-busy'),false);assert.equal(button.getAttribute('aria-disabled'),'true');
assert.equal(button.dataset.reason,'连接已关闭');child.click();assert.equal(clicks,1);
button.setAttribute('aria-busy','false');button.remove();
await assert.rejects(withBusy(button,()=>{throw new Error('同步失败');}),/同步失败/);
assert.equal(button.getAttribute('aria-busy'),'false');
await assert.rejects(withBusy(button,Promise.reject(new Error('异步失败'))),/异步失败/);
assert.equal(button.getAttribute('aria-busy'),'false');dom.window.close();
''')


def test_toast_merges_restarts_expiry_closes_and_renders_plain_text():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/shell/toast.js');const toast=mount(doc.body);
toast.show('<img src=x onerror=bad()>','busy');tick(2500);toast.show('正在执行其他操作','busy');
assert.equal(doc.querySelectorAll('.c-toast').length,1);assert.equal(doc.querySelector('img'),null);
assert.equal(doc.querySelector('.c-toast').getAttribute('role'),'status');
assert.equal(doc.querySelector('.c-toast span').textContent,'正在执行其他操作');
tick(2999);assert.equal(doc.querySelectorAll('.c-toast').length,1);tick(1);assert.equal(doc.querySelector('.c-toast'),null);
toast.show('断开','offline');toast.show('忙碌','busy');assert.equal(doc.querySelectorAll('.c-toast').length,2);
doc.querySelector('.c-toast button').click();assert.equal(doc.querySelectorAll('.c-toast').length,1);
toast.dispose();tick(3000);toast.show('销毁后');assert.equal(doc.querySelector('.console-toasts'),null);dom.window.close();
''')


def test_command_feedback_preserves_reply_exception_and_transport_arguments():
    jsdom_script(DOM + r'''
const {mount,commandFeedback}=await import('./console/shell/toast.js');const toast=mount(doc.body);
const args={id:'part'}, calls=[];let reply={ok:true};
const send=commandFeedback((...parameters)=>{calls.push(parameters);if(reply instanceof Error)throw reply;return reply;},toast);
assert.equal(await send('part_get',args),reply);assert.equal(doc.querySelector('.c-toast'),null);
reply={ok:false,code:'busy',msg:'正在执行其他操作'};
assert.equal(await send('part_get',args),reply);await send('part_get',args);
await send('recipe_get',args); // 不同页面同一错误类别合并。
assert.equal(doc.querySelectorAll('.c-toast').length,1);
reply={ok:false,code:'offline',msg:'连接已关闭'};await send('reset_demo',undefined,{errorFeedback:'dialog'});
assert.equal(doc.querySelectorAll('.c-toast').length,1);
const failure=reply=new Error('连接已关闭');await assert.rejects(send('estop'),error=>error===failure);
assert.equal(doc.querySelectorAll('.c-toast').length,2);
await assert.rejects(send('reset_estop',undefined,{errorFeedback:'dialog'}),error=>error===failure);
assert.equal(doc.querySelectorAll('.c-toast').length,2);
assert.ok(calls.every(call=>call.length===2));assert.equal(calls[0][1],args);
toast.dispose();dom.window.close();
''')


ROUTES = r'''
const {mount}=await import('./console/shell/router.js');
const {mount:mountNav}=await import('./console/shell/nav.js');
const rootPages=doc.querySelector('[data-pages]'), nav=doc.createElement('nav');doc.body.append(nav);
const navigation=mountNav(nav);
for(const id of ['production','parts','records','settings']) {
  const section=doc.createElement('section');section.dataset.page=id;section.hidden=true;section.className='console-page';
  const card=doc.createElement('div');card.className='c-card';section.append(card);rootPages.append(section);
}
const page=id=>rootPages.querySelector(`[data-page="${id}"]`);
const go=id=>{win.history.replaceState(null,'',`#${id}`);router.render();};
'''


def test_route_fallback_crossfades_for_160ms_and_handles_rapid_revisit_and_dispose():
    jsdom_script(DOM + ROUTES + r'''
win.matchMedia=()=>({matches:false});const router=mount(rootPages,{onRoute:id=>navigation.render(id)});
go('parts');assert.equal(page('parts').hidden,false);assert.equal(page('production').hidden,true);
assert.ok(page('production').hasAttribute('inert'));assert.ok(page('production').classList.contains('c-swap-out'));
assert.ok(page('parts').classList.contains('c-swap-in'));tick(80);
assert.ok(page('production').classList.contains('c-swap-out'));tick(80);
assert.equal(rootPages.querySelector('.c-swap-out,.c-swap-in'),null);assert.equal(page('production').hasAttribute('inert'),false);
go('records');tick(80);go('parts');tick(80);
assert.equal(page('parts').hidden,false);assert.equal(page('parts').hasAttribute('inert'),false);
assert.equal(page('records').hasAttribute('inert'),true);tick(80);
assert.equal(rootPages.querySelector('.c-swap-out,.c-swap-in'),null);
go('settings');router.dispose();tick(320);assert.equal(rootPages.querySelector('[inert]'),null);
assert.equal(rootPages.querySelector('.c-swap-out,.c-swap-in'),null);navigation.dispose();dom.window.close();
''')


def test_route_native_transition_ignores_stale_callbacks_and_falls_back_on_capture_error():
    jsdom_script(DOM + ROUTES + r'''
const captures=[];let skipped=0;
doc.startViewTransition=update=>{captures.push(update);return{ready:Promise.resolve(),updateCallbackDone:Promise.resolve(),skipTransition(){skipped++;}};};
const router=mount(rootPages);go('parts');go('records');assert.equal(captures.length,2);
captures[0]();assert.equal(page('parts').hidden,true);captures[1]();assert.equal(page('records').hidden,false);
assert.equal(skipped,1);go('settings');router.dispose();captures[2]();assert.equal(page('records').hidden,false);
win.history.replaceState(null,'','#records');
doc.startViewTransition=()=>{throw new Error('capture unavailable');};
const restored=mount(rootPages);win.history.replaceState(null,'','#production');restored.render();
assert.equal(page('production').hidden,false);restored.dispose();navigation.dispose();dom.window.close();
''')


def test_alt_shortcuts_use_hash_and_focus_navigation_without_emergency_shortcut():
    jsdom_script(DOM + ROUTES + r'''
win.matchMedia=()=>({matches:true});doc.startViewTransition=()=>{throw new Error('reduced motion must skip capture');};
let commands=0;const stop=doc.createElement('button');stop.dataset.action='estop';stop.addEventListener('click',()=>commands++);doc.body.append(stop);
const router=mount(rootPages,{onRoute:id=>navigation.render(id)});
for(const [index,id] of ['production','parts','records','settings'].entries()) {
  const event=new win.KeyboardEvent('keydown',{key:String(index+1),altKey:true,bubbles:true,cancelable:true});
  doc.dispatchEvent(event);assert.equal(event.defaultPrevented,true);assert.equal(win.location.hash,`#${id}`);
  win.dispatchEvent(new win.HashChangeEvent('hashchange'));tick(16);
  assert.equal(page(id).hidden,false);assert.equal(doc.activeElement.dataset.nav,id);
  assert.equal(rootPages.querySelector('.c-swap-out,.c-swap-in'),null);
}
// macOS Option 数字可能改变 key，code 仍是 Digit1。
doc.dispatchEvent(new win.KeyboardEvent('keydown',{key:'¡',code:'Digit1',altKey:true,bubbles:true}));
assert.equal(win.location.hash,'#production');
for(const modifiers of [{},{altKey:true,ctrlKey:true},{altKey:true,metaKey:true},{altKey:true,shiftKey:true},{altKey:true,repeat:true}]) {
  doc.dispatchEvent(new win.KeyboardEvent('keydown',{key:'2',bubbles:true,...modifiers}));assert.equal(win.location.hash,'#production');
}
key(doc,'Escape');key(doc,'e');assert.equal(commands,0);
router.dispose();doc.dispatchEvent(new win.KeyboardEvent('keydown',{key:'4',altKey:true,bubbles:true}));
assert.equal(win.location.hash,'#production');navigation.dispose();dom.window.close();
''')


def test_inline_banner_reset_reuses_demo_sequence_busy_guard_and_stays_in_topbar():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/shell/topbar.js');
const {createReset}=await import('./console/shell/reset.js');
const {mount:mountDialog}=await import('./console/shell/dialog.js');
let state={phase:'estop',hello:{proto:1,sim:true},link:{online:true}}, finish;
const sent=[],ctx={store:{getState:()=>state},send:cmd=>{sent.push(cmd);return cmd==='reset_demo'?new Promise(resolve=>finish=resolve):Promise.resolve({ok:true});}};
ctx.dialog=mountDialog(doc.body);ctx.reset=createReset(ctx);
const header=doc.querySelector('[data-topbar]');
const topbar=mount(header,ctx);topbar.render(state);tick(32);
const banner=header.querySelector('.console-estop-banner'), release=banner.querySelector('[data-action="reset-estop"]');
const slot=header.querySelector('.console-spacer');
assert.equal(banner.parentElement,slot);assert.equal(slot.nextElementSibling.dataset.action,'reset');
assert.equal(header.nextElementSibling,doc.querySelector('[data-pages]'));
assert.equal(banner.hidden,false);assert.equal(banner.getAttribute('role'),'alert');
assert.equal(header.hasAttribute('data-estop'),true);
release.click();release.click();header.querySelector('[data-action="reset"]').click();
assert.deepEqual(sent,['reset_demo']);assert.equal(release.getAttribute('aria-busy'),'true');assert.equal(doc.querySelector('dialog').open,false);
finish({ok:true});for(let n=0;n<10;n++)await Promise.resolve();
assert.deepEqual(sent,['reset_demo','reset_estop']);assert.equal(release.hasAttribute('aria-busy'),false);
state={...state,link:{online:false}};topbar.render(state);tick(32);release.click();assert.equal(sent.length,2);
assert.equal(release.getAttribute('aria-disabled'),'true');topbar.dispose();ctx.dialog.dispose();dom.window.close();
''')


def test_real_reset_keeps_confirmation_and_failed_reset_uses_dialog_without_toast():
    jsdom_script(DOM + r'''
const {createReset}=await import('./console/shell/reset.js');
const {mount:mountDialog}=await import('./console/shell/dialog.js');
const {mount:mountToast,commandFeedback}=await import('./console/shell/toast.js');
const {mount:mountTopbar}=await import('./console/shell/topbar.js');
const toast=mountToast(doc.body);
const sent=[],ctx={store:{getState:()=>({phase:'estop',hello:{proto:1,sim:false},link:{online:true}})}};
ctx.dialog=mountDialog(doc.body);ctx.send=commandFeedback(async cmd=>{sent.push(cmd);return{ok:false,msg:'原流程尚未退出'};},toast);
ctx.reset=createReset(ctx);
const topbar=mountTopbar(doc.querySelector('[data-topbar]'),ctx);topbar.render(ctx.store.getState());tick(32);
const trigger=doc.querySelector('.console-estop-banner [data-action="reset-estop"]');trigger.focus();trigger.click();
assert.equal(sent.length,0);assert.match(doc.querySelector('dialog').textContent,/确认解除急停/);
doc.querySelector('[data-action="confirm"]').click();for(let n=0;n<15;n++)await Promise.resolve();
assert.deepEqual(sent,['reset_estop']);assert.equal(doc.querySelector('dialog').open,true);
assert.match(doc.querySelector('dialog').textContent,/重置未完成.*原流程尚未退出/);assert.equal(doc.querySelector('.c-toast'),null);
assert.equal(trigger.hasAttribute('aria-busy'),false);ctx.dialog.close();assert.equal(doc.activeElement,trigger);
topbar.dispose();ctx.dialog.dispose();toast.dispose();dom.window.close();
''')


def test_dialog_initial_focus_skips_unavailable_controls_and_preserves_replacement_dialog():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/shell/dialog.js');
const trigger=doc.createElement('button');doc.body.append(trigger);trigger.focus();const dialog=mount(doc.body);
const content=doc.createElement('div'), unavailable=doc.createElement('button'), hidden=doc.createElement('input'), check=doc.createElement('input');
unavailable.setAttribute('aria-disabled','true');hidden.type='hidden';check.type='checkbox';
content.append(unavailable,hidden,check);dialog.open({title:'开始生产',content});
assert.equal(doc.activeElement,check);dialog.close();assert.equal(doc.activeElement,trigger);
dialog.open({onConfirm(){dialog.open({title:'后续反馈',content:'请求未完成'});}});
doc.querySelector('[data-action="confirm"]').click();assert.equal(doc.querySelector('dialog').open,true);
assert.equal(doc.querySelector('dialog h2').textContent,'后续反馈');dialog.close();assert.equal(doc.activeElement,trigger);
dialog.dispose();dom.window.close();
''')


def test_shared_css_contract_includes_motion_focus_progress_and_overlay_rules():
    css = (CONSOLE / 'console.css').read_text()
    for name in ['c-enter', 'c-flash', 'c-swap-out', 'c-swap-in', 'c-pulse',
                 'c-viewport', 'c-focus-row', 'c-toast', 'c-progress']:
        assert f'.{name}' in css
    assert '.console-page[hidden].c-swap-out' in css
    assert '::view-transition-new(console-content)' in css
    assert 'prefers-reduced-motion: reduce' in css
    assert '::view-transition-group(*)' in css
    banner = css.split('.console-estop-banner {', 1)[1].split('}', 1)[0]
    assert 'position:' not in banner and 'z-index:' not in banner
    assert 'color: var(--bad)' in banner and 'font-weight: 600' in banner
    assert 'animation: c-estop-enter var(--t-base)' in banner
    assert '@keyframes c-estop-enter { from { opacity: 0; } to { opacity: 1; } }' in css
    assert '.console-topbar[data-estop] { background: var(--bad-bg); border-bottom-color: var(--bad); }' in css
    assert 'transition: background-color var(--t-base)' in css
    assert '.console-topbar[data-estop] .console-spacer { display: flex; grid-row: 3; grid-column: 1 / -1;' in css
    assert 'animation: c-pulse 1s' in css
    assert ':focus-visible { outline: var(--line-w) solid var(--text)' in css
