"""外壳动效的触发、布局重测和销毁；不依赖并发改版中的页面结构。"""
from tests.test_console_shell import DOM
from tests.test_trainer_views import jsdom_script


def test_nav_indicator_tracks_route_resize_fonts_and_cleans_up():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/shell/nav.js');
const fonts=new win.EventTarget();let ready;
fonts.ready=new Promise(resolve=>ready=resolve);
Object.defineProperty(doc,'fonts',{value:fonts});
let observer,disconnected=false;
win.ResizeObserver=class {
  constructor(callback){this.callback=callback;this.targets=[];observer=this;}
  observe(el){this.targets.push(el);} disconnect(){disconnected=true;}
};
const nav=doc.createElement('nav');doc.body.append(nav);
const view=mount(nav), links=[...nav.querySelectorAll('a')];
const indicator=nav.querySelector('.console-nav-indicator');
assert.equal(indicator.getAttribute('aria-hidden'),'true');assert.equal(indicator.hidden,true);
let base=300,width=64,gap=4,reads=0;
nav.getBoundingClientRect=()=>({left:base});
links.forEach((el,i)=>el.getBoundingClientRect=()=>{reads++;return {left:base+i*(width+gap),width};});
assert.equal(observer.targets.length,5);
view.render('production');tick(16);
assert.equal(indicator.hidden,false);assert.equal(indicator.style.width,'64px');
assert.equal(indicator.style.transform,'translateX(0px)');
view.render('parts');tick(16);
assert.equal(links[1].getAttribute('aria-current'),'page');
assert.equal(nav.querySelectorAll('[aria-current]').length,1);
assert.equal(indicator.style.transform,'translateX(68px)');
base=24;width=80;win.dispatchEvent(new win.Event('resize'));tick(16);
assert.equal(indicator.style.transform,'translateX(84px)');assert.equal(indicator.style.width,'80px');
width=92;ready();await Promise.resolve();tick(16);
assert.equal(indicator.style.width,'92px');
width=100;fonts.dispatchEvent(new win.Event('loadingdone'));tick(16);
assert.equal(indicator.style.transform,'translateX(104px)');
width=110;observer.callback();tick(16);assert.equal(indicator.style.width,'110px');
observer.callback();const before=reads;view.dispose();tick(16);
assert.equal(disconnected,true);assert.equal(nav.children.length,0);
fonts.dispatchEvent(new win.Event('loadingdone'));win.dispatchEvent(new win.Event('resize'));
view.render('settings');tick(32);assert.equal(reads,before);
dom.window.close();
''')


def test_nav_fonts_ready_after_dispose_does_not_measure_removed_nodes():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/shell/nav.js');
const fonts=new win.EventTarget();let ready;
fonts.ready=new Promise(resolve=>ready=resolve);Object.defineProperty(doc,'fonts',{value:fonts});
const nav=doc.createElement('nav');doc.body.append(nav);const view=mount(nav);
nav.getBoundingClientRect=()=>{throw new Error('disposed nav measured');};
view.render('parts');view.dispose();ready();await Promise.resolve();tick(32);
assert.equal(nav.children.length,0);dom.window.close();
''')


def test_route_restarts_entry_only_when_page_changes_even_in_same_frame():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/shell/router.js');
const pagesRoot=doc.querySelector('[data-pages]'), measured=[];
for(const id of ['production','parts','records','settings']){
  const page=doc.createElement('section');page.className='console-page';page.dataset.page=id;
  page.hidden=true;pagesRoot.append(page);
  Object.defineProperty(page,'offsetWidth',{get(){
    assert.equal(page.hidden,false);assert.equal(page.hasAttribute('data-enter'),false);
    measured.push(id);return 800;
  }});
}
const routed=[],router=mount(pagesRoot,{onRoute:id=>routed.push(id)});
const go=id=>{win.history.replaceState(null,'',`#${id}`);router.render();};
assert.deepEqual(measured,['production']);
router.render();assert.deepEqual(measured,['production']);
go('parts');go('production');go('parts'); // 不等 rAF，仍重置进场。
assert.deepEqual(measured,['production','parts','production','parts']);
assert.equal(pagesRoot.querySelector('[data-page="parts"]').hasAttribute('data-enter'),true);
assert.equal([...pagesRoot.children].filter(el=>!el.hidden).length,1);
go('unknown');assert.equal(win.location.hash,'#production');
router.dispose();
const count=routed.length;
win.history.replaceState(null,'','#settings');win.dispatchEvent(new win.HashChangeEvent('hashchange'));
assert.equal(routed.length,count);dom.window.close();
''')


def test_estop_banner_waits_for_confirmed_state_and_disposes_with_shell():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/shell/estop.js');
const header=doc.querySelector('[data-topbar]'),sent=[],view=mount(header,{send:cmd=>sent.push(cmd)});
const button=header.querySelector('[data-action="estop"]'),banner=header.nextElementSibling;
assert.equal(banner.className,'console-estop-banner');assert.equal(banner.getAttribute('role'),'alert');
assert.equal(banner.hidden,true);assert.equal(header.lastElementChild,button);
view.render({phase:'pick',link:{online:true}});tick(16);button.click();
assert.deepEqual(sent,['estop']);assert.equal(banner.hidden,true);
view.render({phase:'estop',link:{online:true}});tick(16);
assert.equal(banner.hidden,false);assert.equal(banner.textContent,'已急停');
view.render({phase:'estop',link:{online:false}});tick(16);assert.equal(banner.hidden,false);
button.click();assert.deepEqual(sent,['estop']);
view.render({phase:'idle',link:{online:true}});tick(16);assert.equal(banner.hidden,true);
view.dispose();assert.equal(banner.isConnected,false);assert.equal(button.isConnected,false);
dom.window.close();
''')


def test_dialog_animation_requires_all_native_capabilities_and_keeps_close_immediate():
    jsdom_script(DOM + r'''
const {mount}=await import('./console/shell/dialog.js');
const trigger=doc.createElement('button');doc.body.append(trigger);
for(const [startingStyle,discrete,overlay] of [[false,true,true],[true,false,true],[true,true,false],[true,true,true]]){
  win.CSSStartingStyleRule=startingStyle?class {}:undefined;
  win.CSS={supports:property=>property==='overlay'?overlay:discrete};
  trigger.focus();const view=mount(doc.body),panel=doc.querySelector('dialog');
  assert.equal(panel.hasAttribute('data-motion'),startingStyle&&discrete&&overlay);
  view.open({title:'确认',content:'测试'});assert.equal(panel.open,true);
  view.close();assert.equal(panel.open,false);assert.equal(doc.activeElement,trigger);
  view.open();view.dispose();assert.equal(panel.isConnected,false);
}
dom.window.close();
''')
