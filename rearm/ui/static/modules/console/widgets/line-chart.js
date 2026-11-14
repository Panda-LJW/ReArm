import { frameView } from "../shell/view.js";
import { element, svgElement } from "./dom.js";

// 延续训练曲线的线性刻度与 1/2/5 取整；独立实现，不依赖旧页面。
export function niceTicks(maximum, threshold) {
  const limit = Math.max(2, ...[maximum, threshold].filter(Number.isFinite));
  const target = limit / 4, scale = 10 ** Math.max(0, Math.floor(Math.log10(target)));
  const step = [1, 2, 5, 10].map(v => v * scale).find(v => v >= target);
  const count = Math.ceil(limit / step);
  return { top: count * step, ticks: Array.from({ length: count + 1 }, (_, i) => i * step) };
}

export function mount(root) {
  const doc = root.ownerDocument, legend = element(doc, "div", "library-chart-legend");
  legend.append(element(doc, "span", "library-deviation-key", "偏差 · mm"));
  const thresholdLabel = element(doc, "span", "library-threshold-key"); legend.append(thresholdLabel);
  const plot = element(doc, "div", "library-chart-plot"), labels = element(doc, "div", "library-chart-ticks");
  const svg = svgElement(doc, "svg", { viewBox: "0 0 100 100", preserveAspectRatio: "none", "aria-hidden": true });
  const axis = element(doc, "div", "library-chart-axis"), empty = element(doc, "p", "library-muted", "—");
  plot.append(svg, labels, empty); root.append(legend, plot, axis); root.dataset.chart = "deviation";
  root.classList.add("library-chart"); root.setAttribute("role", "img");
  let previous;
  return frameView(({ rounds = [], threshold_mm: threshold } = {}) => {
    const key = JSON.stringify([rounds, threshold]); if (key === previous) return; previous = key;
    const rows = rounds.filter(r => Number.isFinite(r.deviation_mm));
    const { top, ticks } = niceTicks(Math.max(0, ...rows.map(r => r.deviation_mm)), threshold);
    thresholdLabel.textContent = Number.isFinite(threshold) ? `阈值 ${threshold.toFixed(1)} mm` : "阈值 —";
    svg.replaceChildren(); labels.replaceChildren(); axis.replaceChildren();
    empty.hidden = rows.length > 0;
    const y = value => 100 * (1 - value / top);
    const line = (attrs, cls) => {
      const el = svgElement(doc, "line", { ...attrs, "vector-effect": "non-scaling-stroke", class: cls });
      svg.append(el);
    };
    for (const tick of ticks) {
      line({ x1: 0, x2: 100, y1: y(tick), y2: y(tick) }, "library-chart-grid");
      const label = element(doc, "span", "", tick.toFixed(1)); label.style.top = `${y(tick)}%`; labels.append(label);
    }
    if (Number.isFinite(threshold)) line({ x1: 0, x2: 100, y1: y(threshold), y2: y(threshold) }, "library-chart-threshold");
    if (rows.length) {
      const x = i => rows.length === 1 ? 50 : i * 100 / (rows.length - 1);
      svg.append(svgElement(doc, "polyline", { points: rows.map((r, i) => `${x(i)},${y(r.deviation_mm)}`).join(" "),
        class: "library-chart-line", "vector-effect": "non-scaling-stroke" }));
      // 点用短线，避免非等比 SVG 缩放把圆点拉伸。
      rows.forEach((r, i) => line({ x1: x(i), x2: x(i), y1: y(r.deviation_mm), y2: y(r.deviation_mm) }, "library-chart-dot"));
      axis.append(element(doc, "span", "", `第 ${rows[0].round} 轮`));
      if (rows.length > 1) axis.append(element(doc, "span", "", `第 ${rows.at(-1).round} 轮`));
    }
    root.setAttribute("aria-label", `逐轮偏差：${rows.length ? rows.map(r => `第 ${r.round} 轮 ${r.deviation_mm.toFixed(1)} mm`).join("，") : "暂无记录"}；${thresholdLabel.textContent}`);
  }, () => root.replaceChildren(), doc.defaultView);
}
