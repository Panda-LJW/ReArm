// 道具契约：size_m 为外包围盒 XYZ 尺寸，pose 为 base_link 下的中心 XYZ（m）。
// ring/tube 的孔径暂取外径的 55%；取得模型后只替换本层几何，不改变调用者。
const SHAPES = new Set(["disc", "post", "ring", "tube", "box"]);
const vector = v => Array.isArray(v) && v.length === 3 && Array.from(v).every(Number.isFinite);
export function copyProps(value = []) {
  if (!Array.isArray(value)) throw new TypeError("道具必须是数组");
  const ids = new Set();
  return value.map(prop => {
    if (!prop || typeof prop.id !== "string" || !prop.id || ids.has(prop.id) || !SHAPES.has(prop.shape)
      || !vector(prop.size_m) || prop.size_m.some(v => v <= 0) || !vector(prop.pose)) {
      throw new TypeError("道具需要唯一 id、有效外形、正尺寸和中心坐标");
    }
    ids.add(prop.id);
    return { id: prop.id, shape: prop.shape, size_m: [...prop.size_m], pose: [...prop.pose], held: prop.held === true };
  });
}

// 使用场景已有的 Three 和材质；仅 setProps 后建立这一层，默认场景不变。
export function createPropsLayer(THREE, world, materials, edgeMaterial) {
  const group = new THREE.Group(); group.name = "props"; world.add(group);
  const entries = new Map();
  let tcp = null;
  function geometry({ shape, size_m: [x, y, z] }) {
    if (shape === "box") return new THREE.BoxGeometry(x, y, z);
    if (shape === "disc" || shape === "post") {
      const g = new THREE.CylinderGeometry(0.5, 0.5, z, 40);
      g.rotateX(Math.PI / 2); g.scale(x, y, 1); return g;
    }
    const outline = new THREE.Shape(), hole = new THREE.Path();
    outline.absarc(0, 0, 0.5, 0, Math.PI * 2, false);
    hole.absarc(0, 0, 0.275, 0, Math.PI * 2, true); outline.holes.push(hole);
    const g = new THREE.ExtrudeGeometry(outline, { depth: z, bevelEnabled: false, curveSegments: 20, steps: 1 });
    g.scale(x, y, 1); g.translate(0, 0, -z / 2); return g;
  }
  const atPose = prop => new THREE.Matrix4().makeTranslation(...prop.pose);
  function release(entry) {
    entry.mesh.traverse(o => o.geometry?.dispose()); group.remove(entry.mesh);
  }
  function place(entry) {
    if (entry.prop.held && tcp) {
      // 抓住时保存相对 TCP 的位姿，后续同时跟随平移和旋转，不在每帧重新吸附。
      if (!entry.local) entry.local = tcp.clone().invert().multiply(atPose(entry.prop));
      entry.mesh.matrix.multiplyMatrices(tcp, entry.local);
    } else entry.mesh.matrix.copy(atPose(entry.prop));
    entry.mesh.matrixWorldNeedsUpdate = true;
  }
  return {
    setProps(props) {
      const ids = new Set(props.map(prop => prop.id));
      for (const [id, entry] of entries) if (!ids.has(id)) { release(entry); entries.delete(id); }
      for (const prop of props) {
        let entry = entries.get(prop.id);
        if (entry && (entry.prop.shape !== prop.shape || entry.prop.size_m.some((v, i) => v !== prop.size_m[i]))) {
          release(entry); entries.delete(prop.id); entry = null;
        }
        if (!entry) {
          const mesh = new THREE.Mesh(geometry(prop), materials[prop.shape === "disc" ? "body" : "plate"]);
          mesh.name = prop.id; mesh.userData.propId = prop.id; mesh.matrixAutoUpdate = false;
          mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry, 30), edgeMaterial));
          entry = { prop, mesh, local: null }; entries.set(prop.id, entry); group.add(mesh);
        }
        if (prop.held !== entry.prop.held || prop.pose.some((v, i) => v !== entry.prop.pose[i])) entry.local = null;
        entry.prop = prop; place(entry);
      }
    },
    update(matrix) { tcp = new THREE.Matrix4().set(...matrix); for (const entry of entries.values()) place(entry); },
  };
}
