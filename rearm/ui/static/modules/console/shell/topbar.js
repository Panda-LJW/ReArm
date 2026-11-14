import { mount as mountNav } from "./nav.js";
import { mount as mountEstop } from "./estop.js";
import { setUnavailable } from "./tooltip.js";
import { frameView } from "./view.js";
import { WORDS } from "../state/words.js";
import { online, statusWord } from "../state/selectors.js";

export function mount(root, ctx = {}) {
  const doc = root.ownerDocument;
  const brand = doc.createElement("div"), name = doc.createElement("span"), subtitle = doc.createElement("small");
  brand.className = "console-brand";
  name.className = "console-brand-name"; name.textContent = "ReArm";
  subtitle.textContent = "日新臂 · 生产控制台";
  brand.append(name, subtitle);
  const connection = doc.createElement("div"), dot = doc.createElement("span");
  const connectionLabel = doc.createElement("span"), source = doc.createElement("span");
  connection.className = "console-connection"; connection.hidden = true;
  connection.setAttribute("role", "status"); connection.setAttribute("aria-live", "polite");
  dot.className = "console-connection-dot"; dot.setAttribute("aria-hidden", "true");
  connectionLabel.className = "console-connection-label";
  source.className = "pill console-source"; source.hidden = true;
  connection.append(dot, connectionLabel, source);
  const navigation = doc.createElement("nav");
  navigation.className = "console-nav"; navigation.setAttribute("aria-label", "主导航");
  const status = doc.createElement("span");
  status.className = "console-status pill"; status.dataset.status = "";
  status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
  status.textContent = WORDS.idle;
  const spacer = doc.createElement("div"); spacer.className = "console-spacer";
  const reset = doc.createElement("button");
  reset.type = "button"; reset.className = "console-button";
  reset.dataset.action = "reset"; reset.textContent = "一键重置";
  setUnavailable(reset, "连接就绪后可操作");
  const click = () => { if (reset.getAttribute("aria-disabled") !== "true") ctx.reset(); };
  reset.addEventListener("click", click);
  root.append(brand, connection, navigation, status, spacer, reset);
  const nav = mountNav(navigation, ctx), estop = mountEstop(root, ctx);
  const view = frameView(state => {
    const text = state ? statusWord(state) : WORDS.idle;
    if (status.textContent !== text) status.textContent = text;
    // 与设置页共用已有字段和 online 语义；缺失的连接/来源不补默认数据。
    const hasLink = typeof state?.link?.online === "boolean";
    const connected = hasLink && online(state);
    const label = !hasLink ? "" : !state.link.online ? "未连接" : !state.hello ? "等待握手" :
      connected ? "实时连接" : "协议不兼容";
    const sourceText = state?.hello?.sim === true ? "本地演示" : state?.hello?.sim === false ? "主机" : "";
    connection.hidden = !hasLink && !sourceText;
    dot.hidden = connectionLabel.hidden = !hasLink;
    connection.dataset.online = String(connected);
    connection.setAttribute("aria-label", [label, sourceText].filter(Boolean).join(" · "));
    if (connectionLabel.textContent !== label) connectionLabel.textContent = label;
    source.hidden = !sourceText;
    if (source.textContent !== sourceText) source.textContent = sourceText;
    const resetReason = !state?.link?.online || typeof ctx.reset !== "function" ? "连接就绪后可操作" :
      state.hello?.sim !== true && state.phase !== "estop" ? "当前无需解除急停" : "";
    setUnavailable(reset, resetReason);
    estop.render(state);
  }, () => {
    nav.dispose(); estop.dispose(); reset.removeEventListener("click", click); root.replaceChildren();
  }, doc.defaultView);
  return { ...view, navigate(page) { nav.render(page); } };
}
