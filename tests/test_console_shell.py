"""T1：真实 ASGI 路由、外壳边界和 JSDOM 交互；不启动服务或浏览器。"""
from pathlib import Path
import re

import pytest

from rearm.app import build_app
from rearm.ui.server import create_server
from tests.test_ui_architecture import request
from tests.test_trainer_views import jsdom_script

STATIC = Path(__file__).resolve().parents[1] / 'rearm/ui/static'
CONSOLE = STATIC / 'modules/console'


@pytest.mark.parametrize('url,filename', [
    ('/', 'console.html'), ('/?legacy=1', 'index.html'),
    ('/?legacy=0', 'console.html'), ('/?legacy=true', 'console.html'),
    ('/?legacy=1&mode=show', 'index.html'),
])
def test_home_route_returns_exact_shell(config, tmp_path, url, filename):
    controller = build_app(config, tmp_path)
    app = create_server(controller, controller.bus, controller.snapshot())
    status, body = request(app, url)
    assert status == 200
    assert body == (STATIC / filename).read_bytes()


def test_console_assets_and_thin_entry(config, tmp_path):
    controller = build_app(config, tmp_path)
    app = create_server(controller, controller.bus, controller.snapshot())
    html = (STATIC / 'console.html').read_text()
    assert '/static/tokens.css' in html and '/static/modules/console/main.js' in html
    assert 'app.js' not in html and 'app.css' not in html and 'modules/main.js' not in html
    assert '<style>' not in html and '<script>' not in html
    for path in [*CONSOLE.rglob('*.js'), *CONSOLE.rglob('*.css'), STATIC / 'brand/rearm-wordmark.svg']:
        status, body = request(app, '/static/' + path.relative_to(STATIC).as_posix())
        assert status == 200 and body == path.read_bytes()


def test_console_has_no_transport_legacy_imports_or_cross_page_dependencies():
    for path in CONSOLE.rglob('*.js'):
        source = path.read_text()
        assert not re.search(r'\bfetch\s*\(|\bWebSocket\b|laser', source), path
        if path != CONSOLE / 'main.js':
            assert '__rearmMock' not in source, path
        else:
            assert source.count('__rearmMock') == 1
            assert 'window.__rearmMock = { commands: source.commands };' in source
        assert not re.search(r'\.innerHTML\s*[+]?=', source), path
        assert '/api/' not in source and 'URLSearchParams' not in source
        assert not re.search(r'\.get\(["\x27]backend["\x27]\)', source), path
        assert not re.search(r'\bdisabled\s*=|setAttribute\(["\x27]disabled', source), path
        assert len(source.splitlines()) <= 200, path
        for spec in re.findall(r'(?:from\s*|import\s*\()["\x27]([^"\x27]+)', source):
            target = (path.parent / spec).resolve()
            # T4 使用 T3 的公开孪生入口；工位常量仅进入纯状态层，视图仍不读取数据源。
            public_imports = {
                CONSOLE / 'main.js': {STATIC / 'modules/datasource/mock-console.js', STATIC / 'modules/twin/twin.js'},
                CONSOLE / 'state/workspace.js': {STATIC / 'modules/datasource/fixtures/workspace.js'},
            }
            assert target.is_relative_to(CONSOLE) or target in public_imports.get(path, set()), (path, spec)
            if path.is_relative_to(CONSOLE / 'pages') and target.is_relative_to(CONSOLE / 'pages'):
                assert target.relative_to(CONSOLE / 'pages').parts[0] == path.relative_to(CONSOLE / 'pages').parts[0]
    css = (CONSOLE / 'console.css').read_text()
    # 视觉规范允许同色线性角标、三种固定透明底/阴影；其他颜色仍只能取 tokens。
    assert not re.search(r'#[\da-fA-F]{3,8}\b|\b(?:rgb|hsl|hsla)\(', css)
    assert set(re.findall(r'rgba\([^)]*\)', css)) <= {
        'rgba(6,8,10,.86)', 'rgba(0,0,0,.6)', 'rgba(0,0,0,.72)',
    }
    tokens = set(re.findall(r'(--[\w-]+)\s*:', (STATIC / 'tokens.css').read_text()))
    # 动效规范的局部时间/曲线与错峰序号不属于颜色 token。
    motion_tokens = {'--t-fast', '--t-base', '--t-slow', '--ease-out', '--ease-in-out', '--enter-i', '--i'}
    assert set(re.findall(r'var\((--[\w-]+)', css)) <= tokens | motion_tokens
    assert 'cursor: help' in css and 'var(--estop)' in css


DOM = r'''
import assert from 'node:assert/strict';
import fs from 'node:fs';
const dom = new JSDOM(fs.readFileSync(root+'/rearm/ui/static/console.html','utf8'),
  {url:'http://localhost/?keep=1', pretendToBeVisual:true});
const win=dom.window, doc=win.document;
globalThis.window=win; globalThis.document=doc;
let now=0, serial=0; const timers=new Map();
win.setTimeout=(fn,ms=0)=>{const id=++serial;timers.set(id,{at:now+ms,fn});return id;};
win.clearTimeout=id=>timers.delete(id);
win.requestAnimationFrame=fn=>win.setTimeout(()=>fn(now),16);
win.cancelAnimationFrame=win.clearTimeout;
function tick(ms) {
  const end=now+ms;
  while(true) {
    const next=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];
    if(!next) break;
    timers.delete(next[0]);now=next[1].at;next[1].fn();
  }
  now=end;
}
function pointer(el,type) {el.dispatchEvent(new win.Event(type,{bubbles:false}));}
function key(el,key,shiftKey=false,type='keydown') {
  const event=new win.KeyboardEvent(type,{key,shiftKey,bubbles:true,cancelable:true});
  el.dispatchEvent(event);return event;
}
// JSDOM 没有原生对话框的顶层实现；这里只补 open/close，焦点和按键交给实际模块。
win.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
win.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};
'''


def test_navigation_content_deep_link_and_history_are_independent():
    jsdom_script(DOM + r'''
const {mount:mountNav,PAGES}=await import('./console/shell/nav.js');
const {mount:mountRouter}=await import('./console/shell/router.js');
const nav=doc.createElement('nav');doc.body.append(nav);
const view=mountNav(nav), pagesRoot=doc.querySelector('[data-pages]'), views=[];
for(const {id} of PAGES) {
  const section=doc.createElement('section');section.dataset.page=id;pagesRoot.append(section);
  const {mount}=await import(`./console/pages/${id}/index.js`);
  const page=mount(section,{});page.render();views.push(page);
}
const router=mountRouter(pagesRoot,{onRoute:page=>view.render(page)});tick(16);
assert.equal(win.location.hash,'#production');assert.equal(win.location.search,'?keep=1');
assert.deepEqual([...nav.querySelectorAll('[data-nav]')].map(el=>el.textContent),['生产','零件库','记录','设置']);
for(const {id} of PAGES) {
  win.history.pushState(null,'',`#${id}`);win.dispatchEvent(new win.HashChangeEvent('hashchange'));tick(16);
  const visible=[...pagesRoot.children].filter(el=>!el.hidden);
  assert.equal(visible.length,1);assert.equal(visible[0].dataset.page,id);assert.ok(visible[0].textContent.trim());
  assert.equal(nav.querySelector('[aria-current="page"]').dataset.nav,id);
}
win.history.replaceState(null,'','#records');router.dispose();
const restored=mountRouter(pagesRoot,{onRoute:page=>view.render(page)});tick(16);
assert.equal(pagesRoot.querySelector('[data-page="records"]').hidden,false);
win.history.replaceState(null,'','#unknown');win.dispatchEvent(new win.HashChangeEvent('hashchange'));tick(16);
assert.equal(win.location.hash,'#production');
restored.dispose();view.dispose();views.forEach(v=>v.dispose());dom.window.close();
''')


def test_tooltips_delay_block_activation_and_clear_on_leave_enable_and_dispose():
    jsdom_script(DOM + r'''
const {mount,setUnavailable}=await import('./console/shell/tooltip.js');
const control=doc.createElement('button'), child=doc.createElement('span');
child.textContent='测试动作';control.append(child);doc.body.append(control);
control.setAttribute('aria-describedby','existing-description');
setUnavailable(control,'请先选择对象');const view=mount(doc), tip=doc.querySelector('[data-tip]');
let clicks=0,keys=0;control.addEventListener('click',()=>clicks++);control.addEventListener('keydown',()=>keys++);
child.click();for(const name of ['Enter',' ']) {
  assert.equal(key(child,name).defaultPrevented,true);assert.equal(key(child,name,false,'keyup').defaultPrevented,true);
}
assert.equal(clicks,0);assert.equal(keys,0);assert.equal(control.hasAttribute('disabled'),false);
pointer(control,'pointerenter');tick(799);assert.equal(tip.hidden,true);
tick(50);assert.equal(tip.hidden,true);tick(1);assert.equal(tip.hidden,false);
tick(350);assert.equal(tip.textContent,'请先选择对象');
assert.equal(doc.querySelectorAll('[role="tooltip"][data-tip]').length,1);
pointer(control,'pointerleave');assert.equal(tip.hidden,true);
assert.equal(control.getAttribute('aria-describedby'),'existing-description');
control.focus();tick(850);assert.equal(tip.hidden,false);control.blur();assert.equal(tip.hidden,true);
pointer(control,'pointerenter');tick(400);setUnavailable(control,'');await Promise.resolve();tick(800);
assert.equal(tip.hidden,true);control.click();assert.equal(clicks,1);
setUnavailable(control,'请先选择对象');pointer(control,'pointerenter');tick(850);
control.remove();await Promise.resolve();assert.equal(tip.hidden,true);
view.dispose();tick(2000);assert.equal(doc.querySelector('[data-tip]'),null);dom.window.close();
''')


def test_dialog_traps_focus_cancels_restores_and_uses_shared_disabled_guard():
    jsdom_script(DOM + r'''
const {mount:tips}=await import('./console/shell/tooltip.js');
const {mount:dialogs}=await import('./console/shell/dialog.js');
const trigger=doc.createElement('button');trigger.textContent='打开';doc.body.append(trigger);trigger.focus();
const tooltip=tips(doc), dialog=dialogs(doc.body);let confirmed=0,canceled=0;
dialog.open({title:'确认操作',content:'<img src=x onerror="bad()">',confirmEnabled:false,
  reason:'请先确认条件',onConfirm:()=>confirmed++,onCancel:()=>canceled++});
const panel=doc.querySelector('dialog'), confirm=panel.querySelector('[data-action="confirm"]');
const cancel=panel.querySelector('button');
assert.equal(panel.open,true);assert.equal(panel.querySelector('img'),null);
assert.equal(panel.querySelector('.console-dialog-content').textContent,'<img src=x onerror="bad()">');
assert.equal(doc.activeElement,cancel);key(cancel,'Tab',true);assert.equal(doc.activeElement,confirm);
key(confirm,'Tab');assert.equal(doc.activeElement,cancel);trigger.focus();assert.equal(doc.activeElement,cancel);
confirm.click();key(confirm,'Enter');key(confirm,' ');assert.equal(confirmed,0);assert.equal(panel.open,true);
pointer(confirm,'pointerenter');tick(850);const tip=doc.querySelector('[data-tip]');
assert.equal(tip.hidden,false);assert.equal(tip.closest('dialog'),panel);
key(cancel,'Escape');await Promise.resolve();assert.equal(tip.hidden,true);
assert.equal(canceled,1);assert.equal(panel.open,false);assert.equal(doc.activeElement,trigger);
dialog.open({title:'再次确认',content:'确认工作区附近无人',confirmEnabled:false,onConfirm:()=>confirmed++});
dialog.setConfirmEnabled(true);confirm.click();assert.equal(confirmed,1);assert.equal(panel.open,false);
dialog.open({title:'取消',onCancel:()=>canceled++});panel.dispatchEvent(new win.Event('cancel',{cancelable:true}));
assert.equal(canceled,2);assert.equal(panel.open,false);
dialog.dispose();tooltip.dispose();assert.equal(doc.querySelector('dialog'),null);dom.window.close();
''')


def test_topbar_keeps_estop_last_and_only_sends_on_explicit_enabled_click():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/shell/topbar.js');
const {mount:tips}=await import('./console/shell/tooltip.js');
const commands=[], tooltip=tips(doc), header=doc.querySelector('[data-topbar]');
const topbar=mount(header,{send:cmd=>commands.push(cmd)});topbar.render();tick(32);
const estop=header.querySelector('[data-action="estop"]'), reset=header.querySelector('[data-action="reset"]');
assert.equal(header.lastElementChild,estop);assert.equal(estop.previousElementSibling,reset);
assert.equal(header.querySelector('.console-brand-name').textContent,'ReArm');
assert.equal(header.querySelector('.console-brand small').textContent,'日新臂 · 生产控制台');
assert.equal(header.querySelector('img'),null);
assert.equal(header.querySelector('[data-status]').textContent,'待命');
estop.click();assert.deepEqual(commands,[]);
topbar.render({phase:'pick',link:{online:true}});tick(32);
assert.equal(header.querySelector('[data-status]').textContent,'抓取中');assert.equal(estop.getAttribute('aria-disabled'),'false');
for(const name of ['Escape','e','E',' ']) key(doc.body,name);assert.deepEqual(commands,[]);
estop.click();assert.deepEqual(commands,['estop']);
assert.equal(header.querySelector('[data-status]').textContent,'抓取中'); // 展示必须等待数据源状态。
topbar.render({phase:'estop',link:{online:true}});tick(32);assert.equal(estop.getAttribute('aria-disabled'),'false');
topbar.dispose();tooltip.dispose();dom.window.close();
''')


def test_topbar_connection_uses_handshake_and_hides_missing_source_without_stale_labels():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/shell/topbar.js');
const header=doc.querySelector('[data-topbar]'), topbar=mount(header);
const connection=header.querySelector('.console-connection'), source=header.querySelector('.console-source');
const label=header.querySelector('.console-connection-label');
topbar.render();tick(32);assert.equal(connection.hidden,true);assert.equal(source.hidden,true);
for(const [state,text,sourceText,connected] of [
  [{link:{online:true}},'等待握手','',false],
  [{link:{online:true},hello:{proto:1,sim:true}},'实时连接','本地演示',true],
  [{link:{online:true},hello:{proto:1,sim:false}},'实时连接','主机',true],
  [{link:{online:false},hello:{proto:1,sim:false}},'未连接','主机',false],
  [{link:{online:true},hello:{proto:2,sim:true}},'协议不兼容','本地演示',false],
  [{link:{online:true},hello:{proto:1}},'实时连接','',true],
]) {
  topbar.render(state);tick(32);
  assert.equal(label.textContent,text);assert.equal(connection.dataset.online,String(connected));
  assert.equal(source.textContent,sourceText);assert.equal(source.hidden,!sourceText);
  assert.equal(header.querySelector('[data-status]').textContent,'待命');
}
topbar.render({hello:{sim:true}});tick(32);
assert.equal(connection.hidden,false);assert.equal(label.hidden,true);
assert.equal(source.textContent,'本地演示');assert.equal(connection.dataset.online,'false');
topbar.render({});tick(32);assert.equal(connection.hidden,true);assert.equal(source.textContent,'');
topbar.dispose();assert.equal(header.children.length,0);dom.window.close();
''')


def test_render_coalesces_and_dispose_cancels_pending_frame():
    jsdom_script(DOM + r'''
const {frameView}=await import('./console/shell/view.js');
const seen=[];let disposed=0;const view=frameView(state=>seen.push(state),()=>disposed++,win);
view.render(1);view.render(2);view.render(3);assert.deepEqual(seen,[]);tick(16);assert.deepEqual(seen,[3]);
view.render(4);view.dispose();view.dispose();tick(100);view.render(5);tick(100);
assert.deepEqual(seen,[3]);assert.equal(disposed,1);dom.window.close();
''')


def test_one_page_mount_failure_preserves_other_pages_navigation_and_topbar():
    jsdom_script(DOM + r'''
let failed=false;const replace=win.Element.prototype.replaceChildren;
win.Element.prototype.replaceChildren=function(...children) {
  if(this.dataset.page==='parts' && !failed) {failed=true;throw new Error('page mount failed');}
  return replace.apply(this,children);
};
const warnings=[];const warn=console.warn;console.warn=(...args)=>warnings.push(args);
await import('./console/main.js');tick(32);console.warn=warn;
assert.equal(failed,true);
// JSDOM 无 WebGL/ResizeObserver，孪生失败应独立降级，不能覆盖生产页或影响急停。
assert.equal(warnings.length,2);
assert.equal(warnings.filter(args=>args[0].includes('页面 parts')).length,1);
assert.equal(warnings.filter(args=>args[0].includes('页面 twin')).length,1);
assert.match(doc.querySelector('[data-twin-stage]').textContent,/刷新重试/);
assert.ok(doc.querySelector('[data-action="start"]'));
assert.equal(doc.querySelectorAll('[data-page][data-ready="true"]').length,3);
assert.match(doc.querySelector('[data-page="parts"]').textContent,/刷新重试/);
assert.equal(doc.querySelectorAll('[data-nav]').length,4);
assert.equal(doc.querySelector('[data-status]').textContent,'待命');
assert.equal(doc.querySelector('[data-topbar]').lastElementChild.dataset.action,'estop');
win.history.replaceState(null,'','#settings');win.dispatchEvent(new win.HashChangeEvent('hashchange'));tick(16);
assert.equal(doc.querySelector('[data-page="settings"]').hidden,false);
win.dispatchEvent(new win.PageTransitionEvent('pagehide'));
assert.equal(doc.querySelector('[data-tip]'),null);dom.window.close();
''')
