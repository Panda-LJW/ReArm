import { frameView } from "../shell/view.js";
import { element, svgElement } from "./dom.js";
import { millimeters } from "./format.js";

export function mount(root) {
  const doc = root.ownerDocument, empty = element(doc, "span", "production-muted", "—");
  const chart = svgElement(doc, "svg", { viewBox: "0 0 300 48", role: "img", preserveAspectRatio: "none" });
  chart.classList.add("production-sparkline");
  const value = element(doc, "span", "production-trend-value"); value.hidden = true;
  const line = svgElement(doc, "polyline"), dot = svgElement(doc, "circle", { r: 3 });
  chart.append(line, dot); root.append(empty, chart, value);
  return frameView(values => {
    const rows = (values || []).filter(Number.isFinite);
    empty.hidden = rows.length > 0; chart.style.display = rows.length ? "" : "none";
    const single = rows.length === 1;
    root.dataset.single = String(single); value.hidden = !single;
    value.textContent = single ? millimeters(rows[0]) : "";
    chart.setAttribute("viewBox", single ? "0 0 24 48" : "0 0 300 48");
    line.style.display = single ? "none" : "";
    if (!rows.length) return;
    const top = Math.max(1, ...rows), point = (v, i) => single ? [12, 24] : [6 + i * 288 / (rows.length - 1), 42 - v / top * 36];
    line.setAttribute("points", rows.map((v, i) => point(v, i).join(",")).join(" "));
    const last = point(rows.at(-1), rows.length - 1);
    dot.setAttribute("cx", last[0]); dot.setAttribute("cy", last[1]);
    chart.setAttribute("aria-label", `最近 ${rows.length} 套检查偏差：${rows.map(v => v.toFixed(1)).join("、")} mm`);
  }, () => root.replaceChildren(), doc.defaultView);
}
