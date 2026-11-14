import { frameView } from "./view.js";
import { setUnavailable } from "./tooltip.js";

export function mount(root, ctx = {}) {
  const button = root.ownerDocument.createElement("button");
  button.type = "button"; button.dataset.action = "estop";
  button.className = "console-estop"; button.textContent = "急停";
  setUnavailable(button, "连接就绪后可操作");
  const click = () => {
    if (button.getAttribute("aria-disabled") !== "true") ctx.send("estop");
  };
  button.addEventListener("click", click); root.append(button);
  return frameView(state => {
    setUnavailable(button, state?.link?.online && typeof ctx.send === "function" ? "" : "连接就绪后可操作");
  }, () => { button.removeEventListener("click", click); button.remove(); }, root.ownerDocument.defaultView);
}
