import { mount as mountTopbar } from "./shell/topbar.js";
import { mount as mountRouter } from "./shell/router.js";
import { mount as mountTooltip } from "./shell/tooltip.js";
import { mount as mountDialog } from "./shell/dialog.js";
import { PAGES } from "./shell/nav.js";

const css = document.createElement("link");
css.rel = "stylesheet"; css.href = new URL("./console.css", import.meta.url).href;
document.head.append(css);

// T1 只装配外壳；数据源、store 和业务指令由后续任务接入。
const ctx = {};
const tooltip = mountTooltip(document, ctx), dialog = mountDialog(document.body, ctx);
const topbar = mountTopbar(document.querySelector("[data-topbar]"), ctx);
const pagesRoot = document.querySelector("[data-pages]"), views = [];
const roots = new Map(PAGES.map(({ id, label }) => {
  const root = document.createElement("section");
  root.dataset.page = id; root.className = "console-page"; root.hidden = true;
  root.setAttribute("aria-label", label);
  root.textContent = "此页暂时无法显示，请刷新重试。";
  pagesRoot.append(root); return [id, root];
}));
const router = mountRouter(pagesRoot, { onRoute: topbar.navigate,
  beforeRoute() { tooltip.hide(); dialog.close(); } });
topbar.render();

async function optional(name, mount) {
  try {
    const view = await mount();
    views.push(view); view.render();
    roots.get(name).dataset.ready = "true";
  } catch (error) {
    roots.get(name).replaceChildren(document.createTextNode("此页暂时无法显示，请刷新重试。"));
    console.warn(`页面 ${name} 未启用：`, error);
  }
}

// 各页独立加载，单页 import / mount 失败不会阻断导航或顶栏。
await Promise.all(PAGES.map(({ id }) => optional(id, async () => {
  const { mount } = await import(`./pages/${id}/index.js`);
  return mount(roots.get(id), ctx);
})));

window.addEventListener("pagehide", event => {
  if (event.persisted) return;
  for (const view of views) view.dispose();
  router.dispose(); topbar.dispose(); dialog.dispose(); tooltip.dispose();
}, { once: true });
