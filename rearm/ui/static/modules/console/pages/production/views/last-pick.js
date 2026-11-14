import { frameView } from "../../../shell/view.js";
import { element } from "../../../widgets/dom.js";

export function mount(root) {
  const doc = root.ownerDocument, title = element(doc, "h2", "c-card-head", "最近抓取");
  const body = element(doc, "div", "c-card-body production-last-pick-body");
  const empty = element(doc, "p", "c-empty", "暂无抓取记录"), table = element(doc, "table", "c-table production-last-pick");
  table.setAttribute("aria-label", "最近抓取结果");
  const rows = element(doc, "tbody"), fields = {};
  for (const [key, label] of [["held", "结果"], ["reason", "原因"], ["errors", "指尖误差"], ["retry", "二次下探被拒"]]) {
    const row = element(doc, "tr"), heading = element(doc, "th", "", label), value = element(doc, "td");
    heading.scope = "row"; value.dataset.lastPick = key; fields[key] = value; row.append(heading, value); rows.append(row);
  }
  table.append(rows); body.append(empty, table); root.append(title, body); root.hidden = true;
  return frameView(state => {
    root.hidden = !state.device;
    const pick = state.lastPick; empty.hidden = !!pick; table.hidden = !pick;
    title.textContent = state.link.online ? "最近抓取" : "最近抓取（离线前）";
    if (!pick) return;
    const values = { held: pick.held === true ? "夹到" : pick.held === false ? "未夹到" : "—", reason: pick.reason || "—",
      errors: pick.tip_errors_mm?.length ? `${pick.tip_errors_mm.map(value => Number.isFinite(value) ? value : "—").join(" → ")} mm` : "—",
      retry: pick.retry_refused === true ? "是" : pick.retry_refused === false ? "否" : "—" };
    for (const [key, value] of Object.entries(values)) if (fields[key].textContent !== value) fields[key].textContent = value;
  }, () => root.replaceChildren(), doc.defaultView);
}
