export const token = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
// clamp()/calc() 不能 parseFloat(token)：交给浏览器通过探针计算真实字号。
export function px(name) {
  const probe = document.createElement("i");
  probe.style.cssText = "position:absolute;visibility:hidden;pointer-events:none";
  probe.style.fontSize = `var(${name})`;
  document.body.append(probe);
  const size = parseFloat(getComputedStyle(probe).fontSize);
  probe.remove(); return size;
}
export function canvasContext(canvas) {
  const { width, height } = canvas.getBoundingClientRect(), ratio = globalThis.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(width * ratio)); canvas.height = Math.max(1, Math.round(height * ratio));
  const ctx = canvas.getContext("2d"); ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height); return { ctx, width, height };
}
