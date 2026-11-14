import { frameView } from "./view.js";

export const PAGES = Object.freeze([
  { id: "production", label: "生产" }, { id: "parts", label: "零件库" },
  { id: "records", label: "记录" }, { id: "settings", label: "设置" },
]);

export function mount(root, ctx = {}) {
  const links = PAGES.map(({ id, label }) => {
    const link = root.ownerDocument.createElement("a");
    link.href = `#${id}`; link.dataset.nav = id; link.textContent = label;
    root.append(link); return link;
  });
  return frameView(page => {
    for (const link of links) {
      if (link.dataset.nav === page) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
  }, () => links.forEach(link => link.remove()), root.ownerDocument.defaultView);
}
