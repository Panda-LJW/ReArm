"""T5：库文档、三步训练与跨页互斥；真实 store/主机，JSDOM 和虚拟时间。"""
import re
import pytest

from tests.test_console_production import SETUP
from tests.test_console_shell import CONSOLE
from tests.test_trainer_views import jsdom_script


PARTS_SETUP = SETUP + r'''
const {mount:mountParts}=await import('./console/pages/parts/index.js');
const libraryRoot=doc.createElement('section');libraryRoot.dataset.page='parts';doc.body.append(libraryRoot);
const parts=mountParts(libraryRoot,ctx),offParts=store.subscribe(state=>parts.render(state));
const find=text=>[...libraryRoot.querySelectorAll('button')].find(el=>el.textContent===text&&!el.closest('[hidden]'));
const click=async text=>{const el=find(text);assert.ok(el,`missing ${text}`);el.click();await flush();};
const input=(name,value)=>{const el=libraryRoot.querySelector(`input[aria-label="${name}"]`);el.value=value;el.dispatchEvent(new win.Event('input'));};
const finish=()=>{offParts();parts.dispose();cleanup();};
const tab=async name=>{libraryRoot.querySelector(`[data-tab="${name}"]`).click();await flush();};
async function identifyPart(){
  await click('新增零件');await click('拍照识别');advance(1500);await flush();await click('确认零件');
}
await flush();
'''


def test_library_lists_documents_fields_and_part_links():
    jsdom_script(PARTS_SETUP + r'''
assert.equal(libraryRoot.querySelectorAll('[data-part]').length,4);
assert.equal(libraryRoot.querySelectorAll('[data-tab]').length,2);
assert.match(libraryRoot.querySelector('.library-table').textContent,/名称编号版本收录时间/);
assert.equal(libraryRoot.querySelectorAll('#library-parts tbody svg').length,4);
libraryRoot.querySelector('[data-part]').click();await flush();
assert.equal(libraryRoot.querySelector('[data-force]').textContent,'11.6 N');
assert.match(libraryRoot.querySelector('article').textContent,/36.0 × 36.0 × 5.0 mm/);
for(const word of ['外形与轮廓','全开','估计重量','材质','摩擦系数','安全系数','训练记录','试抓记录','图像数','用时','收录','v1'])
  assert.ok(libraryRoot.querySelector('article').textContent.includes(word),word);
assert.ok(libraryRoot.querySelector('[data-chart="deviation"] svg polyline'));
assert.match(libraryRoot.querySelector('[data-chart="deviation"]').getAttribute('aria-label'),/阈值 1.0 mm/);
assert.equal(libraryRoot.querySelector('video'),null);assert.ok(!libraryRoot.textContent.includes('训练录像'));
const basis=libraryRoot.querySelector('details');basis.open=true;advance(100);assert.equal(basis.open,true);
await tab('recipes');assert.equal(libraryRoot.querySelectorAll('[data-recipe-doc]').length,1);
libraryRoot.querySelector('[data-recipe-doc]').click();await flush();
for(const word of ['圆盘定位工装','装配顺序','薄片 → 定位柱','空心圆柱 → 定位柱','用到的零件','装配训练记录','成功率'])
  assert.ok(libraryRoot.querySelector('article').textContent.includes(word),word);
libraryRoot.querySelector('[data-part-link="tube"]').click();await flush();
assert.equal(libraryRoot.querySelector('[data-force]').textContent,'12.3 N');finish();
''')


def test_new_part_three_steps_progress_auto_enrollment_and_production_interlock():
    jsdom_script(PARTS_SETUP + r'''
await click('新增零件');
assert.equal(libraryRoot.querySelectorAll('[data-new-flow] [data-step]').length,3);
assert.ok(find('拍照识别'));assert.equal(find('开始训练'),undefined);
await click('拍照识别');assert.equal(find('拍照识别').getAttribute('aria-disabled'),'true');
advance(1450);await flush();assert.equal(libraryRoot.querySelector('input[aria-label="名称"]').closest('[hidden]')!==null,true);
advance(50);await flush();
assert.equal(libraryRoot.querySelector('input[aria-label="名称"]').value,'环形垫片');
assert.equal(libraryRoot.querySelector('input[aria-label="编号"]').value,'P005');
input('名称','新的零件');advance(100);await flush();assert.equal(libraryRoot.querySelector('input[aria-label="名称"]').value,'新的零件');
await click('确认零件');assert.equal(find('拍照识别'),undefined);assert.equal(find('确认零件'),undefined);
await click('开始训练');
assert.equal($('[data-status]').textContent,'训练中');assert.equal($('[data-action="start"]').getAttribute('aria-disabled'),'true');
assert.match($('[data-action="start"]').dataset.reason,/正在训练/);
for(let round=1;round<=7;round++){
  advance(1200);await flush();
  assert.equal(libraryRoot.querySelectorAll('[data-new-flow] .library-chart-dot').length,round);
  assert.match(libraryRoot.querySelector('[data-new-flow]').textContent,new RegExp(`第 ${round} 轮`));
  assert.match(libraryRoot.querySelector('[data-new-flow]').textContent,/失败/);
}
advance(1200);await flush();
assert.match(libraryRoot.querySelector('[data-new-flow]').textContent,/训练完成 · 已收录/);
assert.equal(find('开始训练'),undefined);assert.equal($('[data-status]').textContent,'待命');
assert.equal($('[data-action="start"]').getAttribute('aria-disabled'),'false');
assert.equal(store.getState().trains[0].images,192);assert.equal(store.getState().trains[0].elapsed_ms,9600);
await tab('parts');assert.equal(libraryRoot.querySelectorAll('[data-part]').length,5);
assert.equal(store.getState().library.parts.at(-1).name,'新的零件');
assert.equal(source.commands.filter(c=>c.cmd==='train_start').length,1);
assert.ok(source.commands.every(c=>!c.cmd.startsWith('laser_')));finish();
''')


def test_new_recipe_selects_parts_reorders_and_links_trained_document():
    jsdom_script(PARTS_SETUP + r'''
await tab('recipes');await click('新增配方');input('名称','反向配套件');
const fixture=libraryRoot.querySelector('select[aria-label="工装"]');assert.equal(fixture.value,'disc-fixture');
const checks=libraryRoot.querySelectorAll('[data-new-flow] input[type="checkbox"]');assert.equal(checks.length,4);
for(const check of [...checks].slice(0,2)){check.checked=true;check.dispatchEvent(new win.Event('change'));}
await flush();
libraryRoot.querySelector('[aria-label="上移空心圆柱"]').click();await flush();
await click('确认配方');await click('开始训练');advance(9600);await flush();
const request=source.commands.find(c=>c.cmd==='train_start');
assert.deepEqual(request.draft.steps.map(s=>s.part_id),['tube','plate']);
assert.ok(request.draft.steps.every(s=>s.target_id==='post'));
assert.equal(store.getState().library.recipes.length,2);
await click('查看文档');assert.match(libraryRoot.querySelector('article').textContent,/反向配套件/);
assert.equal(libraryRoot.querySelectorAll('[data-part-link]').length,2);
assert.match(libraryRoot.querySelector('article').textContent,/成功率88%/);
await tab('recipes');assert.equal(libraryRoot.querySelectorAll('[data-recipe-doc]').length,2);finish();
''')


@pytest.mark.parametrize('target,tab_name,hook,collection', [
    ('part', 'parts', 'data-part', 'partDocs'),
    ('recipe', 'recipes', 'data-recipe-doc', 'recipeDocs'),
])
def test_retraining_uses_steps_two_three_and_increments_version_without_new_row(target, tab_name, hook, collection):
    jsdom_script(PARTS_SETUP + f"const target='{target}',tabName='{tab_name}',hook='{hook}',collection='{collection}';\n" + r'''
await tab(tabName);const count=store.getState().library[tabName].length;
const row=libraryRoot.querySelector(`[${hook}]`),id=row.getAttribute(hook);row.click();await flush();
const original=structuredClone(store.getState()[collection][id]);
await click('重新训练');assert.equal(find('拍照识别'),undefined);
assert.equal(libraryRoot.querySelector('[aria-current="step"]').dataset.step,'2');
await click('开始训练');advance(9600);await flush();
assert.equal(libraryRoot.querySelector('[aria-current="step"]').dataset.step,'3');
await click('查看文档');const updated=store.getState()[collection][id];
assert.equal(updated.version,original.version+1);assert.equal(updated.name,original.name);assert.equal(updated.code,original.code);
assert.equal(store.getState().library[tabName].length,count);assert.match(libraryRoot.querySelector('article').textContent,/v2/);
assert.deepEqual(source.commands.filter(c=>c.cmd==='train_start').at(-1).draft,{id});finish();
''')


def test_production_blocks_training_and_rechecks_state_before_click():
    jsdom_script(PARTS_SETUP + r'''
await identifyPart();
// 主机先进入生产，刻意不画下一帧，点击仍应读取当前 store。
await source.send('run_start',{recipe_id:'plate-tube'});
find('开始训练').click();await flush();
assert.equal(source.commands.filter(c=>c.cmd==='train_start').length,0);
const start=find('开始训练');assert.equal(start.getAttribute('aria-disabled'),'true');assert.match(start.dataset.reason,/正在生产/);
for(const k of ['Enter',' '])assert.equal(key(start,k).defaultPrevented,true);
advance(38000);await flush();assert.equal(start.getAttribute('aria-disabled'),'false');
await click('开始训练');assert.equal($('[data-status]').textContent,'训练中');finish();
''')


def test_estop_or_reset_never_enrolls_interrupted_training_and_retry_works():
    jsdom_script(PARTS_SETUP + r'''
await identifyPart();await click('开始训练');advance(2400);await flush();
await source.send('estop');await flush();advance(10000);await flush();
assert.match(libraryRoot.querySelector('[data-new-flow]').textContent,/训练已中断，未收录/);
assert.ok(!libraryRoot.querySelector('[data-new-flow]').textContent.includes('训练完成 · 已收录'));
assert.equal(store.getState().library.parts.length,4);assert.equal(store.getState().trains.length,0);
await source.send('reset_demo');await flush();await click('开始训练');advance(1200);await flush();
await source.send('reset_demo');await flush();assert.match(libraryRoot.querySelector('[data-new-flow]').textContent,/未收录/);
await click('开始训练');advance(9600);await flush();assert.equal(store.getState().library.parts.length,5);finish();
''')


def test_capture_ignores_old_candidate_and_can_restart_after_reset():
    jsdom_script(PARTS_SETUP + r'''
await source.send('part_capture');advance(1500);await flush();
await click('新增零件');await flush();assert.equal(find('确认零件'),undefined);
await click('拍照识别');advance(200);await source.send('reset_demo');await flush();
assert.match(libraryRoot.querySelector('[data-new-flow]').textContent,/识别已中断/);
await click('拍照识别');advance(1500);await flush();assert.ok(find('确认零件'));
input('编号','P001');assert.equal(find('确认零件').getAttribute('aria-disabled'),'true');
assert.match(find('确认零件').dataset.reason,/编号已存在/);
input('编号','P105');input('名称','<img src=x onerror=alert(1)>');await click('确认零件');
assert.equal(libraryRoot.querySelector('[data-new-flow] img'),null);finish();
''')


def test_rejected_commands_and_document_retry_do_not_fabricate_success():
    jsdom_script(PARTS_SETUP + r'''
offParts();parts.dispose();let reject='part_get';
const controlled=mountParts(libraryRoot,{...ctx,send:(cmd,args)=>cmd===reject?Promise.resolve({ok:false,msg:'请求未获接受'}):ctx.send(cmd,args)});
const offControlled=store.subscribe(s=>controlled.render(s));await flush();
libraryRoot.querySelector('[data-part]').click();await flush();assert.ok(find('重新读取'));
assert.match(libraryRoot.querySelector('article').textContent,/请求未获接受/);
reject=null;await click('重新读取');assert.equal(libraryRoot.querySelector('[data-force]').textContent,'11.6 N');
await tab('parts');await click('新增零件');reject='part_capture';await click('拍照识别');
assert.match(libraryRoot.querySelector('[data-new-flow]').textContent,/请求未获接受/);assert.equal(find('确认零件'),undefined);
reject=null;await click('拍照识别');advance(1500);await flush();await click('确认零件');
reject='train_start';await click('开始训练');advance(12000);await flush();
assert.equal(store.getState().library.parts.length,4);assert.equal(store.getState().trains.length,0);
assert.match(libraryRoot.querySelector('[data-new-flow]').textContent,/请求未获接受/);
assert.equal(find('开始训练').getAttribute('aria-disabled'),'false');
offControlled();controlled.dispose();cleanup();
''')


def test_training_completion_survives_paused_render_and_tab_switches():
    jsdom_script(PARTS_SETUP + r'''
await identifyPart();find('开始训练').click();await Promise.resolve();
source.advance(9600);await flush(); // 模拟后台标签页暂停 RAF，完成消息仍由 store 收到。
assert.match(libraryRoot.querySelector('[data-new-flow]').textContent,/训练完成 · 已收录/);
await tab('recipes');await tab('parts');assert.equal(libraryRoot.querySelectorAll('[data-part]').length,5);
await click('查看新增流程');assert.match(libraryRoot.querySelector('[data-new-flow]').textContent,/训练完成 · 已收录/);
const before=libraryRoot.innerHTML;offParts();parts.dispose();source.advance(500);await flush();assert.equal(libraryRoot.children.length,0);
assert.ok(before.length>0);cleanup();
''')


def test_line_chart_scale_empty_single_round_and_recording_presence():
    jsdom_script(PARTS_SETUP + r'''
const {niceTicks,mount:chart}=await import('./console/widgets/line-chart.js');
const {mount:recordView}=await import('./console/pages/parts/views/training-record.js');
assert.deepEqual(niceTicks(5.7,1),{top:6,ticks:[0,2,4,6]});
const host=doc.createElement('div');libraryRoot.append(host);const view=chart(host);
view.render({rounds:[],threshold_mm:1});await flush();assert.match(host.getAttribute('aria-label'),/暂无记录/);
view.render({rounds:[{round:1,deviation_mm:0}],threshold_mm:1});await flush();
assert.equal(host.querySelector('polyline').getAttribute('points'),'50,100');
assert.equal(host.querySelectorAll('.library-chart-dot').length,1);view.dispose();
const record=recordView(host);win.HTMLMediaElement.prototype.pause=function(){};
record.render({rounds:[],video_url:'/training/part.mp4'});await flush();
assert.ok(host.querySelector('video'));assert.equal(host.querySelector('video').muted,true);
record.render({rounds:[]});await flush();assert.equal(host.querySelector('video'),null);assert.ok(!host.textContent.includes('录像'));
record.dispose();finish();
''')


def test_parts_css_and_code_stay_scoped_to_t5_and_tokens():
    css = (CONSOLE / 'pages/parts/parts.css').read_text()
    assert not re.search(r'#[\da-fA-F]{3,8}\b|(?:rgb|hsl)a?\(|\d+px|gradient\(|shadow:', css)
    assert all(line.lstrip().startswith(('[data-page="parts"]', '@media', '}')) for line in css.splitlines() if line.strip())
    assert not re.search(r'--fs-(?:2xs|xs|chart)\b', css)
    assert 'stroke: var(--data)' in css and 'stroke: var(--warn)' in css
    assert 'font-size: var(--fs-sm)' in css and 'overflow: auto' in css
    sources = '\n'.join(p.read_text() for p in (CONSOLE / 'pages/parts').rglob('*.js'))
    assert not any(word in sources for word in ['模拟', '待开发', '教师', '敬请期待'])
    assert not re.search(r'\b(?:fetch|WebSocket)\b|__rearmMock|trainer/', sources)
