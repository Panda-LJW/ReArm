// 可选的悬停标签层。投影用 stage 内坐标，验收锚点和鼠标统一用视口 CSS 像素。
export function createHoverLabels(container, stage) {
  let entries = [], pointer = null, disposed = false;
  const viewport = container.ownerDocument?.defaultView || globalThis;

  function refresh() {
    if (disposed) return;
    const bounds = stage.getBoundingClientRect();
    let nearest = null, distance = 40;
    for (const entry of entries) {
      const { el, at } = entry;
      el.style.visibility = "hidden";
      el.hidden = !at;
      if (!at) { delete el.dataset.anchorX; delete el.dataset.anchorY; continue; }
      const x = bounds.left + at[0], y = bounds.top + at[1];
      el.dataset.anchorX = String(x); el.dataset.anchorY = String(y);
      if (!pointer) continue;
      const d = Math.hypot(pointer[0] - x, pointer[1] - y);
      if (d <= 40 && (!nearest || d < distance)) { nearest = entry; distance = d; }
    }
    if (!nearest) return;
    const { el, at } = nearest, { width, height } = el.getBoundingClientRect();
    el.style.transform = "none";
    el.style.left = Math.max(0, Math.min(stage.clientWidth - width, at[0] + 14)) + "px";
    el.style.top = Math.max(0, Math.min(stage.clientHeight - height, at[1] - height / 2)) + "px";
    el.style.visibility = "visible";
  }
  const move = event => { pointer = [event.clientX, event.clientY]; refresh(); };
  const leave = () => { pointer = null; refresh(); };
  container.addEventListener("pointermove", move);
  container.addEventListener("pointerleave", leave);
  container.addEventListener("pointercancel", leave);
  viewport.addEventListener?.("scroll", refresh, true);
  return {
    register(el, id) { el.dataset.twinLabel = String(id); el.style.visibility = "hidden"; },
    place(next) { entries = next; refresh(); },
    dispose() {
      leave(); disposed = true; entries = [];
      container.removeEventListener("pointermove", move);
      container.removeEventListener("pointerleave", leave);
      container.removeEventListener("pointercancel", leave);
      viewport.removeEventListener?.("scroll", refresh, true);
    },
  };
}
