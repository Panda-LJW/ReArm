// 数字孪生对外的唯一入口。
//   const twin = await createTwin(element);  twin.update(frame);  twin.dispose();
// frame 是 datasource 模块定义的 JointFrame：{ angles_deg, mode, online, laser }。
// 孪生只按收到的关节角画姿态，不关心数据来自仿真、面板还是真实下位机。
import { ARM_CONFIG } from "./arm-config.js";
import { panelToUrdf } from "./kinematics.js";

const MODE = {
  live: { text: "实时", icon: "●", cls: "ok" },
  sim: { text: "模拟数据", icon: "◆", cls: "sim" },
  offline: { text: "离线", icon: "✕", cls: "off" },
  waiting: { text: "等待数据", icon: "…", cls: "wait" },
};
const signed = v => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(1) + "°";

export async function createTwin(container, { config = ARM_CONFIG, forceFallback = false, skin = true } = {}) {
  container.classList.add("twin");
  container.innerHTML = `<div class="twin-stage"></div><div class="twin-status" role="status"></div><div class="twin-labels" aria-hidden="true"></div><div class="twin-note"></div>`;
  const stage = container.querySelector(".twin-stage"), statusEl = container.querySelector(".twin-status"), labelsEl = container.querySelector(".twin-labels"), noteEl = container.querySelector(".twin-note");

  let scene, renderer = "webgl";
  try {
    if (forceFallback) throw new Error("fallback requested");
    scene = (await import("./scene.js")).createScene(stage, config);
  } catch (error) {
    stage.replaceChildren(); renderer = "2d";
    scene = (await import("./fallback2d.js")).createScene(stage, config);
  }
  container.dataset.renderer = renderer;
  scene.canvas.setAttribute("role", "img");
  if (renderer === "webgl") scene.canvas.title = "拖动旋转，滚轮缩放，双击复位";

  const driven = config.panelMapping.map(m => config.joints.find(j => j.id === m.joint));
  // J1、J2 离得近：J1 的标签放左侧，其余放右侧，既不互相压住，也不挡左上角的状态提示
  const labels = driven.map((j, i) => { const el = document.createElement("div"); el.className = "twin-label"; el.dataset.side = i === 0 ? "left" : "right"; labelsEl.appendChild(el); return el; });

  // 当前显示的读数向目标读数平滑靠拢；没有目标前停在配置的初始姿态。
  let shown = null, goal = null, mode = "waiting", laser = false, raf = 0, disposed = false, dirty = true;
  // 系统设置了“减少动态效果”时不做过渡，直接到位
  const calm = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const restView = [0, 40, -100];

  function draw() {
    raf = 0; if (disposed) return;
    let moving = false;
    if (goal) {
      if (!shown) shown = [...goal];
      shown = shown.map((v, i) => { const d = goal[i] - v; if (calm || Math.abs(d) < 0.02) return goal[i]; moving = true; return v + d * 0.18; });
    }
    const pose = shown || restView, offline = mode === "offline" || mode === "waiting";
    scene.setPose(panelToUrdf(config, pose), { laserOn: laser && !offline, dimmed: offline });
    scene.render();
    labels.forEach((el, i) => {
      const at = scene.project(driven[i].id);
      el.hidden = !at; if (!at) return;
      el.style.left = Math.round(at[0]) + "px"; el.style.top = Math.round(at[1]) + "px";
      el.textContent = shown ? `${driven[i].label.split(" ")[0]} ${signed(shown[i])}` : driven[i].label.split(" ")[0];
    });
    scene.canvas.setAttribute("aria-label", shown ? `机械臂三维姿态：${driven.map((j, i) => `${j.label} ${shown[i].toFixed(1)} 度`).join("，")}。数据状态：${MODE[mode].text}` : `机械臂三维模型，${MODE[mode].text}`);
    dirty = false;
    if (moving) schedule();
  }
  function schedule() { dirty = true; if (!raf && !disposed) raf = requestAnimationFrame(draw); }

  function renderStatus() {
    const m = MODE[mode];
    statusEl.className = "twin-status " + m.cls;
    statusEl.innerHTML = `<i aria-hidden="true">${m.icon}</i><span>${m.text}</span>`;
    noteEl.textContent = mode === "offline" ? "数据中断，显示最后一次姿态" : mode === "waiting" ? "还没有关节数据" : "";
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
  let skinState = "simple";
  if (skin && scene.loadSkin) scene.loadSkin(new URL("./meshes/b601.json", import.meta.url)).then(() => { skinState = "mesh"; container.dataset.skin = "mesh"; schedule(); }, () => { skinState = "simple"; });
  container.dataset.skin = skinState;
  return {
    renderer,
    // 喂一帧关节数据。字段缺失时保持原值，所以数据源可以只发变化的部分。
    update(frame = {}) {
      if (disposed) return;
      if (Array.isArray(frame.angles_deg) && frame.angles_deg.length >= driven.length && frame.angles_deg.every(Number.isFinite)) goal = frame.angles_deg.slice(0, driven.length);
      if (typeof frame.laser === "boolean") laser = frame.laser;
      const next = frame.online === false ? "offline" : MODE[frame.mode] ? frame.mode : mode;
      if (next !== mode) { mode = next; renderStatus(); }
      schedule();
    },
    // 供测试和调试读取当前显示状态
    state: () => ({ mode, shown: shown ? [...shown] : null, goal: goal ? [...goal] : null, laser, renderer, dirty, skin: skinState }),
    refreshTheme() { scene.applyTheme(); schedule(); },
    dispose() { disposed = true; cancelAnimationFrame(raf); observer.disconnect(); scene.dispose(); container.replaceChildren(); container.classList.remove("twin"); },
  };
}
