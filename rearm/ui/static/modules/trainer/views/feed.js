import { summarize } from "../metrics.js";
import { online, number, correctionSummary, element, preserve } from "./format.js";

export function mount(root) {
  const dispose = preserve([root]), passRows = new Map(); let previous = "";
  return { dispose, render(state, summary = {}) {
    const passes = state.passes.filter(pass => pass.result || pass.correction);
    const passNumbers = new Set(passes.map(pass => pass.pass));
    const events = state.events.filter(e => {
      if (e.type !== "event" || e.name !== "pass_finished") return true;
      // 模拟主机的结束事件没有 pass 字段，只在文字开头标明遍号。
      const pass = Number.isInteger(e.pass) ? e.pass : Number((e.text || e.msg || "").match(/^第\s*(\d+)\s*遍/)?.[1]);
      return !passNumbers.has(pass);
    }).map(e => ({ t: e.t,
      text: e.text || e.msg || e.name || e.code || "主机事件", level: e.type === "error" || ["error", "warning"].includes(e.level) ? "bad" : e.level || "info" }));
    for (const pass of passes) {
      const parts = [];
      if (pass.result) parts.push(`平均 ${number(pass.result.mean_mm)} mm`);
      if (pass.correction) parts.push(pass.correction.items?.length ? `修正 ${correctionSummary(pass.correction)}` : correctionSummary(pass.correction));
      const passed = summarize({ ...state, passes: [pass] },
        { thresholdMm: summary.thresholdMm ?? state.hello?.threshold_mm }).belowThreshold;
      // 晚到修正只补文字，排序仍按本遍结果时间。
      events.push({ pass: pass.pass, t: pass.result?.t ?? pass.correction?.t,
        text: `第 ${pass.pass} 遍：${parts.join(" · ")}`, level: passed ? "ok" : "busy" });
    }
    events.sort((a, b) => b.t - a.t);
    const shown = events.slice(0, 40), key = JSON.stringify([online(state), shown]);
    if (key === previous) return; previous = key;
    for (const pass of passRows.keys()) if (!shown.some(event => event.pass === pass)) passRows.delete(pass);
    root.replaceChildren();
    if (!online(state)) root.append(element("div", "empty", "离线"));
    if (!shown.length && online(state)) root.append(element("div", "empty", "点‘示范’开始"));
    for (const event of shown) {
      let entry = passRows.get(event.pass);
      if (!entry) {
        entry = { row: element("div", "ev"), time: element("time", "num"), icon: element("i"), text: element("span") };
        entry.row.append(entry.time, entry.icon, entry.text);
        if (event.pass != null) passRows.set(event.pass, entry);
      }
      entry.time.textContent = new Date(event.t).toLocaleTimeString("zh-CN", { hour12: false });
      entry.icon.className = ["ok", "bad", "busy", "info"].includes(event.level) ? event.level : "info";
      entry.text.textContent = event.text; root.append(entry.row);
    }
  } };
}
