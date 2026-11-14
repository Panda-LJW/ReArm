import { mount as mountNav } from "./nav.js";
import { mount as mountEstop } from "./estop.js";
import { setUnavailable } from "./tooltip.js";
import { frameView } from "./view.js";
import { WORDS } from "../state/words.js";
import { statusWord } from "../state/selectors.js";

export function mount(root, ctx = {}) {
  const doc = root.ownerDocument;
  const brand = doc.createElement("div"), logo = doc.createElement("img");
  brand.className = "console-brand";
  logo.src = "/static/brand/rearm-wordmark.svg"; logo.alt = "ReArm 日新臂";
  brand.append(logo);
  const navigation = doc.createElement("nav");
  navigation.className = "console-nav"; navigation.setAttribute("aria-label", "主导航");
  const status = doc.createElement("span");
  status.className = "console-status"; status.dataset.status = "";
  status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
  status.textContent = WORDS.idle;
  const spacer = doc.createElement("div"); spacer.className = "console-spacer";
  const reset = doc.createElement("button");
  reset.type = "button"; reset.className = "console-button";
  reset.dataset.action = "reset"; reset.textContent = "一键重置";
  setUnavailable(reset, "连接就绪后可操作");
  const click = () => { if (reset.getAttribute("aria-disabled") !== "true") ctx.reset(); };
  reset.addEventListener("click", click);
  root.append(brand, navigation, status, spacer, reset);
  const nav = mountNav(navigation, ctx), estop = mountEstop(root, ctx);
  const view = frameView(state => {
    const text = state ? statusWord(state) : WORDS.idle;
    if (status.textContent !== text) status.textContent = text;
    setUnavailable(reset, state?.link?.online && typeof ctx.reset === "function" ? "" : "连接就绪后可操作");
    estop.render(state);
  }, () => {
    nav.dispose(); estop.dispose(); reset.removeEventListener("click", click); root.replaceChildren();
  }, doc.defaultView);
  return { ...view, navigate(page) { nav.render(page); } };
}
