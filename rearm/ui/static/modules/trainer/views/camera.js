import { canvasContext, px, token } from "./canvas.js";
import { online, modeText, latestNode, number, element, preserve } from "./format.js";
import { CONFIG } from "../config.js";

const point = p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
const positive = value => Number.isFinite(value) && value > 0;
export function thresholdStatus(result, hello, config = CONFIG) {
  const thresholdMm = hello?.threshold_mm ?? config.thresholdMm ?? CONFIG.thresholdMm;
  if (result?.valid !== true || !Number.isFinite(result.dev_norm_mm) || result.dev_norm_mm < 0
      || !Number.isFinite(thresholdMm) || thresholdMm < 0) return null;
  const inside = result.dev_norm_mm <= thresholdMm;
  return { thresholdMm, inside, color: inside ? "var(--cyan)" : "var(--bad)" };
}
// rPx 使用相机坐标；scale 是相机像素到屏幕 CSS 像素的比例（含留黑边）。
export function thresholdRing(result, refPx, hello, config = CONFIG, viewport = {}) {
  const status = thresholdStatus(result, hello, config);
  if (!status || !point(result.spot_px) || !point(refPx)) return null;
  const width = viewport.width ?? hello?.camera?.width ?? 640;
  const height = viewport.height ?? hello?.camera?.height ?? 480, scale = viewport.scale ?? 1;
  if (![width, height, scale].every(positive)) return null;
  const distance = Math.hypot(result.spot_px[0] - refPx[0], result.spot_px[1] - refPx[1]);
  let pxPerMm = distance / result.dev_norm_mm;
  if (result.dev_norm_mm < .5 || distance < 2 || !positive(pxPerMm)) {
    if (!positive(hello?.camera?.width) || !positive(result.depth_mm)) return null;
    pxPerMm = hello.camera.width / (2 * Math.tan(87 * Math.PI / 360) * result.depth_mm);
  }
  if (!positive(pxPerMm)) return null;
  const rPx = Math.min(Math.min(width, height) * .4, Math.max(12 / scale, status.thresholdMm * pxPerMm));
  return { cx: refPx[0], cy: refPx[1], rPx, inside: status.inside };
}
const invalidReasons = new Map([["spot_not_found", "未找到光点"], ["depth_invalid", "深度无效"], ["timeout", "测量超时"]]);
const overlaps = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
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
  // HTML 浮层的字号直接使用屏幕 CSS 像素，不受 SVG viewBox 缩放。
  const label = element("span", "num trainer-spot-label"); label.hidden = true; root.append(label);
  const invalid = element("span", "trainer-measurement-status"); invalid.hidden = true;
  invalid.setAttribute("role", "status"); root.append(invalid);
  let stream = null, imageFailed = false;
  img.onerror = () => { imageFailed = true; img.hidden = true; };
  img.onload = () => { imageFailed = false; };
  return { dispose() { img.removeAttribute("src"); img.onload = img.onerror = null; restore(); }, render(state, summary) {
    const live = online(state), simulated = state.hello?.sim === true, result = latestNode(state);
    const status = thresholdStatus(result, state.hello);
    const invalidText = result?.valid === false ? invalidReasons.get(result.invalid_reason) ?? "测量无效" : "";
    invalid.textContent = invalidText; invalid.hidden = !live || !invalidText;
    const url = live && state.hello?.camera?.url || null;
    if (url !== stream) { stream = url; imageFailed = false; if (url) img.src = url; else img.removeAttribute("src"); }
    img.hidden = !url || imageFailed; canvas.hidden = !!url && !imageFailed;
    root.classList.toggle("sim", simulated);
    stateChip.textContent = `${modeText(state)} · 手眼相机`;
    stateChip.className = "chip state " + (!live || ["estop", "fault"].includes(state.mode) ? "s-bad" : ["demo", "practice"].includes(state.mode) ? "s-busy" : "s-ok");
    laser.textContent = !live ? "激光 离线" : summary.laserMismatch ? "激光状态不一致" : state.laser ? `激光 ${state.laser.on ? "开" : "关"}` : "激光 未知";
    laser.className = "chip laser" + (state.laser?.on && live ? " laser-on" : "") + (summary.laserMismatch ? " trainer-mismatch" : "");
    badge.textContent = simulated ? "模拟" : ""; badge.hidden = !simulated;
    error.textContent = !live ? "离线" : invalidText ? "测量无效" : result ? `偏差 ${number(result.dev_norm_mm)} mm` : "等待测量";
    error.className = "chip err " + (!live || invalidText || status?.inside === false ? "s-bad" : status ? "s-ok" : "s-info");
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
      // 激光光点落在画面中心略偏下，说明文字放到上方三分之一处，避免和光点标签挤在一起。
      g.fillText(!live ? "离线" : simulated ? "模拟画面" : imageFailed ? "相机画面不可用" : "等待相机画面", w / 2, simulated && live ? h * 0.3 : h / 2);
    }
    const width = img.naturalWidth || state.hello?.camera?.width || 640, height = img.naturalHeight || state.hello?.camera?.height || 480;
    overlay.setAttribute("viewBox", `0 0 ${width} ${height}`); overlay.replaceChildren();
    label.hidden = true;
    const reference = state.demo?.nodes?.find(node => node.id === result?.node)?.ref_spot_px;
    if (!live || !status || !point(result.spot_px) || !point(reference)) return;
    const [x, y] = result.spot_px, [rx, ry] = reference;
    const bounds = root.getBoundingClientRect(), frame = overlay.getBoundingClientRect();
    const scale = Math.max(.01, Math.min(frame.width / width, frame.height / height));
    const ox = (frame.left ?? 0) - (bounds.left ?? 0) + (frame.width - width * scale) / 2;
    const oy = (frame.top ?? 0) - (bounds.top ?? 0) + (frame.height - height * scale) / 2;
    const chips = [stateChip, laser, badge, error].filter(el => !el.hidden).map(el => {
      const rect = el.getBoundingClientRect();
      return { left: rect.left - bounds.left - 8, right: rect.right - bounds.left + 8,
        top: rect.top - bounds.top - 8, bottom: rect.bottom - bounds.top + 8 };
    });
    const radius = 4 / scale, angle = Math.atan2(y - ry, x - rx), size = 7 / scale;
    const ring = thresholdRing(result, reference, state.hello, CONFIG, { width, height, scale });
    if (ring) overlay.append(svgNode("circle", { class: "trainer-threshold-ring", cx: ring.cx, cy: ring.cy, r: ring.rPx,
      fill: "none", stroke: status.color, "stroke-width": 2 / scale, "stroke-dasharray": `${6 / scale} ${4 / scale}` }));
    const spots = [
      svgNode("circle", { cx: rx, cy: ry, r: radius, fill: "none", stroke: "var(--pred)", "stroke-width": 2 / scale }),
      svgNode("circle", { cx: x, cy: y, r: radius, fill: status.color }),
    ];
    overlay.append(svgNode("line", { x1: rx, y1: ry, x2: x, y2: y, stroke: status.color, "stroke-width": 2 / scale }),
      ...spots,
      svgNode("path", { d: `M${x - size * Math.cos(angle - .5)},${y - size * Math.sin(angle - .5)} L${x},${y} L${x - size * Math.cos(angle + .5)},${y - size * Math.sin(angle + .5)}`, fill: "none", stroke: status.color, "stroke-width": 2 / scale }));
    // 极端外部坐标不伪移光点；被芯片遮挡的标记隐藏，文字换到另一侧。
    spots.forEach((circle, i) => {
      const cx = ox + [rx, x][i] * scale, cy = oy + [ry, y][i] * scale;
      if (chips.some(chip => overlaps({ left: cx - 4, right: cx + 4, top: cy - 4, bottom: cy + 4 }, chip))) circle.setAttribute("visibility", "hidden");
    });
    label.textContent = `${status.inside ? "" : "▲ "}偏差 ${number(result.dev_norm_mm)} mm（阈值 ${status.thresholdMm}）`; label.hidden = false;
    const sizeRect = label.getBoundingClientRect(), lw = sizeRect.width, lh = sizeRect.height;
    const cx = ox + (x + rx) / 2 * scale, cy = oy + (y + ry) / 2 * scale, gap = 10;
    const candidates = [[cx + gap, cy - lh - gap], [cx - lw - gap, cy - lh - gap],
      [cx + gap, cy + gap], [cx - lw - gap, cy + gap],
      ...chips.flatMap(chip => [[chip.left - lw - gap, cy], [chip.right + gap, cy], [cx, chip.bottom + gap], [cx, chip.top - lh - gap]])];
    const positions = candidates.map(([left, top]) => ({
      left: Math.max(8, Math.min(bounds.width - lw - 8, left)), top: Math.max(8, Math.min(bounds.height - lh - 8, top)),
    }));
    const placement = positions.find(p => !chips.some(chip => overlaps({ ...p, right: p.left + lw, bottom: p.top + lh }, chip)));
    if (!placement) { label.hidden = true; return; }
    label.style.left = `${placement.left}px`; label.style.top = `${placement.top}px`;
  } };
}
