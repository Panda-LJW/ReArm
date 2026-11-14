import { frameView } from "../../../shell/view.js";
import { productionSummary } from "../../../state/selectors.js";
import { mount as mountSparkline } from "../../../widgets/sparkline.js";
import { element } from "../../../widgets/dom.js";

export function mount(root) {
  const doc = root.ownerDocument, title = element(doc, "h2", "", "完成套数");
  const count = element(doc, "strong", "production-count", "0"); count.dataset.count = "sets";
  const pass = element(doc, "p", "production-pass", "一次通过率 ");
  const rate = element(doc, "span", "production-muted", "—"); rate.dataset.count = "pass-rate"; pass.append(rate);
  const trend = element(doc, "div", "production-trend"), caption = element(doc, "p", "production-muted", "最近检查偏差 · mm");
  root.append(title, count, pass, caption, trend); const sparkline = mountSparkline(trend);
  let runs;
  return frameView(state => {
    if (runs === state.runs) return;
    runs = state.runs;
    const summary = productionSummary(state); count.textContent = String(summary.sets);
    rate.textContent = summary.passRate === null ? "—" : `${Math.round(summary.passRate * 100)}%`;
    rate.className = summary.passRate === null ? "production-muted" : "";
    sparkline.render(summary.deviations.map(row => row.deviation_mm));
  }, () => { sparkline.dispose(); root.replaceChildren(); }, doc.defaultView);
}
