// 数字孪生对外的唯一入口。
//   const twin = await createTwin(element);  twin.update(frame);  twin.dispose();
// frame 是 datasource 模块定义的 JointFrame；优先使用六轴 q_rad，否则使用旧 angles_deg。
// 孪生只按收到的关节角画姿态，不关心数据来自仿真、面板还是真实下位机。
import { ARM_CONFIG } from "./arm-config.js";
import { panelToUrdf } from "./kinematics.js";
import { checkJoints, forwardUrdf, endPoses, laserRay, frustumCorners } from "../arm/fk.js";

const MODE = {
  live: { text: "实时", icon: "●", cls: "ok" },
  sim: { text: "模拟数据", icon: "◆", cls: "sim" },
  offline: { text: "离线", icon: "✕", cls: "off" },
  waiting: { text: "等待数据", icon: "…", cls: "wait" },
};
const signed = v => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(1) + "°";

// 拷贝输入，避免调用方后续改数组影响已显示的叠加；无效路径点断段。
const copyPoint = p => Array.isArray(p) && p.length === 3 && Array.from(p).every(Number.isFinite) ? [...p] : null;
function copyPath(segments = []) {
  const out = [];
  for (const samples of segments) {
    let segment = null;
    for (const sample of samples) {
      const p = copyPoint(sample?.p);
      if (!p) { segment = null; continue; }
      if (!segment) { segment = []; out.push(segment); }
      segment.push({ t: sample.t, p });
    }
  }
  return out;
}
function copyOverlay(value = {}) {
  const spots = value.spots || {};
  return {
    demoPath: copyPath(value.demoPath || []), runPath: copyPath(value.runPath || []),
    nodes: (value.nodes || []).flatMap(node => {
      const p = copyPoint(node.p); return p ? [{ id: node.id, p, current: node.current === true }] : [];
    }),
    laser: typeof value.laser?.on === "boolean" ? { on: value.laser.on } : null,
    spots: { measured: copyPoint(spots.measured), reference: copyPoint(spots.reference),
      deviation_mm: Number.isFinite(spots.deviation_mm) ? spots.deviation_mm : null },
  };
}

// gripper: "custom"（默认，自制矩形指）| "official"（官方尖头指）。
export async function createTwin(container, { config = ARM_CONFIG, forceFallback = false, skin = true, gripper = "custom", view = "arm" } = {}) {
  container.classList.add("twin");
  container.innerHTML = `<div class="twin-stage"></div><div class="twin-status" role="status"></div><div class="twin-labels" aria-hidden="true"></div><div class="twin-note"></div>`;
  const stage = container.querySelector(".twin-stage"), statusEl = container.querySelector(".twin-status"), labelsEl = container.querySelector(".twin-labels"), noteEl = container.querySelector(".twin-note");

  let scene, renderer = "webgl";
  try {
    if (forceFallback) throw new Error("fallback requested");
    scene = (await import("./scene.js")).createScene(stage, config, { view });
  } catch (error) {
    stage.replaceChildren(); renderer = "2d";
    scene = (await import("./fallback2d.js")).createScene(stage, config);
  }
  container.dataset.renderer = renderer;
  scene.canvas.setAttribute("role", "img");
  if (renderer === "webgl") scene.canvas.title = "拖动旋转，滚轮缩放，双击复位";

  const legacyDriven = config.panelMapping.map(m => config.joints.find(j => j.id === m.joint));
  let driven = legacyDriven, labels = [], axes = 3, overlay = copyOverlay(), overlayLabels = [];
  // J1、J2 离得近：J1 的标签放左侧，其余放右侧，既不互相压住，也不挡左上角的状态提示
  function makeLabels() {
    labelsEl.replaceChildren();
    labels = driven.map((j, i) => {
      const el = document.createElement("div"); el.className = "twin-label";
      el.dataset.side = i === 0 || (axes === 6 && i % 2 === 0) ? "left" : "right";
      labelsEl.appendChild(el); return el;
    });
    makeOverlayLabels();
  }
  function makeOverlayLabels() {
    for (const { el } of overlayLabels) el.remove();
    overlayLabels = [];
    // 2D 退路只存储叠加，不画标记或标签。
    if (renderer === "2d") return;
    const add = (className, text, p, current = false) => {
      const el = document.createElement("div"); el.className = className; el.textContent = text;
      el.dataset.current = String(current); labelsEl.appendChild(el); overlayLabels.push({ el, p });
    };
    for (const node of overlay.nodes) add("twin-node-label", String(node.id), node.p, node.current);
    const { measured, reference, deviation_mm } = overlay.spots;
    if (measured && reference && deviation_mm !== null) {
      add("twin-dev-label", `偏差 ${deviation_mm.toFixed(1)} mm`, measured.map((v, i) => (v + reference[i]) / 2));
    }
  }
  makeLabels();

  // 当前显示的读数向目标读数平滑靠拢；没有目标前停在配置的初始姿态。
  let shown = null, goal = null, mode = "waiting", laser = null, raf = 0, disposed = false, dirty = true;
  // 明确的 JointFrame 激光状态优先；没提供时允许独立 overlay 激光事件。
  const laserState = () => laser ?? overlay.laser?.on ?? false;
  let jointError = "", gripperMm = null;
  // 系统设置了“减少动态效果”时不做过渡，直接到位
  const calm = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const restView = [0, 40, -100];

  function draw() {
    raf = 0; if (disposed) return;
    let moving = false;
    if (goal) {
      if (!shown) shown = [...goal];
      const tolerance = axes === 6 ? 0.02 * Math.PI / 180 : 0.02;
      shown = shown.map((v, i) => { const d = goal[i] - v; if (calm || Math.abs(d) < tolerance) return goal[i]; moving = true; return v + d * 0.18; });
    }
    const pose = shown || restView, offline = mode === "offline" || mode === "waiting";
    const options = { laserOn: laserState() && !offline, dimmed: offline, gripperMm, axes };
    if (axes === 6) scene.setPoseMatrices(forwardUrdf(config, pose), { ...options,
      endPoses: endPoses(config, pose), laserRay: laserRay(config, pose), frustumCorners: frustumCorners(config, pose, 0.18) });
    else scene.setPose(panelToUrdf(config, pose), options);
    scene.render();
    const degrees = pose.map(v => axes === 6 ? v * 180 / Math.PI : v);
    labels.forEach((el, i) => {
      const at = scene.project(driven[i].id);
      el.hidden = !at; if (!at) return;
      el.style.left = Math.round(at[0]) + "px"; el.style.top = Math.round(at[1]) + "px";
      el.textContent = shown ? `${driven[i].label.split(" ")[0]} ${signed(degrees[i])}` : driven[i].label.split(" ")[0];
    });
    if (axes === 6 || overlayLabels.length) placeLabels();
    scene.canvas.setAttribute("aria-label", shown ? `机械臂三维姿态：${driven.map((j, i) => `${j.label} ${degrees[i].toFixed(1)} 度`).join("，")}。数据状态：${MODE[mode].text}` : `机械臂三维模型，${MODE[mode].text}`);
    dirty = false;
    if (moving) schedule();
  }
  function schedule() { dirty = true; if (!raf && !disposed) raf = requestAnimationFrame(draw); }

  // 六轴标签按实际尺寸避让；优先贴近关节，在左右偏移的基础上找最近的空行。
  function placeLabels() {
    const placed = [], w = stage.clientWidth, h = stage.clientHeight, gap = 5;
    const entries = [...labels.map((el, i) => ({ el, at: scene.project(driven[i].id) })),
      ...overlayLabels.map(({ el, p }) => ({ el, at: scene.projectPoint(p) }))];
    for (const { el, at } of entries) {
      el.hidden = !at;
      if (!at) continue;
      const width = el.offsetWidth, height = el.offsetHeight;
      const x = Math.max(gap, Math.min(w - width - gap, at[0] + (el.dataset.side === "left" ? -width - 14 : 14)));
      const minY = 44, maxY = Math.max(minY, h - height - 30);
      const desired = Math.max(minY, Math.min(maxY, at[1] - height / 2));
      const candidates = [desired, minY, maxY, ...placed.flatMap(p => [p.y + p.height + gap, p.y - height - gap])]
        .filter(y => y >= minY && y <= maxY).sort((a, b) => Math.abs(a - desired) - Math.abs(b - desired));
      const y = candidates.find(y => placed.every(p => x + width + gap <= p.x || p.x + p.width + gap <= x || y + height + gap <= p.y || p.y + p.height + gap <= y)) ?? desired;
      el.style.transform = "none"; el.style.left = Math.round(x) + "px"; el.style.top = Math.round(y) + "px";
      placed.push({ x, y, width, height });
    }
  }

  function renderStatus() {
    const m = MODE[mode];
    statusEl.className = "twin-status " + m.cls;
    statusEl.innerHTML = `<i aria-hidden="true">${m.icon}</i><span>${m.text}</span>`;
    noteEl.textContent = jointError || (mode === "offline" ? "数据中断，显示最后一次姿态" : mode === "waiting" ? "还没有关节数据" : "");
    noteEl.style.textAlign = jointError ? "right" : "";
    container.dataset.mode = mode;
  }

  // 视角交互：拖动旋转，滚轮缩放，双击复位
  let drag = null;
  const canvas = scene.canvas;
  canvas.addEventListener("pointerdown", e => { drag = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener("pointermove", e => { if (!drag) return; scene.orbit(-(e.clientX - drag[0]) * 0.008, (e.clientY - drag[1]) * 0.006); drag = [e.clientX, e.clientY]; schedule(); });
  canvas.addEventListener("pointerup", () => { drag = null; });
  canvas.addEventListener("pointercancel", () => { drag = null; });
  canvas.addEventListener("wheel", e => { e.preventDefault(); scene.zoom(e.deltaY > 0 ? 1.08 : 0.93); schedule(); }, { passive: false });
  canvas.addEventListener("dblclick", () => { scene.resetView(); schedule(); });
  const observer = new ResizeObserver(() => { scene.resize(); schedule(); });
  observer.observe(stage);

  renderStatus(); schedule();
  // 真实外形是锦上添花：后台加载，成功就换上，失败（文件缺失、无 WebGL）保持简化外形。
  let skinState = "simple", gripperState = "simple";
  if (skin && scene.loadSkin) scene.loadSkin(new URL("./meshes/b601.json", import.meta.url), { gripper }).then(selected => {
    if (disposed) return;
    skinState = "mesh"; gripperState = selected;
    container.dataset.skin = "mesh"; container.dataset.gripper = selected; schedule();
  }, () => { skinState = "simple"; });
  container.dataset.skin = skinState;
  container.dataset.gripper = gripperState;
  return {
    renderer,
    // 喂一帧关节数据。字段缺失时保持原值，所以数据源可以只发变化的部分。
    update(frame = {}) {
      if (disposed) return;
      let accepted = true;
      if (frame.q_rad != null) {
        const checked = checkJoints(config, frame.q_rad), valid = frame.valid;
        const invalidAxis = valid === undefined ? -1 : Array.from({ length: 6 }, (_, i) => i)
          .findIndex(i => !Array.isArray(valid) || valid.length !== 6 || valid[i] !== true);
        if (!checked.ok || invalidAxis >= 0) {
          const issue = checked.issues[0], joint = issue ? config.joints.find(j => j.id === issue.joint) : config.joints[invalidAxis];
          const reason = issue ? ({ missing: "缺测", nan: "非有限数值", out_of_range: "越界" }[issue.kind]) : "无效";
          jointError = "关节数据无效：" + (joint ? `${joint.label.split(" ")[0]} ${reason}` : "需要 6 轴数据");
          // 连尚未结束的显示插值也停下，保持无效帧到达时的姿态。
          if (axes === 6 && !shown) {
            const rest = panelToUrdf(config, restView);
            shown = config.joints.map(j => rest[j.id]);
          }
          goal = shown ? [...shown] : null; accepted = false;
        } else {
          if (axes !== 6) {
            const current = panelToUrdf(config, shown || restView);
            shown = shown ? config.joints.map(j => current[j.id]) : null;
            axes = 6; driven = config.joints; makeLabels();
          }
          goal = [...frame.q_rad]; jointError = "";
        }
      } else if (Array.isArray(frame.angles_deg) && frame.angles_deg.length >= legacyDriven.length && frame.angles_deg.every(Number.isFinite)) {
        if (axes !== 3) { axes = 3; driven = legacyDriven; shown = null; makeLabels(); }
        goal = frame.angles_deg.slice(0, driven.length); jointError = "";
      }
      if (accepted && Number.isFinite(frame.gripper_mm)) {
        const [lo, hi] = config.gripper.openingMm;
        if (frame.gripper_mm >= lo && frame.gripper_mm <= hi) gripperMm = frame.gripper_mm;
      }
      if (typeof frame.laser === "boolean") laser = frame.laser;
      const next = frame.online === false ? "offline" : MODE[frame.mode] ? frame.mode
        : frame.online === true && (mode === "offline" || mode === "waiting") ? "live" : mode;
      mode = next; renderStatus();
      schedule();
    },
    // 整体替换；所有字段可缺省，null 清空。坐标都是 base_link 下的 m。
    setOverlay(value) {
      if (disposed) return;
      overlay = copyOverlay(value || {}); scene.setOverlay(overlay); makeOverlayLabels(); schedule();
    },
    // 供测试和调试读取当前显示状态
    state: () => ({ mode, shown: shown ? [...shown] : null, goal: goal ? [...goal] : null,
      q_rad: axes === 6 ? (shown ? [...shown] : null) : config.joints.map(j => panelToUrdf(config, shown || restView)[j.id]),
      axes, laser: laserState(), renderer, dirty, skin: skinState, gripper: gripperState, view,
      overlay: { demoPoints: overlay.demoPath.reduce((n, s) => n + s.length, 0),
        runPoints: overlay.runPath.reduce((n, s) => n + s.length, 0), nodes: overlay.nodes.length,
        hasSpots: !!(overlay.spots.measured || overlay.spots.reference) } }),
    refreshTheme() { scene.applyTheme(); schedule(); },
    dispose() { disposed = true; cancelAnimationFrame(raf); observer.disconnect(); scene.dispose(); container.replaceChildren(); container.classList.remove("twin"); },
  };
}
