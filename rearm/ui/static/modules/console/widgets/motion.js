// 控制台共享动效工具。样式定义在 console.css（c-flash / c-swap-out / c-swap-in / c-enter），这里只负责触发。
// 约定：JS 只切换 class 或属性，不写内联动画；减少动态效果时 CSS 会把动画关掉，这里同步跳过等待。

export function reducedMotion(win = globalThis) {
  return Boolean(win?.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);
}

// 重新触发一次性动画类：先移除、强制回流、再加上；动画结束后自动移除。
export function replay(el, className) {
  if (!el?.classList) return;
  el.classList.remove(className);
  void el.offsetWidth;
  el.classList.add(className);
  const done = event => {
    if (event.target !== el) return;
    el.classList.remove(className);
    el.removeEventListener("animationend", done);
  };
  el.addEventListener("animationend", done);
}

// 数值变化高亮：文字由 --sub 过渡到 --data，底部细线从左扫到右。值未变化时不触发。
export function flash(el, value) {
  if (!el) return;
  const next = value === undefined ? el.textContent : String(value);
  if (el.dataset.flashValue === next) return;
  const first = el.dataset.flashValue === undefined;
  el.dataset.flashValue = next;
  if (!first) replay(el, "c-flash");
}

// 内容交叉淡入：旧内容 120ms 淡出，回调替换内容后淡入。返回 Promise，替换完成后 resolve。
export function swap(el, render, win = globalThis) {
  if (!el) return Promise.resolve();
  if (reducedMotion(win) || !el.isConnected) { render(); return Promise.resolve(); }
  const token = (el.__swapToken || 0) + 1;
  el.__swapToken = token;
  return new Promise(resolve => {
    el.classList.remove("c-swap-in");
    el.classList.add("c-swap-out");
    const finish = () => {
      if (el.__swapToken !== token) return resolve();
      el.classList.remove("c-swap-out");
      render();
      replay(el, "c-swap-in");
      resolve();
    };
    const timer = win.setTimeout(finish, 140);
    el.addEventListener("animationend", function end(event) {
      if (event.target !== el) return;
      el.removeEventListener("animationend", end);
      win.clearTimeout(timer);
      finish();
    });
  });
}

// 进场错峰：给一组元素写 --i 并加 c-enter；重复调用会重播。最多 6 级。
export function stagger(elements) {
  [...elements].forEach((el, i) => {
    el.style.setProperty("--i", String(Math.min(i, 5)));
    replay(el, "c-enter");
  });
}

// 页面同时交叉淡入：重排共同父容器，旧页保持 hidden/inert；清理由路由生命周期负责。
export function crossfade(previous, next) {
  if (!previous || !next) return;
  for (const el of [previous, next]) el.classList.remove("c-swap-out", "c-swap-in");
  void (next.parentElement || next).offsetWidth;
  previous.classList.add("c-swap-out"); next.classList.add("c-swap-in");
}
