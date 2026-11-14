import { frameView } from "../../shell/view.js";

export function mount(root, ctx = {}) {
  const text = root.ownerDocument.createElement("p"); root.replaceChildren(text);
  return frameView(() => { text.textContent = "管理零件与配方，查看文档和训练记录。"; },
    () => text.remove(), root.ownerDocument.defaultView);
}
