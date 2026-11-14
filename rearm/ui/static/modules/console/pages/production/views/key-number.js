import { frameView } from "../../../shell/view.js";
import { productionSummary } from "../../../state/selectors.js";
import { mount as mountSparkline } from "../../../widgets/sparkline.js";
import { element } from "../../../widgets/dom.js";
import { duration } from "../../../widgets/format.js";

// 只切换展示属性，数值变化的短暂强调由 CSS 完成。
function displayValue(node, value) {
  if (node.textContent === value) return;
  node.textContent = value;
  node.dataset.flash = node.dataset.flash === "a" ? "b" : "a";
}

export function mount(root) {
  const doc = root.ownerDocument, title = element(doc, "h2", "c-kpi-label", "完成套数");
  const count = element(doc, "strong", "production-count c-kpi-value", "0"); count.dataset.count = "sets";
  const completed = element(doc, "div", "production-kpi c-kpi"); completed.append(title, count);
  const pass = element(doc, "p", "production-pass production-kpi c-kpi");
  pass.append(element(doc, "span", "c-kpi-label", "一次通过率 "));
  const rate = element(doc, "span", "production-muted", "—"); rate.dataset.count = "pass-rate"; pass.append(rate);
  const deviation = element(doc, "div", "production-kpi c-kpi"), latest = element(doc, "strong", "c-kpi-value", "—");
  const trend = element(doc, "div", "production-trend"), caption = element(doc, "p", "production-muted c-kpi-label", "最近检查偏差 · mm");
  deviation.append(caption, latest, trend);
  const elapsed = element(doc, "div", "production-kpi c-kpi"), time = element(doc, "strong", "c-kpi-value", "—");
  elapsed.append(element(doc, "span", "c-kpi-label", "最近一套用时"), time);
  root.append(completed, pass, deviation, elapsed); const sparkline = mountSparkline(trend);
  let runs;
  return frameView(state => {
    if (runs === state.runs) return;
    runs = state.runs;
    const summary = productionSummary(state); displayValue(count, String(summary.sets));
    displayValue(rate, summary.passRate === null ? "—" : `${Math.round(summary.passRate * 100)}%`);
    rate.className = summary.passRate === null ? "production-muted" : "";
    const last = state.runs.at(-1);
    displayValue(latest, Number.isFinite(last?.deviation_mm) ? last.deviation_mm.toFixed(1) : "—");
    displayValue(time, duration(last?.duration_ms));
    sparkline.render(summary.deviations.map(row => row.deviation_mm));
  }, () => { sparkline.dispose(); root.replaceChildren(); }, doc.defaultView);
}
