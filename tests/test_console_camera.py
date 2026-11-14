"""观察画面的媒体来源、回退和生命周期；使用现有 Node/JSDOM 宿主。"""
import pytest

from tests.test_console_shell import DOM
from tests.test_trainer_views import jsdom_script


SETUP = DOM + r'''
const {mount}=await import('./console/pages/production/views/observe-view.js');
const {initialState}=await import('./console/state/store.js');
const {workspaceBox}=await import('./console/state/workspace.js');
const mediaCalls=[];
win.HTMLMediaElement.prototype.pause=function(){mediaCalls.push(['pause',this]);};
win.HTMLMediaElement.prototype.load=function(){mediaCalls.push(['load',this]);};
const rect=win.HTMLElement.prototype.getBoundingClientRect;
win.HTMLElement.prototype.getBoundingClientRect=function(){
  if(this.classList.contains('production-camera'))return{width:378,height:252};
  if(this.classList.contains('production-camera-status'))return{width:116,height:28};
  if(this.dataset.target)return{width:150,height:26};
  return rect.call(this);
};
const rootView=doc.createElement('section');rootView.dataset.page='production';doc.body.append(rootView);
const state=initialState();state.phase='recognize';
state.recognition={targets:state.workspace.props.map(prop=>({id:prop.id,name:prop.name,
  confidence:.97,box_px:workspaceBox(state.workspace,prop)}))};
const $=selector=>rootView.querySelector(selector);
const emit=(el,type)=>el.dispatchEvent(new win.Event(type));
function render(view){view.render(state);tick(16);}
function schematic(){
  assert.notEqual($('[data-object]').parentElement.style.display,'none');
  assert.equal($('.production-camera-feed').hidden,true);
  assert.equal($('.production-camera-status').hidden,false);
  assert.ok($('.production-camera-status').classList.contains('c-chip'));
  tick(16); // 标签经 frameView 在下一帧避让刚显示的状态标记。
  for(const label of rootView.querySelectorAll('.production-targets li')){
    assert.ok(parseFloat(label.style.left)>=24);
    assert.ok(parseFloat(label.style.left)+150<=378-24);
    assert.ok(parseFloat(label.style.top)>=24);
    assert.ok(parseFloat(label.style.top)+26<=252-28-4-24);
  }
}
function live(){
  assert.equal($('[data-object]').parentElement.style.display,'none');
  assert.equal($('.production-camera-feed').hidden,false);
  assert.equal($('.production-camera-status').hidden,true);
  for(const selector of ['[data-target-box]','[data-target-leader]','.production-targets li'])
    assert.equal(rootView.querySelectorAll(selector).length,state.recognition.targets.length);
  assert.equal($('.production-targets').hidden,false);
}
'''


def test_no_source_mjpeg_load_and_null_keep_schematic_and_overlay():
    jsdom_script(SETUP + r'''
const view=mount(rootView);render(view);schematic();
assert.equal($('.production-camera-status').textContent,'未接入摄像头');
assert.equal($('.production-camera-feed').childElementCount,0);
const shapes=[...rootView.querySelectorAll('[data-object]')];
view.setCameraSource('/api/camera.mjpg');schematic();
const img=$('.production-camera-feed img');assert.ok(img);assert.equal(img.getAttribute('src'),'/api/camera.mjpg');
emit(img,'load');render(view);live();
const feed=$('.production-camera-feed'),scene=$('.production-observe > g');
const transform=scene.getAttribute('transform').match(/translate\((\S+) (\S+)\) scale\((\S+)\)/).slice(1).map(Number);
assert.equal(parseFloat(feed.style.left),transform[0]);assert.equal(parseFloat(feed.style.top),transform[1]);
assert.equal(parseFloat(feed.style.width),state.workspace.image.width*transform[2]);
assert.equal(parseFloat(feed.style.height),state.workspace.image.height*transform[2]);
assert.ok(feed.compareDocumentPosition($('.production-observe')) & win.Node.DOCUMENT_POSITION_FOLLOWING);
view.setCameraSource(null);render(view);schematic();
assert.equal($('.production-camera-status').textContent,'未接入摄像头');
assert.equal(feed.childElementCount,0);assert.equal(img.hasAttribute('src'),false);
assert.deepEqual([...rootView.querySelectorAll('[data-object]')],shapes);
emit(img,'load');schematic();view.dispose();dom.window.close();
''')


def test_url_extensions_explicit_types_and_query_default():
    jsdom_script(SETUP + r'''
const url='/api/camera.mjpg?token=a+b&stream=1';
win.history.replaceState(null,'','?keep=1&camera='+encodeURIComponent(url)+'#production');
const view=mount(rootView);render(view);
assert.equal($('.production-camera-feed img').getAttribute('src'),url);
for(const [source,tag] of [
  ['/frame.jpeg?v=1#preview','IMG'],['/CAMERA.MJPG?key=1','IMG'],['/live.mjpeg','IMG'],
  ['/clip.mp4','VIDEO'],['/live.m3u8','VIDEO'],['/clip.webm','VIDEO'],
  ['/clip.mp4?preview=frame.jpg','VIDEO'],['/frame.jpg?file=clip.mp4','IMG'],
  [{url:'/stream',type:'mjpeg'},'IMG'],[{url:'/stream',type:'image/jpeg'},'IMG'],
  [{url:'/stream',type:'multipart/x-mixed-replace; boundary=frame'},'IMG'],
  [{url:'/misleading.mp4',type:'img'},'IMG'],[{url:'/misleading.jpg',type:'video'},'VIDEO'],
  [{url:'/stream',type:'application/vnd.apple.mpegurl'},'VIDEO'],
]){
  view.setCameraSource(source);render(view);
  const el=$('.production-camera-feed').firstElementChild;
  assert.equal(el.tagName,tag,JSON.stringify(source));
  assert.equal(el.getAttribute('src'),typeof source==='string'?source:source.url);
  if(tag==='VIDEO'){
    assert.ok(el.muted&&el.defaultMuted&&el.autoplay&&el.playsInline);
    emit(el,'loadedmetadata');schematic();emit(el,'loadeddata');
  }else emit(el,'load');
  render(view);live();
}
view.setCameraSource(null);render(view);schematic();
assert.equal($('.production-camera-feed').childElementCount,0); // render 不重新接回 URL 默认源。
view.dispose();win.history.replaceState(null,'','?camera=');
const empty=mount(rootView);render(empty);schematic();
assert.equal($('.production-camera-status').textContent,'未接入摄像头');
empty.dispose();dom.window.close();
''')


def test_media_stream_uses_video_and_detaches_without_stopping_owned_tracks():
    jsdom_script(SETUP + r'''
let stops=0;win.MediaStream=class {getTracks(){return[{stop(){stops++;}}];}};
const source=new win.MediaStream(),view=mount(rootView);render(view);
view.setCameraSource(source);const video=$('.production-camera-feed video');
assert.equal(video.srcObject,source);assert.equal(video.hasAttribute('src'),false);
assert.ok(video.muted&&video.autoplay&&video.playsInline);schematic();
emit(video,'loadeddata');render(view);live();
view.setCameraSource(null);render(view);schematic();
assert.equal(video.srcObject,null);assert.equal(stops,0);
assert.deepEqual(mediaCalls.map(([call])=>call),['pause','load']);
view.setCameraSource(source);const active=$('video');emit(active,'loadeddata');
view.dispose();assert.equal(active.srcObject,null);assert.equal(stops,0);
assert.equal(rootView.childElementCount,0);view.setCameraSource(source);render(view);
assert.equal(rootView.childElementCount,0);assert.deepEqual(mediaCalls.map(([call])=>call),['pause','load','pause','load']);
dom.window.close();
''')


@pytest.mark.parametrize('extension,event', [('mjpg', 'load'), ('mp4', 'loadeddata')])
def test_errors_fall_back_and_replaced_sources_cannot_change_current_view(extension, event):
    jsdom_script(SETUP + f"const extension='{extension}',readyEvent='{event}';" + r'''
const view=mount(rootView);render(view);
for(const loaded of [false,true]){
  view.setCameraSource('/camera.'+extension);
  const el=$('.production-camera-feed').firstElementChild;
  if(loaded){emit(el,readyEvent);render(view);live();}
  emit(el,'error');render(view);schematic();
  assert.equal($('.production-camera-status').textContent,'摄像头连接失败');
  assert.equal($('.production-camera-feed').childElementCount,0);
  assert.equal(el.hasAttribute('src'),false);
  emit(el,readyEvent);schematic();
}
view.setCameraSource('/old.'+extension);const old=$('.production-camera-feed').firstElementChild;
const staleReady=old['on'+readyEvent],staleError=old.onerror;
view.setCameraSource('/new.mjpg');staleReady();staleError();schematic();
assert.equal($('.production-camera-status').textContent,'摄像头连接中');
const current=$('img');emit(current,'load');render(view);live();
staleError();live();
view.setCameraSource(null);schematic();assert.equal($('.production-camera-status').textContent,'未接入摄像头');
view.dispose();dom.window.close();
''')
