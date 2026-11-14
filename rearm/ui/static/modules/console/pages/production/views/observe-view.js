import { frameView } from "../../../shell/view.js";
import { workspaceBox } from "../../../state/workspace.js";
import { element, svgElement } from "../../../widgets/dom.js";
import { observationLayout, imageTransform } from "./observation-layout.js";

export function mount(root) {
  const doc = root.ownerDocument, title = element(doc, "h2", "", "观察画面");
  const camera = element(doc, "div", "production-camera");
  const image = svgElement(doc, "svg", { role: "img", "aria-label": "工作台俯视图" });
  image.classList.add("production-observe");
  const scene = svgElement(doc, "g"), objects = svgElement(doc, "g"), boxes = svgElement(doc, "g"), leaders = svgElement(doc, "g");
  scene.append(objects, boxes); image.append(scene, leaders);
  const targets = element(doc, "ul", "production-targets");
  const result = element(doc, "p", "production-result", "尚未检查"); result.dataset.result = ""; result.setAttribute("aria-live", "polite");
  camera.append(image, targets); root.append(title, camera, result);
  let workspace, recognition, step, inspection, phase, latest, relayout = true;
  function placeLabels() {
    const { width, height } = camera.getBoundingClientRect();
    if (!width || !height) return;
    const gap = parseFloat(doc.defaultView.getComputedStyle(camera).getPropertyValue("--sp-1")) || 4;
    const rows = [...targets.children], sizes = rows.map(label => {
      const { width, height } = label.getBoundingClientRect(); return { width, height };
    });
    const { plot, labels } = observationLayout(width, height, sizes, gap);
    const transform = imageTransform(plot, workspace.image);
    image.setAttribute("viewBox", `0 0 ${width} ${height}`);
    scene.setAttribute("transform", `translate(${transform.x} ${transform.y}) scale(${transform.scale})`);
    leaders.replaceChildren(...rows.map((label, i) => {
      const at = labels[i], target = recognition.targets.find(item => item.id === label.dataset.target);
      const prop = workspace.props.find(item => item.id === target.id);
      const [x, y, w, h] = prop ? workspaceBox(workspace, prop) : target.box_px;
      label.style.left = `${at.left}px`; label.style.top = `${at.top}px`;
      return svgElement(doc, "line", { x1: transform.x + (x + w / 2) * transform.scale,
        y1: transform.y + (y + h / 2) * transform.scale, x2: at.left + at.width / 2,
        y2: at.top < plot.top ? at.top + at.height : at.top, "data-target-leader": target.id });
    }));
    relayout = false;
  }
  const view = frameView(state => {
    latest = state;
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
      result.textContent = !inspection ? "尚未检查" : inspection.ok ? "到位" : `偏差 ${inspection.deviation_mm.toFixed(1)} mm`;
      result.dataset.outcome = !inspection ? "empty" : inspection.ok ? "ok" : "deviation";
    }
  }, () => { observer?.disconnect(); root.replaceChildren(); }, doc.defaultView);
  const observer = doc.defaultView.ResizeObserver ? new doc.defaultView.ResizeObserver(() => {
    relayout = true; if (latest) view.render(latest);
  }) : null;
  observer?.observe(camera);
  return view;
}
