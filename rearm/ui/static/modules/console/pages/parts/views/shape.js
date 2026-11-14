import { svgElement } from "../../../widgets/dom.js";

export function shape(doc, item, recipe = false) {
  const svg = svgElement(doc, "svg", { viewBox: "0 0 100 100", role: "img", "aria-label": `${item.name || "零件"}外形轮廓` });
  svg.classList.add("library-shape");
  const add = (tag, attrs) => svg.append(svgElement(doc, tag, attrs));
  if (recipe) {
    add("ellipse", { cx: 50, cy: 73, rx: 37, ry: 15 });
    add("path", { d: "M30 35 V65 C30 77 70 77 70 65 V35 M30 35 C30 23 70 23 70 35 C70 47 30 47 30 35 Z M45 29 V12 H55 V29" });
  } else if (item.outline?.length >= 3) {
    const xs = item.outline.map(p => p[0]), ys = item.outline.map(p => p[1]);
    const width = Math.max(...xs) - Math.min(...xs), height = Math.max(...ys) - Math.min(...ys);
    const scale = 76 / Math.max(1, width, height);
    add("polygon", { points: item.outline.map(p => [50 + (p[0] - Math.min(...xs) - width / 2) * scale,
      50 + (p[1] - Math.min(...ys) - height / 2) * scale].join(",")).join(" ") });
  } else if (item.shape === "box") {
    const sizes = item.size_mm || [1, 1], scale = 76 / Math.max(...sizes.slice(0, 2));
    add("rect", { x: 50 - sizes[0] * scale / 2, y: 50 - sizes[1] * scale / 2, width: sizes[0] * scale, height: sizes[1] * scale });
  } else add("circle", { cx: 50, cy: 50, r: 38 });
  if (!recipe && ["ring", "tube"].includes(item.shape)) add("circle", { cx: 50, cy: 50, r: 18 });
  return svg;
}
