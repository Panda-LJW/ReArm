export const number = (value, digits = 1) => Number.isFinite(value) ? value.toFixed(digits) : "—";
export const online = state => state.link.online === true && !!state.hello;
export const modeText = state => !online(state) ? "离线" : ({ idle: "空闲", demo: "示范中", practice: "练习中", estop: "已急停", fault: "故障" }[state.mode] || "等待状态");
export const latestNode = state => state.passes.flatMap(pass => Object.values(pass.nodes))
  .filter(node => node.valid === true).sort((a, b) => b.t - a.t || b.seq - a.seq)[0] ?? null;
export const lastCorrection = state => state.passes.filter(pass => pass.correction).at(-1)?.correction ?? null;
export function correctionText(correction) {
  if (!correction) return "练习一遍后显示修正";
  const item = correction.items?.[0];
  return correction.applied ? (item ? `${item.target} ${item.delta > 0 ? "+" : ""}${number(item.delta, 2)} ${item.unit}` : "已应用修正") : "本遍未应用修正";
}
export function element(tag, className = "", text = "") {
  const el = document.createElement(tag); el.className = className; el.textContent = text; return el;
}
// 保存具体节点，回退不替换 app.js 已绑定事件的区域根节点。
export function preserve(nodes) {
  const saved = nodes.map(el => ({ el, html: el.innerHTML, attrs: [...el.attributes].map(a => [a.name, a.value]) }));
  return () => { for (const { el, html, attrs } of saved) {
    el.innerHTML = html;
    for (const a of [...el.attributes]) el.removeAttribute(a.name);
    for (const [name, value] of attrs) el.setAttribute(name, value);
  } };
}
