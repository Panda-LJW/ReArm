import { element, svgElement } from "../../../widgets/dom.js";
import { workspaceBox } from "../../../state/workspace.js";

// 与观察画面共用工作台投影；没有拍照结果时明确标为等待状态。
export function capturePreview(doc, workspace) {
  const fragment = doc.createDocumentFragment();
  if (workspace?.image && workspace.props?.length) {
    const image = svgElement(doc, "svg", { viewBox: `0 0 ${workspace.image.width} ${workspace.image.height}`,
      role: "img", "aria-label": "工作台俯视图" });
    image.classList.add("library-workspace-preview");
    for (const prop of workspace.props.filter(prop => !prop.held)) {
      const [x, y, width, height] = workspaceBox(workspace, prop);
      const outline = prop.shape === "box" ? svgElement(doc, "rect", { x, y, width, height }) :
        svgElement(doc, "ellipse", { cx: x + width / 2, cy: y + height / 2, rx: width / 2, ry: height / 2 });
      const title = svgElement(doc, "title"); title.textContent = prop.name; outline.append(title); image.append(outline);
    }
    fragment.append(image);
  }
  const waiting = element(doc, "p", "c-chip br", "等待拍照"); waiting.setAttribute("role", "status");
  fragment.append(waiting); return fragment;
}
