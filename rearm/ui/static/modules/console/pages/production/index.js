import { frameView } from "../../shell/view.js";

export function mount(root, ctx = {}) {
  const text = root.ownerDocument.createElement("p"); root.replaceChildren(text);
  return frameView(() => { text.textContent = "选择配方后开始生产，在这里查看装配进度和检查结果。"; },
    () => text.remove(), root.ownerDocument.defaultView);
}
