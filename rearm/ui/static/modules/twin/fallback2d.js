// 没有 WebGL 时的退路：用 2D 画布画侧视简图。接口与 scene.js 相同，孪生主体不用区分。
import { forward, position } from "./kinematics.js";

export function createScene(container, config) {
  const canvas = document.createElement("canvas");
  canvas.className = "twin-canvas";
  container.appendChild(canvas);
  const g = canvas.getContext("2d"), css = n => getComputedStyle(container).getPropertyValue(n).trim();
  let pose = null, options = {}, points = {}, size = [1, 1];
  const chain = [...config.joints.map(j => j.id), "tool"];

  function resize() {
    const d = Math.min(devicePixelRatio || 1, 2);
    size = [Math.max(1, container.clientWidth), Math.max(1, container.clientHeight)];
    canvas.width = size[0] * d; canvas.height = size[1] * d; g.setTransform(d, 0, 0, d, 0, 0);
  }
  function setPose(urdfAngles, opts = {}) {
    setPoseMatrices(forward(config, urdfAngles), opts);
  }
  function setPoseMatrices({ frames, end_link }, opts = {}) {
    pose = { ...frames, tool: end_link }; options = opts;
  }
  function render() {
    const [w, h] = size; g.clearRect(0, 0, w, h);
    if (!pose) return;
    // 侧视：横轴取到底座轴线的水平距离（带方向），纵轴取高度
    const yaw = Math.atan2(position(pose.tool)[1], position(pose.tool)[0]), lift = config.scene.pedestalHeight;
    const scale = Math.min(w / 0.95, h / (0.72 + lift)), ox = w * 0.22, oy = h - 12 - lift * scale;
    const to = p => [ox + (p[0] * Math.cos(yaw) + p[1] * Math.sin(yaw)) * scale, oy - p[2] * scale];
    g.globalAlpha = options.dimmed ? 0.45 : 1;
    g.strokeStyle = css("--twin-grid") || "#2c323c"; g.lineWidth = 1;
    g.beginPath(); g.moveTo(0, oy + lift * scale); g.lineTo(w, oy + lift * scale); g.stroke();
    g.fillStyle = css("--twin-pedestal") || "#1b2028"; g.fillRect(ox - 40, oy, 80, lift * scale);
    let prev = to([0, 0, 0]); points = {};
    g.lineCap = "round"; g.lineJoin = "round"; g.strokeStyle = css("--twin-plate") || "#aab3c0"; g.lineWidth = 9;
    g.beginPath(); g.moveTo(...prev);
    for (const id of chain) { const p = to(position(pose[id])); points[id] = p; g.lineTo(...p); }
    g.stroke();
    g.fillStyle = css("--twin-joint") || "#3d8bff";
    for (const id of chain.slice(0, options.axes === 6 ? 6 : 3)) { g.beginPath(); g.arc(...points[id], 7, 0, 7); g.fill(); }
    if (options.axes === 6 || Number.isFinite(options.gripperMm)) {
      const m = pose.tool, opening = Number.isFinite(options.gripperMm) ? options.gripperMm / 1000 : config.shape.finger.opening;
      const transform = p => [0, 1, 2].map(r => m[r * 4 + 3] + p.reduce((sum, v, c) => sum + m[r * 4 + c] * v, 0));
      g.strokeStyle = css("--twin-finger") || "#e7eaf0"; g.lineWidth = 4;
      for (const mount of config.gripper.fingers) {
        const at = mount.xyz.map((v, i) => v + mount.axis[i] * (opening + config.shape.finger.thickness) / 2);
        g.beginPath(); g.moveTo(...to(transform(at)));
        g.lineTo(...to(transform([at[0] - config.shape.finger.length, at[1], at[2]]))); g.stroke();
      }
    }
    g.globalAlpha = 1;
  }
  resize();
  return { canvas, setPose, setPoseMatrices, setOverlay() {}, projectPoint: () => null,
    project: id => points[id] || null, resize, render, applyTheme() {}, orbit() {}, zoom() {}, resetView() {}, dispose() { canvas.remove(); } };
}
