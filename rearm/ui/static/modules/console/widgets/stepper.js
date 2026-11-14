import { frameView } from "../shell/view.js";
import { element } from "./dom.js";

export function mount(root) {
  const doc = root.ownerDocument, list = element(doc, "ol", "production-stepper");
  root.append(list); let signature = "";
  return frameView(rows => {
    const next = JSON.stringify(rows);
    if (signature === next) return;
    signature = next;
    list.replaceChildren(...(rows || []).map(row => {
      const li = element(doc, "li", "", row.label);
      li.dataset.progress = row.done ? "done" : row.current ? "current" : "waiting";
      if (row.current) li.setAttribute("aria-current", "step");
      return li;
    }));
  }, () => list.remove(), doc.defaultView);
}
