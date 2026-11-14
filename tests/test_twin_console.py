"""节点① T3：状态开关、真实投影锚点与悬停交互；不启动浏览器。"""
import json

import pytest

from tests.test_arm_kinematics import node
from tests.test_twin_overlay import SCENE_HOST


HOST = SCENE_HOST + r'''
import * as T from '../vendor/three.module.min.js';
import {createPropsLayer} from './twin/props.js';
const htmlSetter=Object.getOwnPropertyDescriptor(Element.prototype,'innerHTML').set;
Object.defineProperty(Element.prototype,'innerHTML',{set(value){
 htmlSetter.call(this,value);
 if(value.includes('twin-stage')) for(const [key,el] of Object.entries(this.slots)) {
  el.className=key.slice(1);el.parent=this;
  if(key==='.twin-stage') el.layout={left:137,top:91};
 }
}});
const rect=Element.prototype.getBoundingClientRect;
Element.prototype.getBoundingClientRect=function(){return this.layout
 ?{...this.layout,width:this.clientWidth,height:this.clientHeight,
   right:this.layout.left+this.clientWidth,bottom:this.layout.top+this.clientHeight}:rect.call(this);};
Element.prototype.appendChild=function(el){el.parent=this;this.children.push(el);return el;};
Element.prototype.remove=function(){if(this.parent)this.parent.children=this.parent.children.filter(el=>el!==this);};
Element.prototype.addEventListener=function(type,fn){this.listeners??=new Map();
 if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type).add(fn);};
Element.prototype.removeEventListener=function(type,fn){this.listeners?.get(type)?.delete(fn);};
Element.prototype.fire=function(type,fields={}){for(const fn of this.listeners?.get(type)||[])fn(fields);};
const viewport=new Element();
globalThis.addEventListener=(...args)=>viewport.addEventListener(...args);
globalThis.removeEventListener=(...args)=>viewport.removeEventListener(...args);
const resizeObservers=[];
globalThis.ResizeObserver=class{constructor(callback){this.callback=callback;resizeObservers.push(this);}
 observe(el){this.el=el;}disconnect(){this.el=null;}};
let twinCode=await readFile(new URL('./twin/twin.js',base),'utf8');
twinCode=absoluteImports(twinCode).replace('import("./scene.js")','import('+JSON.stringify(sceneUrl)+')')
 .replace('import("./fallback2d.js")','import('+JSON.stringify(new URL('./twin/fallback2d.js',base).href)+')');
const {createTwin}=await import(moduleUrl(twinCode));
const labelsOf=container=>container.slots['.twin-labels'].children;
const anchors=container=>labelsOf(container).map(el=>[Number(el.dataset.anchorX),Number(el.dataset.anchorY)]);
const visible=container=>labelsOf(container).map((el,i)=>!el.hidden&&el.style.visibility==='visible'?i:-1).filter(i=>i>=0);
const move=(container,p)=>container.fire('pointermove',{clientX:p[0],clientY:p[1]});
'''


@pytest.mark.parametrize('fallback', [False, True])
@pytest.mark.parametrize('status', [False, True])
def test_status_switch_and_default_labels_preserve_old_display(fallback, status):
    out = node(HOST + f'''
const container=new Element(), twin=await createTwin(container,{{skin:false,
 forceFallback:{json.dumps(fallback)},status:{json.dumps(status)}}});
twin.update({{q_rad:middle,online:true,mode:'sim'}});settle();
const chip=container.slots['.twin-status'], canvas=container.slots['.twin-stage'].children[0];
const result={{statusHidden:chip.hidden,display:chip.style.display,html:chip.html||'',aria:canvas.attrs['aria-label'],
 labels:labelsOf(container).map(el=>({{hook:el.dataset.twinLabel??null,visibility:el.style.visibility??null}})),
 initialProps:Object.hasOwn(twin.state(),'props'),mode:twin.state().mode}};
twin.dispose();console.log(JSON.stringify(result));
''')
    assert out['statusHidden'] is not status
    assert ('模拟数据' in out['html']) is status
    assert ('模拟数据' in out['aria']) is status
    if not status:
        assert out['display'] == 'none' and out['html'] == ''
    assert out['mode'] == 'sim' and not out['initialProps']
    assert out['labels'] == [{'hook': None, 'visibility': None}] * 6


@pytest.mark.parametrize('fallback', [False, True])
def test_hover_matches_acceptance_hooks_and_viewport_coordinates(fallback):
    out = node(HOST + f'''
const container=new Element(), twin=await createTwin(container,{{skin:false,status:false,labels:'hover',forceFallback:{json.dumps(fallback)}}});
const immediate=anchors(container), initiallyHidden=visible(container).length===0;
twin.update({{q_rad:middle,online:true}});settle();
const initial=anchors(container), hooks=labelsOf(container).map(el=>el.dataset.twinLabel);
move(container,initial[0]);const hovered=visible(container);
const expected={json.dumps(fallback)}?null:(()=>{{const p=new T.Vector3(...position(forwardUrdf(P,middle).frames.joint1)).project(drawnCamera);
 return [137+(p.x+1)*400,91+(1-p.y)*280];}})();
container.fire('pointerleave');const left=visible(container);
move(container,initial[0]);container.fire('pointercancel');const cancelled=visible(container);
move(container,[0,0]);const far=visible(container);
twin.dispose();console.log(JSON.stringify({{immediate,initiallyHidden,initial,hooks,hovered,expected,left,cancelled,far}}));
''')
    assert out['initiallyHidden'] and all(all(v is not None for v in p) for p in out['immediate'])
    assert out['hooks'] == [f'joint{i}' for i in range(1, 7)]
    assert out['hovered'] == [0] and out['left'] == out['cancelled'] == out['far'] == []
    if not fallback:
        assert out['initial'][0] == pytest.approx(out['expected'])


def test_hover_selects_nearest_within_40_pixels_and_clears_unprojectable_anchor():
    out = node(HOST + '''
import {createHoverLabels} from './twin/hover-labels.js';
const root=new Element(),stage=new Element();stage.layout={left:137,top:91};
const hover=createHoverLabels(root,stage), a=new Element(),b=new Element();
hover.register(a,'a');hover.register(b,'b');const entries=[{el:a,at:[100,100]},{el:b,at:[130,100]}];
hover.place(entries);const states=[];
for(const [x,y] of [[100,140],[100,140.001],[118,100],[115,100]]) {
 move(root,[x+137,y+91]);states.push([a.style.visibility,b.style.visibility]);
}
hover.place([{el:a,at:null},{el:b,at:[130,100]}]);
const missing={hidden:a.hidden,x:a.dataset.anchorX??null,y:a.dataset.anchorY??null};
hover.dispose();console.log(JSON.stringify({states,missing}));
''')
    assert out['states'] == [['visible', 'hidden'], ['hidden', 'hidden'], ['hidden', 'visible'], ['visible', 'hidden']]
    assert out['missing'] == {'hidden': True, 'x': None, 'y': None}


def test_hover_refreshes_on_motion_scroll_resize_orbit_and_rebuilds_overlay_labels():
    out = node(HOST + '''
const root=new Element(),twin=await createTwin(root,{skin:false,status:false,labels:'hover'});
twin.update({q_rad:middle,online:true});settle();const a=anchors(root);
const stage=root.slots['.twin-stage'];stage.layout={left:277,top:151};viewport.fire('scroll');const b=anchors(root);
twin.update({q_rad:[0.3,-1.1,-0.7,0.4,-1.2,1.5]});settle();const c=anchors(root);
stage.clientWidth=600;stage.children[0].clientWidth=600;resizeObservers.find(o=>o.el===stage).callback();settle();const d=anchors(root);
const canvas=stage.children[0];canvas.fire('pointerdown',{clientX:200,clientY:100,pointerId:1});
canvas.fire('pointermove',{clientX:250,clientY:120});canvas.fire('pointerup');settle();const e=anchors(root);
const p=position(endPoses(P,twin.state().q_rad).tcp);
twin.setOverlay({nodes:[{id:'<node>',p}],spots:{measured:p,reference:p,deviation_mm:0}});settle();
const overlay=labelsOf(root).slice(6).map(el=>({text:el.textContent,hook:el.dataset.twinLabel,hidden:el.style.visibility}));
twin.setOverlay(null);twin.update({angles_deg:[0,40,-100]});settle();
const reset=labelsOf(root).map(el=>el.dataset.twinLabel);
twin.dispose();const events=[...root.listeners.values(),...viewport.listeners.values()].reduce((n,set)=>n+set.size,0);
twin.setProps([]);twin.update({q_rad:middle});console.log(JSON.stringify({a,b,c,d,e,overlay,reset,events,queued:queued.size}));
''')
    for before, after in zip(out['a'], out['b']):
        assert [y - x for x, y in zip(before, after)] == pytest.approx([140, 60])
    assert out['b'] != out['c'] != out['d'] != out['e']
    assert out['overlay'] == [{'text': '<node>', 'hook': '<node>', 'hidden': 'hidden'},
                              {'text': '偏差 0.0 mm', 'hook': '偏差 0.0 mm', 'hidden': 'hidden'}]
    assert out['reset'] == ['joint1', 'joint2', 'joint3']
    assert out['events'] == out['queued'] == 0
