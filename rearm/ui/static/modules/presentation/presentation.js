// 路演模式：给大屏投影用的显示方案。只做两件事——在 <html> 上切换 data-mode="show"，
// 并在自己的挂载位里放一个开关按钮。放大规则全部在 presentation.css 里，靠覆盖 design tokens 实现。
// 打开方式：地址栏加 ?mode=show，或点顶栏“路演模式”按钮。
export const PARAM = "mode", VALUE = "show";

export function isShow(params) { return params.get(PARAM) === VALUE; }

// 纯函数：给定当前地址和目标状态，返回新的地址（保留其它参数和 #页面）。
export function urlFor(href, on) {
  const url = new URL(href);
  if (on) url.searchParams.set(PARAM, VALUE); else url.searchParams.delete(PARAM);
  return url.toString();
}

export function initPresentation({ params = new URLSearchParams(location.search), root = document.documentElement, slot = document.getElementById("modeslot") } = {}) {
  let on = false, button = null;
  function apply(next, { updateUrl = true } = {}) {
    on = !!next;
    if (on) root.dataset.mode = VALUE; else delete root.dataset.mode;
    if (button) { button.textContent = on ? "退出路演" : "路演模式"; button.setAttribute("aria-pressed", String(on)); button.title = on ? "回到日常调试显示，并退出全屏" : "切到大屏投影显示：字号放大，并进入全屏"; }
    if (updateUrl) history.replaceState(null, "", urlFor(location.href, on));
    // 通知其它模块：变量变了，图表和模型按新字号、新配色重画；窗口尺寸相关的布局也重算一次。
    document.dispatchEvent(new CustomEvent("rearm:theme", { detail: { mode: on ? VALUE : "normal" } }));
    dispatchEvent(new Event("resize"));
  }
  if (slot) {
    button = document.createElement("button");
    button.id = "modetoggle"; button.type = "button";
    // 投影时地址栏和标签栏会占掉近百像素高度：点按钮进入路演的同时进入全屏，退出时一并退出。
    // 全屏需要用户手势，且可能被浏览器拒绝；失败时只是不全屏，路演模式照常。
    button.onclick = () => {
      apply(!on);
      try {
        if (on && !document.fullscreenElement) root.requestFullscreen?.().catch(() => {});
        else if (!on && document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
      } catch { /* 不支持全屏的环境 */ }
    };
    slot.replaceChildren(button);
  }
  apply(isShow(params), { updateUrl: false });
  return { isOn: () => on, set: apply };
}
