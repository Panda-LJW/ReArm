import { swap } from "../../../widgets/motion.js";

// 样式未加载时直接显示内容；快速切换和卸载后不提交过期视图。
export function contentSwap(root) {
  const win = root.ownerDocument.defaultView;
  let sequence = 0;
  return {
    render(draw) {
      const request = ++sequence;
      const styled = win.getComputedStyle(root).getPropertyValue("--t-fast").trim();
      return swap(root, () => {
        if (request !== sequence) return;
        sequence++; draw();
      }, styled ? win : { matchMedia: () => ({ matches: true }) });
    },
    cancel() { sequence++; root.classList.remove("c-swap-in", "c-swap-out"); },
  };
}
