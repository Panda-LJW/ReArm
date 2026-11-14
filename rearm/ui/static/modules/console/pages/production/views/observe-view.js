import { frameView } from "../../../shell/view.js";
import { workspaceBox } from "../../../state/workspace.js";
import { element, svgElement } from "../../../widgets/dom.js";

export function mount(root) {
  const doc = root.ownerDocument, title = element(doc, "h2", "", "观察画面");
  const camera = element(doc, "div", "production-camera");
  const image = svgElement(doc, "svg", { viewBox: "0 0 640 480", role: "img", "aria-label": "工作台俯视图" });
  image.classList.add("production-observe");
  const objects = svgElement(doc, "g"), boxes = svgElement(doc, "g"), leaders = svgElement(doc, "g"); image.append(objects, boxes, leaders);
  const targets = element(doc, "ul", "production-targets");
  const result = element(doc, "p", "production-result", "—"); result.dataset.result = ""; result.setAttribute("aria-live", "polite");
  camera.append(image, targets); root.append(title, camera, result);
  let workspace, recognition, step, inspection, phase, latest, relayout = true;
  // 标签按实际文字尺寸避让，连线保留标签与目标的对应关系；字号不跟图像缩小。
  function placeLabels() {
    const { width, height } = camera.getBoundingClientRect();
    if (!width || !height) return;
    const gap = parseFloat(doc.defaultView.getComputedStyle(camera).getPropertyValue("--sp-1")) || 0;
    const placed = [], lines = [];
    for (const label of targets.children) {
      const prop = workspace.props.find(item => item.id === label.dataset.target);
      const target = recognition.targets.find(item => item.id === label.dataset.target);
      const [x, y, w, h] = prop ? workspaceBox(workspace, prop) : target.box_px;
      const px = (x + w / 2) / workspace.image.width * width, py = (y + h / 2) / workspace.image.height * height;
      const box = label.getBoundingClientRect(), maxX = Math.max(gap, width - box.width - gap), maxY = Math.max(gap, height - box.height - gap);
      const clampX = value => Math.max(gap, Math.min(maxX, value)), clampY = value => Math.max(gap, Math.min(maxY, value));
      const xs = [clampX(px), clampX(px - box.width), gap, maxX];
      const ys = [clampY(py - box.height - gap), clampY(py + gap), gap, maxY,
        ...placed.flatMap(p => [clampY(p.top - box.height - gap), clampY(p.top + p.height + gap)])];
      const candidates = xs.flatMap(left => ys.map(top => ({ left, top, width: box.width, height: box.height })))
        .sort((a, b) => Math.hypot(a.left - px, a.top - py) - Math.hypot(b.left - px, b.top - py));
      const at = candidates.find(a => placed.every(b => a.left + a.width + gap <= b.left || b.left + b.width + gap <= a.left ||
        a.top + a.height + gap <= b.top || b.top + b.height + gap <= a.top)) || candidates[0];
      placed.push(at); label.style.left = `${at.left}px`; label.style.top = `${at.top}px`;
      lines.push(svgElement(doc, "line", { x1: x + w / 2, y1: y + h / 2,
        x2: (at.left + at.width / 2) / width * workspace.image.width, y2: (at.top + at.height / 2) / height * workspace.image.height,
        "data-target-leader": label.dataset.target }));
    }
    leaders.replaceChildren(...lines); relayout = false;
  }
  const view = frameView(state => {
    latest = state;
    if (workspace !== state.workspace) {
      workspace = state.workspace; relayout = true;
      image.setAttribute("viewBox", `0 0 ${workspace.image.width} ${workspace.image.height}`);
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
      boxes.replaceChildren(...(phase === "recognize" ? recognition?.targets || [] : []).map(target => {
        const [x, y, width, height] = target.box_px;
        const rect = svgElement(doc, "rect", { x, y, width, height }); rect.dataset.targetBox = target.id; return rect;
      }));
      targets.replaceChildren(...(recognition?.targets || []).map(target => {
        const row = element(doc, "li"); row.dataset.target = target.id;
        row.append(element(doc, "span", "", target.name), element(doc, "span", "", `${Math.round(target.confidence * 100)}%`));
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
      result.textContent = !inspection ? "—" : inspection.ok ? "到位" : `偏差 ${inspection.deviation_mm.toFixed(1)} mm`;
      result.dataset.outcome = !inspection ? "empty" : inspection.ok ? "ok" : "deviation";
    }
  }, () => { observer?.disconnect(); root.replaceChildren(); }, doc.defaultView);
  const observer = doc.defaultView.ResizeObserver ? new doc.defaultView.ResizeObserver(() => {
    relayout = true; if (latest) view.render(latest);
  }) : null;
  observer?.observe(camera);
  return view;
}
