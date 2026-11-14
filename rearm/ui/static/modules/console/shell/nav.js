import { frameView } from "./view.js";

export const PAGES = Object.freeze([
  { id: "production", label: "生产" }, { id: "parts", label: "零件库" },
  { id: "records", label: "记录" }, { id: "settings", label: "设置" },
]);

export function mount(root, ctx = {}) {
  const doc = root.ownerDocument, win = doc.defaultView;
  const links = PAGES.map(({ id, label }) => {
    const link = root.ownerDocument.createElement("a");
    link.href = `#${id}`; link.dataset.nav = id; link.textContent = label;
    root.append(link); return link;
  });
  const indicator = doc.createElement("span");
  indicator.className = "console-nav-indicator";
  indicator.setAttribute("aria-hidden", "true"); indicator.hidden = true;
  root.append(indicator);
  let disposed = false;
  function position() {
    const active = links.find(link => link.getAttribute("aria-current") === "page");
    if (!active) { indicator.hidden = true; return; }
    const tab = active.getBoundingClientRect(), nav = root.getBoundingClientRect();
    indicator.style.width = `${tab.width}px`;
    indicator.style.transform = `translateX(${tab.left - nav.left + root.scrollLeft}px)`;
    indicator.hidden = false;
  }
  const layout = frameView(position, () => {}, win);
  const reposition = () => { if (!disposed) layout.render(); };
  win.addEventListener("resize", reposition);
  const observer = win.ResizeObserver ? new win.ResizeObserver(reposition) : null;
  [root, ...links].forEach(el => observer?.observe(el));
  doc.fonts?.ready.then(reposition);
  doc.fonts?.addEventListener("loadingdone", reposition);
  return frameView(page => {
    for (const link of links) {
      if (link.dataset.nav === page) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    position();
  }, () => {
    disposed = true; layout.dispose(); observer?.disconnect();
    win.removeEventListener("resize", reposition);
    doc.fonts?.removeEventListener("loadingdone", reposition);
    indicator.remove(); links.forEach(link => link.remove());
  }, win);
}
