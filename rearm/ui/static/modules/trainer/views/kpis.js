import { number, online, modeText, correctionSummary, lastCorrection, preserve, element } from "./format.js";

export function mount(root) {
  const dispose = preserve([root]);
  const cells = [...root.querySelectorAll(".kpi")].map((cell, i) => {
    cell.querySelector(".k").textContent = ["第几遍", "和示范差多少", "比第一遍好了多少", "修正了几次"][i];
    return { cell, value: cell.querySelector(".v"), detail: cell.querySelector(".d") };
  });
  function set(i, value, unit, detail, level = "none") {
    const { cell, value: target, detail: desc } = cells[i];
    target.replaceChildren(document.createTextNode(value));
    if (unit && value !== "—") target.append(element("small", "", unit));
    desc.textContent = detail; cell.dataset.level = level;
    target.classList.toggle("badc", level === "bad");
  }
  return { dispose, render(state, summary) {
    if (!online(state)) { cells.forEach((_, i) => set(i, "—", "", "离线")); return; }
    let detail = modeText(state);
    if (state.mode === "practice") detail = summary.lastCompletedPass == null
      ? "第 1 遍进行中" : `第 ${summary.lastCompletedPass} 遍已完成 · 练习中`;
    else if (summary.pass == null && state.mode === "idle") detail = state.demo
      ? "点“练习”开始" : "点“示范”，手扶机械臂做一遍";
    set(0, summary.pass == null ? "—" : String(summary.pass), "遍", detail);
    const passed = summary.belowThreshold;
    set(1, number(summary.lastMeanMm), "mm", passed == null ? "" : passed
      ? `✓ 达标（最大 ≤ ${summary.thresholdMm} mm）` : `▲ 未达标（最大 ${number(summary.lastMaxMm)} mm）`,
    passed == null ? "none" : passed ? "ok" : "bad");
    const pct = summary.improvedPct;
    const baseline = state.passes.filter(pass => pass.result).length === 1;
    const worse = !baseline && pct < 0;
    set(2, baseline || pct == null ? "—" : number(Math.abs(pct), 0), "%", baseline ? "第 1 遍是基准" : pct == null ? "" :
      `${worse ? "▲ 变差 ·" : pct > 0 ? "↓" : "持平 ·"} ${number(summary.firstMeanMm)} → ${number(summary.lastMeanMm)} mm`, worse ? "bad" : "none");
    const correction = lastCorrection(state);
    set(3, summary.corrections == null ? "—" : String(summary.corrections), "次",
      summary.corrections == null || !correction ? "" : `第 ${correction.pass} 遍：${correctionSummary(correction)}`);
  } };
}
