// 每个视图只保留本帧最后一次 render；dispose 后不再写 DOM。
export function frameView(draw, cleanup = () => {}, win = window) {
  let frame = null, latest, disposed = false;
  return {
    render(state) {
      if (disposed) return;
      latest = state;
      if (frame !== null) return;
      frame = win.requestAnimationFrame(() => {
        frame = null;
        if (!disposed) draw(latest);
      });
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      if (frame !== null) win.cancelAnimationFrame(frame);
      cleanup();
    },
  };
}
