"""T6：记录完成/中断/重置和只读连接信息；沿用 Node/JSDOM 宿主。"""
from tests.test_console_shell import DOM
from tests.test_trainer_views import jsdom_script


SETUP = DOM + r'''
const {createStore,initialState}=await import('./console/state/store.js');
const {createMockConsole}=await import('./datasource/mock-console.js');
const {mount:mountRecords}=await import('./console/pages/records/index.js');
const {mount:mountSettings}=await import('./console/pages/settings/index.js');
const store=createStore(), source=createMockConsole({now:()=>new Date(2026,10,15,9,0,0).getTime(),setTimer:()=>1,clearTimer:()=>{}});
const off=source.subscribe(message=>store.dispatch(message));source.start();
const ctx={store,send(){throw new Error('只读页面不应发送指令');}};
const recordsRoot=doc.createElement('section'),settingsRoot=doc.createElement('section');
recordsRoot.dataset.page='records';settingsRoot.dataset.page='settings';doc.body.append(recordsRoot,settingsRoot);
const records=mountRecords(recordsRoot,ctx),settings=mountSettings(settingsRoot,ctx);
const offViews=store.subscribe(state=>{records.render(state);settings.render(state);});tick(16);
const body=kind=>recordsRoot.querySelector(`[data-records="${kind}"] tbody`);
const rows=kind=>[...body(kind).rows].filter(row=>!row.querySelector('.records-empty')).map(row=>[...row.cells].map(cell=>cell.textContent));
const setting=key=>settingsRoot.querySelector(`[data-setting="${key}"]`).textContent;
const advance=ms=>{source.advance(ms);tick(16);};
function cleanup(){offViews();off();source.stop();records.dispose();settings.dispose();dom.window.close();}
'''


def test_records_show_only_completed_runs_and_reset_clears_both_tables():
    jsdom_script(SETUP + r'''
assert.equal(recordsRoot.querySelectorAll('table').length,2);
assert.deepEqual([...recordsRoot.querySelectorAll('[data-records="production"] th')].map(el=>el.textContent),['时间','配方','结果','偏差','用时']);
assert.match(body('production').textContent,/还没有生产记录/);
assert.match(body('training').textContent,/还没有训练记录/);
assert.equal(source.commands.length,0);
await source.send('run_start',{recipe_id:'plate-tube'});advance(14000);
assert.equal(rows('production').length,0);
await source.send('estop');advance(5000);assert.equal(rows('production').length,0);
await source.send('reset_demo');await source.send('reset_estop');tick(16);
await source.send('run_start',{recipe_id:'plate-tube'});advance(38000);
assert.deepEqual(rows('production'),[['09:00:51','薄片 + 空心圆柱配套件','到位','0.4 mm','0:32']]);
const first=body('production').rows[0];advance(50);assert.equal(body('production').rows[0],first);
await source.send('train_start',{target:'part',draft:{id:'plate'}});advance(9600);
assert.equal(rows('training').length,1);
const hello=store.getState().hello;
await source.send('reset_demo');tick(16);
assert.equal(rows('production').length,0);assert.equal(rows('training').length,0);
assert.match(body('production').textContent,/还没有生产记录/);
assert.equal(store.getState().hello,hello);assert.equal(setting('threshold'),'1.0 mm');
cleanup();
''')


def test_training_records_resolve_part_recipe_names_and_ignore_interrupted_training():
    jsdom_script(SETUP + r'''
assert.deepEqual([...recordsRoot.querySelectorAll('[data-records="training"] th')].map(el=>el.textContent),['时间','对象','轮数','最终偏差','用时']);
await source.send('train_start',{target:'part',draft:{id:'plate'}});advance(8400);
assert.equal(rows('training').length,0);
advance(1200);
assert.deepEqual(rows('training'),[['09:00:09','零件 · 薄片','8 轮','0.6 mm','40:00']]);
await source.send('train_start',{target:'recipe',draft:{id:'plate-tube'}});advance(9600);
assert.deepEqual(rows('training')[0],['09:00:19','配方 · 薄片 + 空心圆柱配套件','8 轮','0.6 mm','40:00']);
assert.equal(rows('training').length,2);
assert.deepEqual(store.getState().trains.map(row=>row.target),['part','recipe']);
const first=body('training').rows[0];advance(500);assert.equal(body('training').rows[0],first);
await source.send('train_start',{target:'part',draft:{id:'tube'}});advance(2400);
await source.send('estop');advance(10000);assert.equal(rows('training').length,2);
cleanup();
''')


def test_record_metadata_can_arrive_late_without_fabricating_missing_values_or_markup():
    jsdom_script(SETUP + r'''
const state={...initialState(),runs:[
  {run_id:'1',recipe_id:'later',ok:false,deviation_mm:1.26,duration_ms:125000,t:new Date(2026,10,15,9,5,0).getTime()},
  {run_id:'2',recipe_id:'unknown',ok:null,deviation_mm:null,duration_ms:null,t:null},
],trains:[{train_id:'1',target:'part',doc_id:'other',round:null,deviation_mm:null,elapsed_ms:null,t:null}]};
records.render(state);tick(16);
assert.deepEqual(rows('production')[0],['—','unknown','—','—','—']);
assert.deepEqual(rows('production')[1],['09:05:00','later','未到位','1.3 mm','2:05']);
assert.deepEqual(rows('training')[0],['—','零件 · other','—','—','—']);
const name='<img src=x onerror=alert(1)>很长的配方名称';
records.render({...state,library:{parts:[{id:'other',name:'新零件'}],recipes:[{id:'later',name}]}});tick(16);
assert.equal(rows('production')[1][1],name);assert.equal(rows('training')[0][1],'零件 · 新零件');
assert.equal(recordsRoot.querySelector('img'),null);
assert.deepEqual(state.runs.map(row=>row.run_id),['1','2']);
records.render(state);records.dispose();tick(16);
assert.equal(recordsRoot.childElementCount,0);
assert.ok(![...doc.querySelectorAll('link')].some(el=>el.href.endsWith('/records.css')));
cleanup();
''')


def test_settings_are_readonly_and_follow_connection_protocol_and_threshold():
    jsdom_script(SETUP + r'''
assert.equal(setting('source'),'本地演示');assert.equal(setting('connection'),'已连接');
assert.equal(setting('protocol'),'v1');assert.equal(setting('threshold'),'1.0 mm');assert.equal(setting('opening'),'全开');
assert.equal(settingsRoot.querySelectorAll('input,select,textarea,button,[contenteditable]').length,0);
assert.equal(source.commands.length,0);
source.stop();tick(16);assert.equal(setting('connection'),'未连接');
assert.equal(setting('protocol'),'v1');assert.equal(setting('threshold'),'1.0 mm');
const blank=initialState();settings.render(blank);tick(16);
for(const field of ['source','protocol','threshold'])assert.equal(setting(field),'—');
settings.render({...blank,link:{online:true}});tick(16);assert.equal(setting('connection'),'等待握手');
settings.render({...blank,link:{online:true},hello:{proto:2,sim:false,threshold_mm:null}});tick(16);
assert.equal(setting('source'),'主机');assert.equal(setting('connection'),'协议不兼容');assert.equal(setting('protocol'),'v2');
assert.equal(setting('threshold'),'—');
const current={...blank,link:{online:true},hello:{proto:1,sim:true,threshold_mm:2.75}};
settings.render(current);tick(16);assert.equal(setting('threshold'),'2.8 mm');assert.equal(setting('connection'),'已连接');
settings.render({...current,hello:{...current.hello,threshold_mm:0}});tick(16);assert.equal(setting('threshold'),'0.0 mm');
assert.equal(source.commands.length,0);
settings.render(blank);settings.dispose();tick(16);assert.equal(settingsRoot.childElementCount,0);
assert.ok(![...doc.querySelectorAll('link')].some(el=>el.href.endsWith('/settings.css')));
cleanup();
''')
