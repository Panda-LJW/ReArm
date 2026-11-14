import { mount as mountTopbar } from "./shell/topbar.js";
import { mount as mountRouter } from "./shell/router.js";
import { mount as mountTooltip } from "./shell/tooltip.js";
import { mount as mountDialog } from "./shell/dialog.js";
import { PAGES } from "./shell/nav.js";
import { createStore } from "./state/store.js";
import { createReset } from "./shell/reset.js";
import { mount as mountToast, commandFeedback } from "./shell/toast.js";

const css = document.createElement("link");
css.rel = "stylesheet"; css.href = new URL("./console.css", import.meta.url).href;
document.head.append(css);

const store = createStore();
let source = null, unsubscribeSource = () => {};
const toast = mountToast(document.body);
const ctx = { store, send: commandFeedback(async (cmd, args) => {
  const reply = source ? await source.send(cmd, args) : { v: 1, ok: false, code: "offline", msg: "连接已关闭", seq: 0 };
  if (reply?.ok && reply.msg) toast.show(reply.msg);
  return reply;
}, toast) };
const tooltip = mountTooltip(document, ctx), dialog = mountDialog(document.body, ctx);
ctx.dialog = dialog; ctx.reset = createReset(ctx);
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
const unsubscribeStore = store.subscribe(state => { topbar.render(state); for (const view of views) view.render(state); });

async function optional(name, mount) {
  try {
    const view = await mount();
    if (view) { views.push(view); view.render(store.getState()); }
    if (roots.has(name)) roots.get(name).dataset.ready = "true";
  } catch (error) {
    const failed = name === "twin" ? roots.get("production")?.querySelector("[data-twin-stage]") : roots.get(name);
    failed?.replaceChildren(document.createTextNode(name === "twin" ? "机械臂画面暂时无法显示，请刷新重试。" : "此页暂时无法显示，请刷新重试。"));
    console.warn(`页面 ${name} 未启用：`, error);
  }
}

await optional("datasource", async () => {
  const backend = new URL(window.location.href).searchParams.get("arm") === "backend";
  const moduleName = backend ? "backend-source" : "mock-console";
  const adapter = await import(`../datasource/${moduleName}.js`);
  source = backend ? adapter.createBackendSource() : adapter.createMockConsole();
  window.__rearmMock = { commands: source.commands };
  unsubscribeSource = source.subscribe(message => store.dispatch(message));
  source.start();
});

// 各页独立加载，单页 import / mount 失败不会阻断导航或顶栏。
await Promise.all(PAGES.map(({ id }) => optional(id, async () => {
  const { mount } = await import(`./pages/${id}/index.js`);
  return mount(roots.get(id), ctx);
})));

await optional("twin", async () => {
  const root = roots.get("production").querySelector("[data-twin-stage]");
  if (!root) return;
  const css = document.createElement("link");
  css.rel = "stylesheet"; css.href = new URL("../twin/twin.css", import.meta.url).href; document.head.append(css);
  const [{ createTwin }, { mount }] = await Promise.all([
    import("../twin/twin.js"), import("./pages/production/views/twin-stage.js"),
  ]);
  return mount(root, { ...ctx, createTwin });
});

window.addEventListener("pagehide", event => {
  if (event.persisted) return;
  unsubscribeSource(); source?.stop(); unsubscribeStore();
  for (const view of views) view.dispose();
  router.dispose(); topbar.dispose(); dialog.dispose(); tooltip.dispose(); toast.dispose();
}, { once: true });
