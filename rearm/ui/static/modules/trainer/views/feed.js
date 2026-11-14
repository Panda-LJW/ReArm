import { online, number, correctionText, element, preserve } from "./format.js";

export function mount(root) {
  const dispose = preserve([root]); let previous = "";
  return { dispose, render(state) {
    const events = state.events.filter(e => e.name !== "pass_finished").map(e => ({ t: e.t,
      text: e.text || e.msg || e.name || e.code || "主机事件", level: e.type === "error" || ["error", "warning"].includes(e.level) ? "bad" : e.level || "info" }));
    for (const pass of state.passes) {
      if (pass.result) events.push({ t: pass.result.t, text: `第 ${pass.pass} 遍结束：平均 ${number(pass.result.mean_mm)} mm`, level: "ok" });
      if (pass.correction) events.push({ t: pass.correction.t, text: `第 ${pass.pass} 遍修正：${correctionText(pass.correction)}`, level: "info" });
    }
    events.sort((a, b) => b.t - a.t);
    const shown = events.slice(0, 40), key = JSON.stringify([online(state), shown]);
    if (key === previous) return; previous = key;
    root.replaceChildren();
    if (!online(state)) root.append(element("div", "empty", "离线"));
    if (!shown.length && online(state)) root.append(element("div", "empty", "点‘示范’开始"));
    for (const event of shown) {
      const row = element("div", "ev"), time = element("time", "num", new Date(event.t).toLocaleTimeString("zh-CN", { hour12: false }));
      row.append(time, element("i", ["ok", "bad", "busy", "info"].includes(event.level) ? event.level : "info"), element("span", "", event.text)); root.append(row);
    }
  } };
}
