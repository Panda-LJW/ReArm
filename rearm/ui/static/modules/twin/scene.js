// three.js 渲染：把 kinematics.forward() 给出的连杆位姿画出来。不读页面状态，不知道数据从哪来。
import * as THREE from "../../vendor/three.module.min.js";
import { forward, position } from "./kinematics.js";

const cssVar = (el, name, fallback) => getComputedStyle(el).getPropertyValue(name).trim() || fallback;

function palette(el) {
  return {
    body: cssVar(el, "--twin-body", "#3a4250"), plate: cssVar(el, "--twin-plate", "#aab3c0"),
    joint: cssVar(el, "--twin-joint", "#3d8bff"), finger: cssVar(el, "--twin-finger", "#e7eaf0"),
    finger2: cssVar(el, "--twin-finger-2", "#8b9098"),
    edge: cssVar(el, "--twin-edge", "#7c8798"), grid: cssVar(el, "--twin-grid", "#2c323c"),
    laser: cssVar(el, "--twin-laser", "#ff6a4d"), pedestal: cssVar(el, "--twin-pedestal", "#1b2028"),
    skinDark: cssVar(el, "--twin-skin-dark", "#39414e"), skinDarker: cssVar(el, "--twin-skin-darker", "#262c35"),
    skinMetal: cssVar(el, "--twin-skin-metal", "#cdd4de"), skinTrim: cssVar(el, "--twin-skin-trim", "#8f99a8"),
  };
}

export function createScene(container, config) {
  const canvas = document.createElement("canvas");
  canvas.className = "twin-canvas";
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  container.appendChild(canvas);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 20);
  camera.up.set(0, 0, 1); // 与 URDF 一致：Z 向上
  scene.add(new THREE.HemisphereLight(0xffffff, 0x1a1f28, 1.5));
  const key = new THREE.DirectionalLight(0xffffff, 2.2);
  key.position.set(0.8, -1.2, 1.6);
  scene.add(key);

  const materials = {}, edgeMaterial = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.55 });
  for (const name of ["body", "plate", "joint", "finger", "pedestal"]) materials[name] = new THREE.MeshStandardMaterial({ roughness: 0.62, metalness: name === "plate" ? 0.55 : 0.2 });
  // 真实外形（压缩网格）用的材质：平面着色，省掉法线数据，也让机加工件的棱面更清楚
  for (const name of ["skinDark", "skinDarker", "skinMetal", "skinTrim", "skinPlate", "skinFinger", "skinFinger2"]) materials[name] = new THREE.MeshStandardMaterial({ roughness: 0.7, metalness: /Metal|Plate/.test(name) ? 0.5 : 0.15, flatShading: true });
  // 网格材质映射；自制夹指按照片一白一灰，颜色仍由 CSS 主题控制。
  const SKIN = { matte_black: "skinDark", hardware_black: "skinDarker", anodized_grey: "skinPlate", carriage_grey: "skinPlate", metal: "skinMetal", rack_metal: "skinMetal", silver_trim: "skinMetal", seeed_yellow: "skinTrim", travel_stop_yellow: "skinTrim", finger_black: "skinFinger", finger_white: "skinFinger", finger_grey: "skinFinger2" };
  const THEME = { skinPlate: "plate", skinFinger: "finger", skinFinger2: "finger2" };
  const gridMaterial = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.8 });
  const laserMaterial = new THREE.LineBasicMaterial({ transparent: true });
  const spotMaterial = new THREE.MeshBasicMaterial({ transparent: true });

  // 小工具：造一个带描边的零件并挂到 group 上。
  function part(group, geometry, material, at = [0, 0, 0], rotate = null) {
    const mesh = new THREE.Mesh(geometry, materials[material]);
    mesh.userData.simple = material !== "pedestal"; // 简化外形的零件；换上真实外形后隐藏
    mesh.position.set(...at);
    if (rotate) mesh.rotation.set(...rotate);
    mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 30), edgeMaterial));
    group.add(mesh);
    return mesh;
  }
  const box = (group, size, material, at, rotate) => part(group, new THREE.BoxGeometry(...size), material, at, rotate);
  // 圆柱默认沿 Y 轴；axis 指定它在连杆坐标系里应沿哪根轴。
  const ROT = { x: [0, 0, Math.PI / 2], y: null, z: [Math.PI / 2, 0, 0] };
  const cylinder = (group, radius, length, axis, material, at) => part(group, new THREE.CylinderGeometry(radius, radius, length, 40), material, at, ROT[axis]);
  // 侧板：在连杆 XY 平面内从 a 连到 b，两端带圆头，厚度沿 Z。
  function plate(group, a, b, width, z, thickness) {
    const dx = b[0] - a[0], dy = b[1] - a[1], length = Math.hypot(dx, dy);
    box(group, [length, width, thickness], "plate", [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z], [0, 0, Math.atan2(dy, dx)]);
    for (const end of [a, b]) cylinder(group, width / 2, thickness, "z", "plate", [end[0], end[1], z]);
  }

  const shape = config.shape, joints = config.joints, next = id => joints[joints.findIndex(j => j.id === id) + 1].xyz;
  const world = new THREE.Group();
  world.position.z = 0; scene.add(world);
  const links = {};
  const frame = id => { const g = new THREE.Group(); g.matrixAutoUpdate = false; world.add(g); links[id] = g; return g; };

  // 安装台与地面网格
  const lift = config.scene.pedestalHeight;
  if (lift > 0) box(world, [shape.basePlate[0] + 0.04, shape.basePlate[1] + 0.04, lift], "pedestal", [0, 0, -lift / 2]);
  const grid = new THREE.GridHelper(2.4, 24);
  grid.rotation.x = Math.PI / 2; grid.position.z = -lift; grid.material = gridMaterial; world.add(grid);

  // 底座（固定）
  box(world, shape.basePlate, "body", [0, 0, shape.basePlate[2] / 2]);
  cylinder(world, shape.baseRadius, shape.baseHeight, "z", "body", [0, 0, shape.baseHeight / 2]);
  cylinder(world, shape.baseRadius + 0.002, 0.008, "z", "joint", [0, 0, shape.baseHeight - 0.004]);

  // link1：转台 + 肩关节电机（J2 轴沿本连杆 Y）
  const l1 = frame("joint1"), j2 = next("joint1");
  box(l1, [0.07, 0.078, 0.03], "plate", [0.005, 0, 0.015]);
  cylinder(l1, shape.motorRadiusLarge, 0.060, "y", "body", [j2[0], 0, j2[2]]);
  for (const side of [-1, 1]) box(l1, [0.05, 0.004, 0.07], "plate", [j2[0], side * 0.036, 0.04]);

  // link2：大臂双侧板 + 肘关节电机
  const l2 = frame("joint2"), j3 = next("joint2"), ua = shape.upperArm, midUpper = (ua.zNear + ua.zFar) / 2;
  for (const z of [ua.zNear, ua.zFar]) plate(l2, [0, 0], j3, ua.width, z, shape.plateThickness);
  cylinder(l2, shape.motorRadiusLarge, 0.008, "z", "joint", [0, 0, ua.zNear + 0.006]);
  cylinder(l2, shape.motorRadiusLarge, 0.052, "z", "body", [j3[0], j3[1], midUpper]);
  box(l2, [0.10, 0.03, 0.05], "body", [j3[0] / 2, 0, midUpper]);

  // link3：小臂双侧板（带偏置）+ 腕俯仰电机
  const l3 = frame("joint3"), j4 = next("joint3"), fa = shape.foreArm, midFore = (fa.zNear + fa.zFar) / 2;
  for (const z of [fa.zNear, fa.zFar]) plate(l3, [0, 0], j4, fa.width, z, shape.plateThickness);
  cylinder(l3, shape.motorRadiusLarge, 0.008, "z", "joint", [0, 0, fa.zNear + 0.006]);
  cylinder(l3, shape.motorRadiusSmall, 0.050, "z", "body", [j4[0], j4[1], midFore]);
  box(l3, [0.09, 0.026, 0.046], "body", [j4[0] / 2, j4[1] / 2, midFore], [0, 0, Math.atan2(j4[1], j4[0])]);

  // link4：腕部支架 + 腕偏摆电机（J5 轴沿本连杆 Y）
  const l4 = frame("joint4"), j5 = next("joint4");
  box(l4, [j5[0] + 0.02, 0.05, 0.05], "plate", [j5[0] / 2, -0.012, j5[2]]);
  cylinder(l4, shape.motorRadiusSmall, 0.05, "y", "body", [j5[0], j5[1] - 0.025, j5[2]]);

  // link5：U 形支架（J6 轴沿本连杆 X）
  const l5 = frame("joint5"), j6 = next("joint5");
  box(l5, [0.05, 0.066, 0.07], "plate", [0, 0, j6[2]]);

  // link6：腕旋转电机
  const l6 = frame("joint6");
  cylinder(l6, shape.motorRadiusSmall + 0.002, 0.05, "z", "body", [0, 0, 0.025]);

  // 末端：导轨 + 两根夹指（工具坐标系 +X 为指向）
  const tool = frame("tool"), rail = shape.gripperRail, finger = shape.finger;
  const slidingParts = [];
  let openingMm = finger.opening * 1000;
  function slidePart(mesh, mount, center = [0, 0, 0]) {
    mesh.rotation.set(...mount.rpy);
    slidingParts.push({ mesh, mount, center });
  }
  function setOpening(value) {
    if (Number.isFinite(value)) openingMm = value;
    for (const { mesh, mount, center } of slidingParts) {
      mesh.position.set(...mount.xyz.map((v, i) => v + center[i] + mount.axis[i] * openingMm / 2000));
    }
  }
  box(tool, rail.size, "body", rail.center);
  for (const mount of config.gripper.fingers) {
    slidePart(box(tool, [finger.length, finger.thickness, finger.height], "finger"), mount,
      [-finger.length / 2, mount.axis[1] * finger.thickness / 2, 0]);
  }
  setOpening(openingMm);

  // 激光束：从工具原点沿工具 +X 打到地面
  const laserGeometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
  const laser = new THREE.Line(laserGeometry, laserMaterial); world.add(laser);
  const spot = new THREE.Mesh(new THREE.CircleGeometry(0.012, 24), spotMaterial); world.add(spot);

  function applyTheme() {
    const p = palette(container);
    for (const name of Object.keys(materials)) materials[name].color.set(p[THEME[name] || name]);
    edgeMaterial.color.set(p.edge); gridMaterial.color.set(p.grid); laserMaterial.color.set(p.laser); spotMaterial.color.set(p.laser);
  }

  // 视角：绕目标点的方位角/仰角/距离
  const view = { azimuth: config.scene.cameraAzimuthDeg * Math.PI / 180, elevation: config.scene.cameraElevationDeg * Math.PI / 180, distance: config.scene.cameraDistance };
  const home = { ...view }, target = new THREE.Vector3(...config.scene.cameraTarget);
  function placeCamera() {
    const c = Math.cos(view.elevation);
    camera.position.set(target.x + view.distance * c * Math.cos(view.azimuth), target.y + view.distance * c * Math.sin(view.azimuth), target.z + view.distance * Math.sin(view.elevation));
    camera.lookAt(target);
  }

  let lastFrames = null;
  function setPose(urdfAngles, options = {}) {
    setPoseMatrices(forward(config, urdfAngles), options);
  }
  // 六轴入口直接使用已算好的矩阵，禁止再调用带限位夹取的旧 forward。
  function setPoseMatrices({ frames, end_link: toolMatrix }, { laserOn = false, dimmed = false, gripperMm = null } = {}) {
    lastFrames = { ...frames, tool: toolMatrix };
    for (const [id, matrix] of Object.entries(lastFrames)) { links[id].matrix.set(...matrix); links[id].matrixWorldNeedsUpdate = true; }
    setOpening(gripperMm);
    const origin = position(toolMatrix), dir = [toolMatrix[0], toolMatrix[4], toolMatrix[8]], floor = -lift;
    const reach = dir[2] < -1e-3 ? (floor - origin[2]) / dir[2] : 0, hit = reach > 0 && reach < 3;
    laser.visible = spot.visible = hit;
    if (hit) {
      const end = origin.map((v, i) => v + dir[i] * reach);
      laserGeometry.setFromPoints([new THREE.Vector3(...origin), new THREE.Vector3(...end)]);
      spot.position.set(end[0], end[1], floor + 0.001);
    }
    laserMaterial.opacity = laserOn ? 1 : 0.28; spotMaterial.opacity = laserOn ? 1 : 0.35;
    for (const m of Object.values(materials)) { m.transparent = dimmed; m.opacity = dimmed ? 0.45 : 1; }
  }

  // 把关节原点投影成容器内的像素坐标，供标签定位。
  function project(id) {
    if (!lastFrames || !lastFrames[id]) return null;
    const v = new THREE.Vector3(...position(lastFrames[id])).project(camera);
    return [(v.x + 1) / 2 * canvas.clientWidth, (1 - v.y) / 2 * canvas.clientHeight];
  }

  // 换上真实外形：读清单和二进制顶点，挂到各自的连杆坐标系下。失败就保持简化外形。
  let skinned = false, disposed = false;
  async function readSkin(manifestUrl, custom = false) {
    const response = await fetch(manifestUrl);
    if (response.ok === false) throw new Error("外形清单不可用");
    const manifest = await response.json();
    if (manifest.units !== "m" || !Array.isArray(manifest.parts)) throw new Error("外形清单格式错误");
    if (custom && (manifest.parts.length !== 2 || !["left", "right"].every(side =>
      manifest.parts.some(p => p.side === side && p.frame === "tool" && ["finger_white", "finger_grey"].includes(p.material))))) {
      throw new Error("自制夹指必须包含左右两个部件");
    }
    const binary = await fetch(new URL(manifestUrl.href.replace(/\.json$/, ".bin")));
    if (binary.ok === false) throw new Error("外形网格不可用");
    const buffer = await binary.arrayBuffer();
    const added = [];
    try {
      for (const item of manifest.parts) {
        const group = item.frame === "base" ? world : links[item.frame];
        if (!group || !SKIN[item.material]) continue;
        for (const key of ["positions", "indices"]) {
          const block = item[key];
          if (!block || !Number.isInteger(block.offset) || block.offset < 0 || block.offset % 4 ||
              !Number.isInteger(block.count) || block.count <= 0 || block.count % 3 || block.offset + block.count * 4 > buffer.byteLength) {
            throw new Error("外形网格数据不完整");
          }
        }
        const positions = new Float32Array(buffer, item.positions.offset, item.positions.count);
        const indices = new Uint32Array(buffer, item.indices.offset, item.indices.count);
        if (!positions.every(Number.isFinite) || indices.some(i => i >= positions.length / 3)) throw new Error("外形网格索引错误");
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        geometry.setIndex(new THREE.BufferAttribute(indices, 1));
        const mesh = new THREE.Mesh(geometry, materials[SKIN[item.material]]);
        mesh.userData.skin = item;
        mesh.userData.bakedInEndLink = custom;
        added.push([group, mesh, item]);
      }
      if (!added.length) throw new Error("外形文件里没有可用的零件");
      return added;
    } catch (error) {
      for (const [, mesh] of added) mesh.geometry.dispose();
      throw error;
    }
  }
  async function loadSkin(manifestUrl, { gripper = "custom" } = {}) {
    let added = await readSkin(manifestUrl), selected = "official";
    if (gripper !== "official") {
      try {
        const custom = await readSkin(new URL("gripper.json", manifestUrl), true);
        // 两根自制指完整就绪后才移除官方尖头指；滑块、齿条、限位块全部保留。
        added = added.filter(([, mesh, item]) => {
          if (item.material !== "finger_black") return true;
          mesh.geometry.dispose(); return false;
        }).concat(custom);
        selected = "custom";
      } catch {
        // 自制文件缺失、HTTP/解析失败或损坏：静默保留已加载的官方夹指。
        selected = "official";
      }
    }
    if (disposed) {
      for (const [, mesh] of added) mesh.geometry.dispose();
      return selected;
    }
    world.traverse(o => { if (o.userData.simple) o.visible = false; });
    for (const [group, mesh, item] of added) {
      const mount = config.gripper.fingers.find(f => f.side === item.side);
      // 自制网格已在 end_link 零开口坐标系，只叠加与滑块相同的 ±Y 行程。
      if (mount) slidePart(mesh, mesh.userData.bakedInEndLink
        ? { ...mount, xyz: [0, 0, 0], rpy: [0, 0, 0] } : mount);
      group.add(mesh);
    }
    setOpening(openingMm);
    skinned = true;
    return selected;
  }

  function resize() {
    const w = Math.max(1, container.clientWidth), h = Math.max(1, container.clientHeight);
    renderer.setSize(w, h, false); camera.aspect = w / h;
    // 竖窄容器里按宽度收视野，保证整条臂都在画面里
    camera.fov = w / h < 1 ? 30 / Math.max(0.55, w / h) : 30; camera.updateProjectionMatrix();
  }
  function render() { placeCamera(); renderer.render(scene, camera); }

  applyTheme(); resize();
  return {
    canvas, setPose, setPoseMatrices, project, resize, render, applyTheme, loadSkin, isSkinned: () => skinned,
    orbit(dAzimuth, dElevation) { view.azimuth += dAzimuth; view.elevation = Math.min(1.35, Math.max(-0.1, view.elevation + dElevation)); },
    zoom(factor) { view.distance = Math.min(3, Math.max(0.7, view.distance * factor)); },
    resetView() { Object.assign(view, home); },
    dispose() {
      disposed = true;
      scene.traverse(o => { o.geometry?.dispose(); });
      for (const m of [...Object.values(materials), edgeMaterial, gridMaterial, laserMaterial, spotMaterial]) m.dispose();
      renderer.dispose(); canvas.remove();
    },
  };
}
