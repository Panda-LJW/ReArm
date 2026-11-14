// 模拟数据源：不依赖任何后端，在关节限位内循环几个姿态，用于离线演示和单独调试显示模块。
import { makeFrame, createEmitter } from "./frame.js";

const POSES = [[0, 40, -100], [28, 62, -118], [-24, 78, -132], [12, 30, -84], [-35, 55, -110]];

export function createSimSource({ periodMs = 50, holdMs = 1800, moveMs = 1400, now = () => Date.now() } = {}) {
  const emitter = createEmitter();
  let timer = null, started = 0;
  const ease = t => t * t * (3 - 2 * t);
  // 纯函数，便于测试：给定经过的毫秒数，返回当时的关节角。
  function anglesAt(elapsed) {
    const span = holdMs + moveMs, step = Math.floor(elapsed / span), within = elapsed % span;
    const from = POSES[step % POSES.length], to = POSES[(step + 1) % POSES.length];
    const k = within < holdMs ? 0 : ease((within - holdMs) / moveMs);
    return from.map((v, i) => v + (to[i] - v) * k);
  }
  const tick = () => emitter.emit(makeFrame({ angles_deg: anglesAt(now() - started), mode: "sim", laser: (now() - started) % (holdMs + moveMs) < holdMs }));
  return {
    kind: "sim", anglesAt,
    start() { if (timer) return; started = now(); tick(); timer = setInterval(tick, periodMs); },
    stop() { clearInterval(timer); timer = null; },
    subscribe: emitter.subscribe,
  };
}
