import { PAGES } from "./nav.js";
import { reducedMotion, crossfade, stagger } from "../widgets/motion.js";

// hash 是唯一的页面选择来源，前进、后退和刷新走同一条路径。
export function mount(root, { onRoute = () => {}, beforeRoute = () => {} } = {}) {
  const doc = root.ownerDocument, win = doc.defaultView;
  const pages = [...root.querySelectorAll("[data-page]")];
  let currentPage, transition, timer, revision = 0, disposed = false;
  const inertBefore = new Map();
  function clearMotion() {
    win.clearTimeout(timer);
    for (const el of pages) {
      el.classList.remove("c-swap-out", "c-swap-in");
      if (inertBefore.has(el)) {
        el.toggleAttribute("inert", inertBefore.get(el)); inertBefore.delete(el);
      }
    }
  }
  function display(page) {
    for (const el of pages) {
      el.hidden = el.dataset.page !== page;
      if (!el.hidden && currentPage !== page) {
        delete el.dataset.enter;
        void el.offsetWidth;
        el.dataset.enter = "";
        stagger(el.querySelectorAll(".c-card"));
      }
    }
    currentPage = page;
  }
  function route() {
    if (disposed) return;
    const hash = win.location.hash.slice(1);
    const page = PAGES.some(item => item.id === hash) ? hash : "production";
    if (hash !== page) win.history.replaceState(null, "", `${win.location.pathname}${win.location.search}#${page}`);
    beforeRoute();
    const token = ++revision;
    transition?.skipTransition(); transition = null; clearMotion();
    const previous = pages.find(el => el.dataset.page === currentPage);
    const next = pages.find(el => el.dataset.page === page);
    const update = () => { if (!disposed && token === revision) display(page); };
    if (!previous || page === currentPage || reducedMotion(win)) update();
    else if (typeof doc.startViewTransition === "function") {
      try {
        transition = doc.startViewTransition(update);
        // 画面捕获失败时仍必须完成切页；过期回调不能覆盖新路由。
        transition.ready.catch(() => {});
        transition.updateCallbackDone.catch(update);
        transition.finished?.catch(() => {});
      } catch { update(); }
    } else {
      update();
      inertBefore.set(previous, previous.hasAttribute("inert"));
      previous.setAttribute("inert", "");
      crossfade(previous, next);
      timer = win.setTimeout(clearMotion, 160);
    }
    onRoute(page);
  }
  function shortcut(event) {
    if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.repeat || event.isComposing) return;
    const number = /^[1-4]$/.test(event.key) ? Number(event.key) : /^Digit[1-4]$/.test(event.code) ? Number(event.code.slice(-1)) : 0;
    if (!number) return;
    event.preventDefault();
    const page = PAGES[number - 1].id;
    win.location.hash = page;
    // hashchange 是路由入口；只把键盘焦点送到对应导航，避免留在已隐藏页面。
    beforeRoute(); doc.querySelector(`[data-nav="${page}"]`)?.focus();
  }
  win.addEventListener("hashchange", route);
  doc.addEventListener("keydown", shortcut);
  route();
  return { render: route, dispose() {
    disposed = true; ++revision; transition?.skipTransition(); clearMotion();
    win.removeEventListener("hashchange", route); doc.removeEventListener("keydown", shortcut);
  } };
}
