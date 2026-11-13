// 可选模块的装配处：决定加载哪些模块、把谁接到谁上。每个模块单独 try，
// 任何一个缺失或出错都只影响它自己，主面板（app.js）照常运行。
const params = new URLSearchParams(location.search);
const base = new URL(".", import.meta.url);

function loadCss(path) {
  return new Promise(resolve => {
    const link = document.createElement("link");
    link.rel = "stylesheet"; link.href = new URL(path, base).href;
    link.onload = () => resolve(true);
    link.onerror = () => { link.remove(); resolve(false); };
    document.head.appendChild(link);
  });
}
async function optional(name, mount) {
  try { await mount(); document.documentElement.dataset[name] = "on"; }
  catch (error) { document.documentElement.dataset[name] = "off"; console.warn(`可选模块 ${name} 未启用：`, error); }
}

await loadCss("main.css");

// 视觉主题：只覆盖 design tokens 和少量外观细节。?theme=classic 可临时关掉，便于对比。
await optional("theme", async () => {
  if (params.get("theme") === "classic") throw new Error("已按地址栏参数关闭");
  if (!await loadCss("theme/theme.css")) throw new Error("样式文件不存在");
  document.dispatchEvent(new CustomEvent("rearm:theme", { detail: { theme: "instrument" } }));
});

// 专注阅读：状态的图标编码、动效收敛、按阶段弱化次要区域。纯样式模块。
await optional("focus", async () => {
  if (!await loadCss("focus/focus.css")) throw new Error("样式文件不存在");
});

// 数字孪生：数据源 → 孪生。两者只通过 JointFrame 相连。
await optional("twin", async () => {
  const slot = document.getElementById("twin"), card = document.getElementById("twincard");
  if (!slot || !card || params.get("twin") === "off") throw new Error("已关闭或页面没有挂载位");
  const [{ createTwin }, { sourceFromParams }] = await Promise.all([import("./twin/twin.js"), import("./datasource/index.js"), loadCss("twin/twin.css")]);
  card.hidden = false; document.body.classList.add("has-twin");
  try {
    const twin = await createTwin(slot, { skin: params.get("skin") !== "simple" }), source = sourceFromParams(params);
    source.subscribe(frame => twin.update(frame));
    source.start();
    document.addEventListener("rearm:theme", () => twin.refreshTheme());
    window.__rearmTwin = { twin, source }; // 仅供调试和自动化验收读取
    // 主程序可能已经广播过状态，补要一次
    document.dispatchEvent(new CustomEvent("rearm:modules-ready"));
  } catch (error) { card.hidden = true; document.body.classList.remove("has-twin"); throw error; }
});

// 路演模式
await optional("presentation", async () => {
  const [{ initPresentation }] = await Promise.all([import("./presentation/presentation.js"), loadCss("presentation/presentation.css")]);
  initPresentation({ params });
});
