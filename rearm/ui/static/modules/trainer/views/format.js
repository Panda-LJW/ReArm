import { number } from "../format.js";
export { number };
export const online = state => state.link.online === true && !!state.hello;
export const modeText = state => !online(state) ? "离线" : ({ idle: "空闲", demo: "示范中", practice: "练习中", estop: "已急停", fault: "故障" }[state.mode] || "等待状态");
export function latestNode(state) {
  // 有当前节点时只取该节点；缺测或尚未测量都不能回退到别处的旧光点。
  if (state.currentNode) return state.passes.find(pass => pass.pass === state.currentNode.pass)
    ?.nodes[state.currentNode.node] ?? null;
  return state.passes.flatMap(pass => Object.values(pass.nodes))
    .sort((a, b) => b.t - a.t || b.seq - a.seq)[0] ?? null;
}
export const lastCorrection = state => state.passes.filter(pass => pass.correction).at(-1)?.correction ?? null;
export const correctionValue = item => number(item.delta, 2, true) +
  (["deg", "°"].includes(item.unit) ? "°" : item.unit ? ` ${item.unit}` : "");
export function correctionSummary(correction) {
  if (!correction) return "";
  const groups = new Map();
  for (const item of correction.items || []) {
    const group = groups.get(item.target) ?? { count: 0, maximum: item };
    group.count++;
    if (Math.abs(item.delta) > Math.abs(group.maximum.delta)) group.maximum = item;
    groups.set(item.target, group);
  }
  return [...groups].map(([target, group]) =>
    `${target} ${group.count} 处，最大 ${correctionValue(group.maximum)}`).join("；") || "无需修正";
}
export const correctionTarget = item => {
  const note = item.note?.trim(), node = note?.match(/节点\s*\d+/)?.[0];
  return note ? `${item.target} · ${node || note}` : item.target;
};
export function correctionText(correction) {
  if (!correction) return "练习一遍后显示修正";
  const item = correction.items?.[0];
  return correction.applied ? (item ? `${correctionTarget(item)} ${correctionValue(item)}` : "已应用修正") : "本遍未应用修正";
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
