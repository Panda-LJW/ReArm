import { canvasContext, px, token } from "./canvas.js";
import { online, modeText, latestNode, number, element, preserve } from "./format.js";

const point = p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
function svgNode(tag, attrs, text = "") {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  el.textContent = text; return el;
}
export function mount(root) {
  const restore = preserve([root]);
  const img = root.querySelector("#camimg"), overlay = root.querySelector("#overlay"), stateChip = root.querySelector("#chipstate"), laser = root.querySelector("#chiplaser"), badge = root.querySelector("#chipver"), error = root.querySelector("#chiperr");
  root.classList.add("trainer-camera");
  root.querySelector(".camera-status").classList.add("trainer-camera-status");
  img.alt = "手眼相机画面"; img.removeAttribute("src");
  badge.className = "chip trainer-camera-badge";
  const legend = root.querySelector(".chip.legend"); legend.hidden = true;
  const canvas = element("canvas", "trainer-camera-canvas"); canvas.setAttribute("aria-label", "模拟手眼相机画面"); root.prepend(canvas);
  let stream = null, imageFailed = false;
  img.onerror = () => { imageFailed = true; img.hidden = true; };
  img.onload = () => { imageFailed = false; };
  return { dispose() { img.removeAttribute("src"); img.onload = img.onerror = null; restore(); }, render(state, summary) {
    const live = online(state), simulated = state.hello?.sim === true, result = latestNode(state);
    const url = live && state.hello?.camera?.url || null;
    if (url !== stream) { stream = url; imageFailed = false; if (url) img.src = url; else img.removeAttribute("src"); }
    img.hidden = !url || imageFailed; canvas.hidden = !!url && !imageFailed;
    root.classList.toggle("sim", simulated);
    stateChip.textContent = `${modeText(state)} · 手眼相机`;
    stateChip.className = "chip state " + (!live || ["estop", "fault"].includes(state.mode) ? "s-bad" : ["demo", "practice"].includes(state.mode) ? "s-busy" : "s-ok");
    laser.textContent = !live ? "激光 离线" : summary.laserMismatch ? "激光状态不一致" : state.laser ? `激光 ${state.laser.on ? "开" : "关"}` : "激光 未知";
    laser.className = "chip laser" + (state.laser?.on && live ? " laser-on" : "") + (summary.laserMismatch ? " trainer-mismatch" : "");
    badge.textContent = simulated ? "模拟" : ""; badge.hidden = !simulated;
    error.textContent = !live ? "离线" : result ? `偏差 ${number(result.dev_norm_mm)} mm` : "等待测量";
    error.className = "chip err " + (!live || result?.dev_norm_mm > summary.thresholdMm ? "s-bad" : result ? "s-ok" : "s-info");
    if (!canvas.hidden) {
      const { ctx: g, width: w, height: h } = canvasContext(canvas);
      g.fillStyle = token("--video"); g.fillRect(0, 0, w, h);
      if (simulated && live) {
        const offsetX = Math.sin(state.joint?.q?.[0] || 0) * w * .04, offsetY = Math.sin(state.joint?.q?.[1] || 0) * h * .04;
        const step = Math.max(w, h) / 12; g.strokeStyle = token("--grid"); g.lineWidth = 1; g.beginPath();
        for (let x = -step; x < w + step; x += step) { g.moveTo(x + offsetX, 0); g.lineTo(x + offsetX, h); }
        for (let y = -step; y < h + step; y += step) { g.moveTo(0, y + offsetY); g.lineTo(w, y + offsetY); } g.stroke();
      }
      g.font = `${px("--fs-lg")}px ${token("--sans")}`; g.fillStyle = token("--mute"); g.textAlign = "center";
      g.fillText(!live ? "离线" : simulated ? "模拟画面" : imageFailed ? "相机画面不可用" : "等待相机画面", w / 2, h / 2);
    }
    const width = img.naturalWidth || 640, height = img.naturalHeight || 480;
    overlay.setAttribute("viewBox", `0 0 ${width} ${height}`); overlay.replaceChildren();
    const reference = state.demo?.nodes?.find(node => node.id === result?.node)?.ref_spot_px;
    if (!live || !result || !point(result.spot_px) || !point(reference)) return;
    const [x, y] = result.spot_px, [rx, ry] = reference;
    const scale = Math.max(.01, Math.min(root.clientWidth / width, root.clientHeight / height));
    const radius = 4 / scale, angle = Math.atan2(y - ry, x - rx), size = 7 / scale;
    overlay.append(svgNode("line", { x1: rx, y1: ry, x2: x, y2: y, stroke: "var(--obs)", "stroke-width": 2 / scale }),
      svgNode("circle", { cx: rx, cy: ry, r: radius, fill: "none", stroke: "var(--pred)", "stroke-width": 2 / scale }),
      svgNode("circle", { cx: x, cy: y, r: radius, fill: "var(--obs)" }),
      svgNode("path", { d: `M${x - size * Math.cos(angle - .5)},${y - size * Math.sin(angle - .5)} L${x},${y} L${x - size * Math.cos(angle + .5)},${y - size * Math.sin(angle + .5)}`, fill: "none", stroke: "var(--obs)", "stroke-width": 2 / scale }));
    const label = svgNode("text", { x: Math.min(width - 120 / scale, Math.max(8 / scale, (x + rx) / 2 + 10 / scale)), y: Math.max(30 / scale, (y + ry) / 2 - 12 / scale), fill: "var(--text)", class: "num trainer-spot-label" }, `${number(result.dev_norm_mm)} mm`);
    label.style.fontSize = `calc(var(--fs-chart) / ${scale})`; overlay.append(label);
  } };
}
