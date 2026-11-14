"""节点① T3：占位几何、夹持变换、生命周期和 2D 退路。"""
import json

import pytest

from tests.test_arm_kinematics import node
from tests.test_twin_console import HOST


@pytest.mark.parametrize('shape', ['disc', 'post', 'ring', 'tube', 'box'])
def test_prop_geometry_dimensions_center_and_hollow_shapes(shape):
    out = node(HOST + f'''
const s=createScene(new Element(),C,{{propsFactory:createPropsLayer}});frame(s);
const shape={json.dumps(shape)}, prop={{id:'part',shape,size_m:[0.08,0.06,0.02],pose:[0.2,0.1,0.3],held:false}};
const absent=!named('props');s.setProps([prop]);frame(s);
const mesh=named('props').children[0];mesh.geometry.computeBoundingBox();
const box=mesh.geometry.boundingBox, size=box.getSize(new T.Vector3()).toArray();
const ray=x=>new T.Raycaster(new T.Vector3(x,0.1,1),new T.Vector3(0,0,-1)).intersectObject(mesh,false).length;
const center=ray(0.2),wall=ray(0.23),centerPosition=mesh.getWorldPosition(new T.Vector3()).toArray();
s.dispose();console.log(JSON.stringify({{absent,size,position:centerPosition,center,wall,type:mesh.material.type}}));
''')
    assert out['absent'] and out['size'] == pytest.approx([0.08, 0.06, 0.02], abs=1e-7)
    assert out['position'] == pytest.approx([0.2, 0.1, 0.3])
    assert (out['center'] == 0) is (shape in ('ring', 'tube'))
    assert out['wall'] > 0 and out['type'] == 'MeshStandardMaterial'


def test_held_prop_preserves_grasp_offset_follows_rotation_and_releases():
    out = node(HOST + '''
const root=new Element(),twin=await createTwin(root,{skin:false});
twin.update({q_rad:middle,online:true});settle();
const origin=position(endPoses(P,middle).tcp),pose=origin.map((v,i)=>v+[0.01,-0.02,0.003][i]);
const prop={id:'held',shape:'box',size_m:[0.02,0.03,0.01],pose,held:true};
const fixed={...prop,id:'fixed',held:false};twin.setProps([prop,fixed]);settle();
const mesh=named('props').children[0],geometry=mesh.geometry,initial=rowMajor(mesh.matrixWorld);
const q=[0.3,-1.1,-0.7,0.4,-1.2,1.5];twin.update({q_rad:q});settle();const moved=rowMajor(mesh.matrixWorld);
const expected=new T.Matrix4().set(...endPoses(P,q).tcp)
 .multiply(new T.Matrix4().set(...endPoses(P,middle).tcp).invert()).multiply(new T.Matrix4().makeTranslation(...pose));
twin.setProps([prop,fixed]);settle();const repeat=rowMajor(mesh.matrixWorld),sameMesh=mesh===named('props').children[0]&&geometry===mesh.geometry;
const stationary=named('props').children[1].getWorldPosition(new T.Vector3()).toArray();
twin.setProps([{...prop,pose:[0.1,0.2,0.15],held:false}]);twin.update({q_rad:middle});settle();
const released=rowMajor(named('props').children[0].matrixWorld),count=named('props').children.length;
twin.dispose();console.log(JSON.stringify({initial,moved,expected:rowMajor(expected),repeat,sameMesh,stationary,pose,released,count}));
''')
    assert [out['initial'][i] for i in [3, 7, 11]] == pytest.approx(out['pose'])
    assert out['moved'] == pytest.approx(out['expected']) and out['moved'] != out['initial']
    assert out['repeat'] == pytest.approx(out['moved']) and out['sameMesh']
    assert out['stationary'] == pytest.approx(out['pose']) and out['count'] == 1
    assert [out['released'][i] for i in [3, 7, 11]] == pytest.approx([0.1, 0.2, 0.15])
    assert [out['released'][i] for i in [0, 5, 10]] == pytest.approx([1, 1, 1])


@pytest.mark.parametrize('fallback', [False, True])
def test_public_props_api_copies_workspace_and_clears_in_both_renderers(fallback):
    out = node(HOST + f'''
import {{WORKSPACE}} from './datasource/fixtures/workspace.js';
const root=new Element(),twin=await createTwin(root,{{skin:false,forceFallback:{json.dumps(fallback)}}});
const input=structuredClone(WORKSPACE.props),expected=structuredClone(input).map(({{id,shape,size_m,pose,held}})=>({{id,shape,size_m,pose,held}}));
twin.setProps(input);twin.update({{q_rad:middle,online:true}});settle();const saved=twin.state().props;
input[0].pose[0]=999;input[0].size_m[0]=999;input.push(input[0]);saved[1].pose[0]=999;
const unchanged=JSON.stringify(twin.state().props)===JSON.stringify(expected),copy=twin.state().props;
const count={json.dumps(fallback)}?root.slots['.twin-stage'].children.length:named('props').children.length;
twin.setProps(null);settle();const cleared=twin.state().props;
twin.dispose();twin.setProps(input);console.log(JSON.stringify({{unchanged,copy,expected,count,cleared,renderer:twin.renderer}}));
''')
    assert out['unchanged'] and out['copy'] == out['expected'] and out['cleared'] == []
    assert out['count'] == (1 if fallback else len(out['expected']))
    assert out['renderer'] == ('2d' if fallback else 'webgl')


def test_prop_theme_skin_replacement_and_disposal_reuse_scene_materials():
    out = node(HOST + '''
const s=createScene(new Element(),{...C,scene:{...C.scene,pedestalHeight:9}},{propsFactory:createPropsLayer});frame(s);
const prop={id:'part',shape:'tube',size_m:[0.04,0.04,0.03],pose:[0.2,0,0.3],held:false};
s.setProps([prop]);frame(s);const mesh=named('props').children[0],parent=mesh.parent;
const material=mesh.material;let geometries=0,materials=0;
mesh.traverse(o=>o.geometry?.addEventListener('dispose',()=>geometries++));
material.addEventListener('dispose',()=>materials++);
globalThis.getComputedStyle=()=>({getPropertyValue:n=>n==='--twin-plate'?'#123456':''});s.applyTheme();
const color=material.color.getHexString();globalThis.fetch=fetchFiles;
await s.loadSkin(new URL('./twin/meshes/b601.json',base));frame(s);
const kept=mesh.visible&&mesh.parent===parent,at=mesh.getWorldPosition(new T.Vector3()).toArray();
s.setProps([{...prop,size_m:[0.06,0.06,0.03]}]);frame(s);
const replacement=named('props').children[0],changed=mesh!==replacement;
replacement.traverse(o=>o.geometry?.addEventListener('dispose',()=>geometries++));
const afterReplacement={geometries,materials};s.setProps([]);
const afterClear={geometries,materials,count:named('props').children.length};
s.setProps([prop]);named('props').children[0].traverse(o=>o.geometry?.addEventListener('dispose',()=>geometries++));
s.dispose();console.log(JSON.stringify({color,kept,at,changed,afterReplacement,afterClear,geometries,materials}));
''')
    assert out['color'] == '123456' and out['kept'] and out['changed']
    assert out['at'] == pytest.approx([0.2, 0, 0.3])
    assert out['afterReplacement'] == {'geometries': 2, 'materials': 0}
    assert out['afterClear'] == {'geometries': 4, 'materials': 0, 'count': 0}
    assert out['geometries'] == 6 and out['materials'] == 1


@pytest.mark.parametrize('bad', ['{}', '[{...prop,shape:"unknown"}]', '[{...prop,size_m:[0,1,1]}]',
                                 '[{...prop,pose:[NaN,0,0]}]', '[prop,prop]'])
def test_malformed_props_reject_atomically_without_losing_previous_scene(bad):
    out = node(HOST + f'''
const root=new Element(),twin=await createTwin(root,{{skin:false}});
const prop={{id:'part',shape:'box',size_m:[0.02,0.03,0.01],pose:[0.1,0.2,0.3],held:false}};
twin.setProps([prop]);settle();let rejected=false;
try{{twin.setProps({bad});}}catch(error){{rejected=error instanceof TypeError;}}
const props=twin.state().props,count=named('props').children.length;
twin.dispose();console.log(JSON.stringify({{rejected,props,count,prop}}));
''')
    assert out['rejected'] and out['props'] == [out['prop']] and out['count'] == 1
