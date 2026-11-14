import { frameView } from "../../shell/view.js";

export function mount(root, ctx = {}) {
  const text = root.ownerDocument.createElement("p"); root.replaceChildren(text);
  return frameView(() => { text.textContent = "在这里查看连接状态和机械臂参数。"; },
    () => text.remove(), root.ownerDocument.defaultView);
}
