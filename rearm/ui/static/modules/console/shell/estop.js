import { frameView } from "./view.js";
import { setUnavailable } from "./tooltip.js";

export function mount(root, ctx = {}) {
  const button = root.ownerDocument.createElement("button");
  button.type = "button"; button.dataset.action = "estop";
  button.className = "console-estop"; button.textContent = "急停";
  const banner = root.ownerDocument.createElement("div");
  banner.className = "console-estop-banner"; banner.hidden = true;
  banner.setAttribute("role", "alert"); banner.textContent = "已急停";
  root.after(banner);
  setUnavailable(button, "连接就绪后可操作");
  const click = () => {
    if (button.getAttribute("aria-disabled") !== "true") ctx.send("estop");
  };
  button.addEventListener("click", click); root.append(button);
  return frameView(state => {
    setUnavailable(button, state?.link?.online && typeof ctx.send === "function" ? "" : "连接就绪后可操作");
    // 等待数据源确认，不能仅因点击急停就提前显示。
    banner.hidden = state?.phase !== "estop";
  }, () => { button.removeEventListener("click", click); button.remove(); banner.remove(); }, root.ownerDocument.defaultView);
}
