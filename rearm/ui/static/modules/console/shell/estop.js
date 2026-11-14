import { frameView } from "./view.js";
import { setUnavailable } from "./tooltip.js";
import { resetReason } from "./reset.js";
import { withBusy } from "../widgets/busy.js";

export function mount(root, ctx = {}) {
  const button = root.ownerDocument.createElement("button");
  button.type = "button"; button.dataset.action = "estop";
  button.className = "console-estop"; button.textContent = "急停";
  const banner = root.ownerDocument.createElement("div");
  banner.className = "console-estop-banner"; banner.hidden = true;
  banner.setAttribute("role", "alert"); banner.textContent = "已急停";
  const release = root.ownerDocument.createElement("button");
  release.type = "button"; release.className = "console-button";
  release.dataset.action = "reset-estop"; release.textContent = "解除急停";
  setUnavailable(release, "连接就绪后可操作");
  const reset = () => { if (release.getAttribute("aria-disabled") !== "true") ctx.reset(release); };
  release.addEventListener("click", reset);
  if (typeof ctx.reset === "function") banner.append(release);
  const win = root.ownerDocument.defaultView;
  setUnavailable(button, "连接就绪后可操作");
  const click = () => {
    if (button.getAttribute("aria-disabled") !== "true") void withBusy(button, () => ctx.send("estop")).catch(() => {});
  };
  button.addEventListener("click", click); root.append(banner, button);
  return frameView(state => {
    setUnavailable(button, state?.link?.online && typeof ctx.send === "function" ? "" : "连接就绪后可操作");
    // 等待数据源确认，不能仅因点击急停就提前显示。
    banner.hidden = state?.phase !== "estop";
    root.toggleAttribute("data-estop", !banner.hidden);
    setUnavailable(release, resetReason(state, ctx));
  }, () => {
    root.removeAttribute("data-estop");
    button.removeEventListener("click", click); release.removeEventListener("click", reset);
    button.remove(); banner.remove();
  }, win);
}
