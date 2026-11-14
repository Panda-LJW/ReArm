import { PAGES } from "./nav.js";

// hash 是唯一的页面选择来源，前进、后退和刷新走同一条路径。
export function mount(root, { onRoute = () => {}, beforeRoute = () => {} } = {}) {
  const win = root.ownerDocument.defaultView;
  const pages = [...root.querySelectorAll("[data-page]")];
  function route() {
    const hash = win.location.hash.slice(1);
    const page = PAGES.some(item => item.id === hash) ? hash : "production";
    if (hash !== page) win.history.replaceState(null, "", `${win.location.pathname}${win.location.search}#${page}`);
    beforeRoute();
    for (const el of pages) el.hidden = el.dataset.page !== page;
    onRoute(page);
  }
  win.addEventListener("hashchange", route);
  route();
  return { render: route, dispose() { win.removeEventListener("hashchange", route); } };
}
