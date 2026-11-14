import { frameView } from "../../shell/view.js";

export function mount(root, ctx = {}) {
  const text = root.ownerDocument.createElement("p"); root.replaceChildren(text);
  return frameView(() => { text.textContent = "在这里查看历次生产和训练记录。"; },
    () => text.remove(), root.ownerDocument.defaultView);
}
