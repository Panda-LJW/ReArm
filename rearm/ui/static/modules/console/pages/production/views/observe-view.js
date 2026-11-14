import { frameView } from "../../../shell/view.js";
import { workspaceBox } from "../../../state/workspace.js";
import { productionBusy } from "../../../state/selectors.js";
import { element, svgElement } from "../../../widgets/dom.js";
import { observationLayout, imageTransform } from "./observation-layout.js";

export function mount(root) {
  const doc = root.ownerDocument, title = element(doc, "h2", "c-card-head", "观察画面");
  const body = element(doc, "div", "production-observe-body c-card-body");
  const camera = element(doc, "div", "production-camera c-viewport");
  const feed = element(doc, "div", "production-camera-feed");
  const cameraStatus = element(doc, "span", "production-camera-status c-chip");
  cameraStatus.setAttribute("role", "status");
  const image = svgElement(doc, "svg", { role: "img", "aria-label": "工作台俯视图" });
  image.classList.add("production-observe");
  const scene = svgElement(doc, "g"), objects = svgElement(doc, "g"), boxes = svgElement(doc, "g"), leaders = svgElement(doc, "g");
  scene.append(objects, boxes); image.append(scene, leaders);
  const targets = element(doc, "ul", "production-targets");
  const result = element(doc, "p", "production-result", "尚未检查"); result.dataset.result = ""; result.setAttribute("aria-live", "polite");
  camera.append(feed, image, targets, cameraStatus); body.append(camera, result); root.append(title, body);
  let workspace, recognition, step, inspection, phase, latest, relayout = true;
  let media = null, disposed = false;
  const params = new URL(doc.defaultView.location.href).searchParams;
  let manualCamera = params.has("camera"), autoSource;
  function cameraState(message) {
    feed.hidden = !!message; objects.style.display = message ? "" : "none";
    cameraStatus.textContent = message; cameraStatus.hidden = !message;
    relayout = true; if (latest) view.render(latest);
  }
  function disconnectCamera() {
    if (!media) return;
    const previous = media; media = null;
    previous.onload = previous.onloadeddata = previous.onerror = null;
    if (previous.tagName === "VIDEO") {
      previous.pause();
      // 流由调用者持有，只解绑显示，不停止可能被其他视图共用的 tracks。
      previous.srcObject = null;
    }
    previous.removeAttribute("src");
    if (previous.tagName === "VIDEO") previous.load();
    feed.replaceChildren();
  }
  // type 可用 img/image/mjpeg/jpeg 或对应 MIME；其他类型走浏览器原生 video（含原生 HLS）。
  function setCameraSource(source) {
    if (disposed) return;
    disconnectCamera(); cameraState(source ? "摄像头连接中" : "未接入摄像头");
    if (!source) return;
    const Stream = doc.defaultView.MediaStream, isStream = typeof Stream === "function" && source instanceof Stream;
    const { url, type = "" } = typeof source === "string" ? { url: source } : source;
    const format = type.toLowerCase().split(";", 1)[0].trim();
    const isImage = !isStream && (format ? /^(img|image|mjpg|mjpeg|jpg|jpeg)$|^image\/|^multipart\/x-mixed-replace$/.test(format) :
      /\.(mjpg|mjpeg|jpe?g)$/i.test(new URL(url, doc.baseURI).pathname));
    const next = element(doc, isImage ? "img" : "video"); media = next;
    next.setAttribute("aria-label", "摄像头画面");
    const ready = () => { if (media === next) cameraState(""); };
    next.onerror = () => {
      if (media !== next) return;
      disconnectCamera(); cameraState("摄像头连接失败");
    };
    if (isImage) { next.alt = "摄像头画面"; next.onload = ready; }
    else {
      next.muted = next.defaultMuted = next.autoplay = next.playsInline = true;
      next.onloadeddata = ready;
    }
    feed.append(next);
    if (isStream) next.srcObject = source;
    else next.src = url;
  }
  function placeLabels() {
    const { width, height } = camera.getBoundingClientRect();
    if (!width || !height) return;
    const gap = parseFloat(doc.defaultView.getComputedStyle(camera).getPropertyValue("--sp-1")) || 4;
    const rows = [...targets.children], sizes = rows.map(label => {
      const { width, height } = label.getBoundingClientRect(); return { width, height };
    });
    const statusHeight = cameraStatus.hidden ? 0 : cameraStatus.getBoundingClientRect().height + gap;
    const { plot, labels } = observationLayout(width, height - statusHeight, sizes, gap);
    const transform = imageTransform(plot, workspace.image);
    // 媒体与识别框共用图像坐标区，给上下标签留出原有空间。
    Object.assign(feed.style, { left: `${transform.x}px`, top: `${transform.y}px`,
      width: `${workspace.image.width * transform.scale}px`, height: `${workspace.image.height * transform.scale}px` });
    image.setAttribute("viewBox", `0 0 ${width} ${height}`);
    scene.setAttribute("transform", `translate(${transform.x} ${transform.y}) scale(${transform.scale})`);
    leaders.replaceChildren(...rows.flatMap((label, i) => {
      const at = labels[i], target = recognition.targets[Number(label.dataset.targetIndex)];
      const prop = workspace.props.find(item => item.id === target.id);
      label.style.left = `${at.left}px`; label.style.top = `${at.top}px`;
      const box = prop ? workspaceBox(workspace, prop) : target.box_px;
      if (!box) return [];
      const [x, y, w, h] = box;
      return [svgElement(doc, "line", { x1: transform.x + (x + w / 2) * transform.scale,
        y1: transform.y + (y + h / 2) * transform.scale, x2: at.left + at.width / 2,
        y2: at.top < plot.top ? at.top + at.height : at.top, "data-target-leader": target.id })];
    }));
    relayout = false;
  }
  const view = frameView(state => {
    latest = state;
    if (!manualCamera && state.device) {
      const source = state.link.online ? state.device.camera?.url || null : null;
      if (source !== autoSource) { autoSource = source; setCameraSource(source); }
    }
    camera.dataset.busy = String(productionBusy(state));
    if (workspace !== state.workspace) {
      workspace = state.workspace; relayout = true;
      objects.replaceChildren(...workspace.props.filter(prop => !prop.held).map(prop => {
        const [x, y, width, height] = workspaceBox(workspace, prop);
        const shape = prop.shape === "box" ? svgElement(doc, "rect", { x, y, width, height }) :
          svgElement(doc, "ellipse", { cx: x + width / 2, cy: y + height / 2, rx: width / 2, ry: height / 2 });
        shape.dataset.object = prop.id; shape.dataset.kind = prop.kind;
        const name = svgElement(doc, "title"); name.textContent = prop.name; shape.append(name); return shape;
      }));
    }
    if (recognition !== state.recognition || step !== state.step || phase !== state.phase) {
      recognition = state.recognition; step = state.step; phase = state.phase; relayout = true;
      // 框属于观察位拍下的那一帧；离开识别阶段后不把旧框冒充实时检测。
      boxes.replaceChildren(...(phase === "recognize" || recognition?.live ? recognition?.targets || [] : []).filter(target => target.box_px).map(target => {
        const [x, y, width, height] = target.box_px;
        const rect = svgElement(doc, "rect", { x, y, width, height }); rect.dataset.targetBox = target.id; return rect;
      }));
      targets.replaceChildren(...(recognition?.targets || []).map((target, index) => {
        const row = element(doc, "li"); row.dataset.target = target.id; row.dataset.targetIndex = index;
        row.append(element(doc, "span", "", target.name));
        if (Number.isFinite(target.confidence)) row.append(element(doc, "span", "", `${Math.round(target.confidence * 100)}%`));
        if (phase === "pick" && step?.action === "pick" && step.status === "started" &&
            step.part_id === target.id && Number.isFinite(step.angle_deg)) {
          const angle = element(doc, "span", "", `${step.angle_deg.toFixed(1)}°`); angle.dataset.angle = ""; row.append(angle);
        }
        return row;
      }));
      targets.hidden = !recognition;
    }
    if (relayout) placeLabels();
    if (inspection !== state.inspection) {
      inspection = state.inspection;
      result.textContent = !inspection ? "尚未检查" : inspection.ok ? "到位" : `偏差 ${inspection.deviation_mm.toFixed(1)} mm`;
      result.dataset.outcome = !inspection ? "empty" : inspection.ok ? "ok" : "deviation";
    }
  }, () => { disposed = true; disconnectCamera(); observer?.disconnect(); root.replaceChildren(); }, doc.defaultView);
  const observer = doc.defaultView.ResizeObserver ? new doc.defaultView.ResizeObserver(() => {
    relayout = true; if (latest) view.render(latest);
  }) : null;
  observer?.observe(camera);
  view.setCameraSource = source => { manualCamera = true; setCameraSource(source); };
  setCameraSource(params.get("camera"));
  return view;
}
