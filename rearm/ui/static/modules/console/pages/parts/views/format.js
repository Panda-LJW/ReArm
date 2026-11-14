import { element } from "../../../widgets/dom.js";

export const number = value => Number.isFinite(value) ? value.toFixed(1) : "—";
export { duration } from "../../../widgets/format.js";
export function collected(value) {
  if (!Number.isFinite(value)) return "—";
  const d = new Date(value), pad = v => String(v).padStart(2, "0");
  return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${[d.getHours(), d.getMinutes(), d.getSeconds()].map(pad).join(":")}`;
}
export function button(doc, text, action, primary = false) {
  const el = element(doc, "button", `console-button${primary ? " console-primary" : ""}`, text);
  el.type = "button"; el.addEventListener("click", action); return el;
}
export function field(doc, text, tag = "input") {
  const label = element(doc, "label", "library-field"), input = element(doc, tag);
  input.setAttribute("aria-label", text); label.append(element(doc, "span", "", text), input);
  return { label, input };
}
export function detail(doc, name, value) {
  const pair = element(doc, "div", "library-detail");
  pair.append(element(doc, "dt", "", name), element(doc, "dd", "", value)); return pair;
}
