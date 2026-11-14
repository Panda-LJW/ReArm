import { PAGES } from "./nav.js";

// hash 是唯一的页面选择来源，前进、后退和刷新走同一条路径。
export function mount(root, { onRoute = () => {}, beforeRoute = () => {} } = {}) {
  const win = root.ownerDocument.defaultView;
  const pages = [...root.querySelectorAll("[data-page]")];
  let currentPage;
  function route() {
    const hash = win.location.hash.slice(1);
    const page = PAGES.some(item => item.id === hash) ? hash : "production";
    if (hash !== page) win.history.replaceState(null, "", `${win.location.pathname}${win.location.search}#${page}`);
    beforeRoute();
    for (const el of pages) {
      el.hidden = el.dataset.page !== page;
      if (!el.hidden && currentPage !== page) {
        // 只在切页时重启；同步布局让快速往返也经过无动画态，不延迟页面显示。
        delete el.dataset.enter;
        void el.offsetWidth;
        el.dataset.enter = "";
      }
    }
    currentPage = page;
    onRoute(page);
  }
  win.addEventListener("hashchange", route);
  route();
  return { render: route, dispose() { win.removeEventListener("hashchange", route); } };
}
