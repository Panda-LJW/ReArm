"""自制夹指的实体网格、安装与真实 Three 场景加载回归（无需 gmsh）。"""
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pytest

from tests.test_arm_kinematics import DOM_HOST, node

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "rearm/ui/static/modules"
MESHES = MODULES / "twin/meshes"


def read_mesh(name):
    manifest = json.loads((MESHES / f"{name}.json").read_text())
    binary = (MESHES / f"{name}.bin").read_bytes()
    parts = []
    for part in manifest["parts"]:
        arrays = {key: np.frombuffer(binary, dtype=dtype, offset=part[key]["offset"],
                                    count=part[key]["count"]).reshape(-1, 3)
                  for key, dtype in (("positions", "<f4"), ("indices", "<u4"))}
        parts.append((part, arrays))
    return manifest, binary, parts


@pytest.fixture(scope="module")
def params():
    return node("console.log(JSON.stringify(P));")


def test_gripper_binary_layout_and_closed_surface():
    manifest, binary, parts = read_mesh("gripper")
    assert manifest["units"] == "m" and manifest["opening_mm"] == 0
    assert len(parts) == 2 and {p["side"] for p, _ in parts} == {"left", "right"}
    assert {p["frame"] for p, _ in parts} == {"tool"}
    assert {p["material"] for p, _ in parts} == {"finger_white", "finger_grey"}
    offset = triangles = 0
    for part, arrays in parts:
        for key in ("positions", "indices"):
            block = part[key]
            assert block["offset"] == offset and offset % 4 == 0
            assert block["count"] > 0 and block["count"] % 3 == 0
            offset += block["count"] * 4
        vertices, faces = arrays["positions"], arrays["indices"]
        assert np.isfinite(vertices).all() and faces.max() < len(vertices)
        a, b, c = vertices[faces].transpose(1, 0, 2)
        assert (np.linalg.norm(np.cross(b - a, c - a), axis=1) > 1e-12).all()
        # 闭合实体，每条边恰有两面；有向体积为正，翻转没有翻坏法线。
        edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
        assert (np.unique(edges, axis=0, return_counts=True)[1] == 2).all()
        volume_mm3 = np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6 * 1e9
        assert volume_mm3 == pytest.approx(27600.512, rel=0.002)
        triangles += len(faces)
    assert offset == len(binary) and triangles == manifest["triangles"] < 20_000
    assert manifest["simplified"] is False
    assert manifest["source_sha256"] == hashlib.sha256((ROOT / manifest["source"]).read_bytes()).hexdigest()
    assert manifest["step_bounds_mm"]["size"] == [25, 40, 65.5]


def test_closed_fingers_are_symmetric_touching_and_match_mount(params):
    manifest, _, parts = read_mesh("gripper")
    fingers = {p["side"]: a["positions"] for p, a in parts}
    left, right = fingers["left"], fingers["right"]
    assert left[:, 1].min() >= -0.0005 and right[:, 1].max() <= 0.0005
    # 全部三角形均在各自半空间内，因此不仅顶点、连三角形内部也不会交叉。
    assert left[:, 1].min() - right[:, 1].max() == pytest.approx(0, abs=1e-7)
    np.testing.assert_allclose([left[:, 1].min(), left[:, 1].max()],
                               [-right[:, 1].max(), -right[:, 1].min()], atol=0.0005)
    np.testing.assert_allclose(right, left * [1, -1, -1], atol=1e-7)
    gripper = params["gripper"]
    custom = gripper["customFinger"]
    assert manifest["assembly"] == {k: custom[k] for k in ("mount", "flipRpy", "tipX")}
    for vertices in fingers.values():
        assert np.ptp(vertices[:, 0]) == pytest.approx(gripper["fingerLength"], abs=0.001)
        assert vertices[:, 0].min() == pytest.approx(custom["mount"]["xyz"][0], abs=1e-7)
        assert vertices[:, 0].max() == pytest.approx(custom["tipX"], abs=1e-7)
    assert params["T_end_tcp"][3] == custom["tipX"]
    assert params["T_end_camera"][3] == pytest.approx(custom["tipX"] - 0.070)
    assert [params["T_end_camera"][i] for i in (7, 11)] == [0, 0.04]
    assert params["T_end_laser"][3] == params["T_end_camera"][3]
    assert params["T_end_camera"][11] - params["T_end_laser"][11] == pytest.approx(0.020)


def test_maximum_opening_stays_on_rail_and_root_meets_carriages(params):
    _, _, custom = read_mesh("gripper")
    _, _, official = read_mesh("b601")
    rail = next(a["positions"] for p, a in official if p["source"] == "gripper_base_seeed_yellow")
    assert params["gripper"]["openingMm"] == [0, 57]
    assert params["gripper"]["fingerTravel"] == [0, 0.0285]
    for side, sign in (("left", 1), ("right", -1)):
        finger = next(a["positions"] for p, a in custom if p["side"] == side)
        carriage = next(a["positions"] for p, a in official if p["side"] == side and p["material"] == "carriage_grey")
        assert finger[:, 0].min() == pytest.approx(carriage[:, 0].max(), abs=0.0005)
        for vertices in (finger, carriage):
            opened_y = vertices[:, 1] + sign * params["gripper"]["fingerTravel"][1]
            assert opened_y.min() > rail[:, 1].min() and opened_y.max() < rail[:, 1].max()
        # STEP 根部四个 M4 孔的中心投影落在官方滑块端面范围内。
        for y in (sign * 0.010, sign * 0.020):
            assert carriage[:, 1].min() < y < carriage[:, 1].max()


def test_gripper_option_url_wiring_and_css_palette():
    twin = (MODULES / "twin/twin.js").read_text()
    assert 'gripper = "custom"' in twin
    assert re.search(r"scene\.loadSkin\(.*\{ gripper \}", twin)
    for file in ("main.js", "twin/demo.html"):
        text = (MODULES / file).read_text()
        assert 'gripper: params.get("gripper") === "official" ? "official" : "custom"' in text
    assert "?gripper=official" in (MODULES / "twin/demo.html").read_text()
    css = (MODULES / "twin/twin.css").read_text()
    assert "--twin-finger:" in css and "--twin-finger-2:" in css


# 渲染器用宿主替身，其余为真实 Three 几何、矩阵、材质和 scene.js；不伪造加载逻辑。
SCENE_HOST = DOM_HOST + '''
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const base=pathToFileURL(process.cwd()+'/');
let code=await readFile(new URL('./twin/scene.js',base),'utf8');
code=code.replace('import * as THREE from "../../vendor/three.module.min.js";',`
import * as ActualThree from '${new URL('../vendor/three.module.min.js',base)}';
const THREE={...ActualThree,WebGLRenderer:class {
 constructor({canvas}){this.canvas=canvas;} setPixelRatio(){} setSize(){} dispose(){}
 render(scene,camera){scene.updateMatrixWorld();camera.updateMatrixWorld();globalThis.drawnScene=scene;}
}};`);
code=code.replace('"./kinematics.js"',JSON.stringify(new URL('./twin/kinematics.js',base).href));
const {createScene}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const requests=[];
globalThis.fetch=async url=>{
 const path=new URL(url).pathname;requests.push(path);
 const custom=path.includes('/gripper.');
 if(custom && fault==='network') throw Error('network disconnected');
 if(custom && fault==='json404' && path.endsWith('.json')) return {ok:false};
 if(custom && fault==='bin404' && path.endsWith('.bin')) return {ok:false};
 return {ok:true,
  json:async()=>{
   if(custom && fault==='badJson') throw SyntaxError('invalid json');
   const data=JSON.parse(await readFile(url,'utf8'));
   if(custom && fault==='oneFinger') data.parts.pop();
   return data;
  },
  arrayBuffer:async()=>{
   const b=await readFile(url);
   if(custom && fault==='truncated') return new ArrayBuffer(12);
   if(custom && fault==='badIndex') {
    const m=JSON.parse(await readFile(new URL('gripper.json',url),'utf8'));
    b.writeUInt32LE(0xffffffff,m.parts[0].indices.offset);
   }
   return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);
  },
 };
};
function meshes() {const found=[];drawnScene.traverse(o=>{if(o.userData.skin)found.push(o);});return found;}
'''


@pytest.mark.parametrize("choice,fault,expected", [
    ("custom", "none", "custom"), ("official", "none", "official"),
    *[("custom", fault, "official") for fault in
      ("json404", "bin404", "network", "badJson", "oneFinger", "truncated", "badIndex")],
])
def test_scene_loads_selected_fingers_and_falls_back_atomically(choice, fault, expected):
    out = node(f"const fault={json.dumps(fault)};\n" + SCENE_HOST + '''
const scene=createScene(new Element(),C), pose=forwardUrdf(P,middle);
scene.setPoseMatrices(pose,{gripperMm:57});
const choice=CHOICE;
const selected=await scene.loadSkin(new URL('./twin/meshes/b601.json',base),choice==='custom'?undefined:{gripper:choice});
scene.render();
const rows=[];
for(const opening of [57,0,20,57]) {
 scene.setPoseMatrices(pose,{gripperMm:opening});scene.render();
 rows.push(meshes().filter(m=>m.userData.skin.side).map(m=>{
  m.geometry.computeBoundingBox();const box=m.geometry.boundingBox.clone().translate(m.position);
  return {source:m.userData.skin.source,side:m.userData.skin.side,material:m.userData.skin.material,
   xyz:m.position.toArray(),rotation:m.rotation.toArray().slice(0,3),min:box.min.toArray(),max:box.max.toArray(),color:m.material.color.getHexString()};
 }));
}
const sources=meshes().map(m=>m.userData.skin.source), skinned=scene.isSkinned();
globalThis.getComputedStyle=()=>({getPropertyValue:k=>({'--twin-finger':'#f8f0e0','--twin-finger-2':'#555e66'}[k]||'')});
scene.applyTheme();
const themed=meshes().filter(m=>m.userData.skin.material.startsWith('finger_')).map(m=>m.material.color.getHexString());
scene.dispose();console.log(JSON.stringify({selected,rows,sources,requests,skinned,themed}));
'''.replace("CHOICE", json.dumps(choice)))
    assert out["selected"] == expected and out["skinned"]
    manifest, _, parts = read_mesh("b601")
    original = {p["source"] for p in manifest["parts"]}
    tips = {p["source"] for p in manifest["parts"] if p["material"] == "finger_black"}
    assert set(out["sources"]) == (original - tips | {"custom_finger_left", "custom_finger_right"}
                                  if expected == "custom" else original)
    if choice == "official":
        assert not any("/gripper." in request for request in out["requests"])
    for opening, row in zip((57, 0, 20, 57), out["rows"]):
        for part in row:
            sign = 1 if part["side"] == "left" else -1
            assert part["xyz"] == pytest.approx([0, sign * opening / 2000, 0])
            assert part["rotation"] == [0, 0, 0]  # 安装旋转已烘焙，加载时不能再做一遍。
        if expected == "custom":
            fingers = {p["side"]: p for p in row if p["source"].startswith("custom_finger_")}
            assert fingers["left"]["min"][1] - fingers["right"]["max"][1] == pytest.approx(opening / 1000, abs=1e-7)
            assert fingers["left"]["color"] == "e7eaf0" and fingers["right"]["color"] == "8b9098"
    if expected == "custom":
        assert out["themed"] == ["f8f0e0", "555e66"]
