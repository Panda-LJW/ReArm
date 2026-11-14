// 面板数据源：监听主程序广播的 "rearm:state" 事件，取最近一发的关节读数。
// 这是目前的默认数据源：仿真时数据来自仿真臂，接上真机后来自上位机后端。
import { makeFrame, createEmitter } from "./frame.js";

export function createPanelSource({ target = document } = {}) {
  const emitter = createEmitter();
  const onState = event => {
    const { state, connected } = event.detail || {};
    const recent = state?.recent || [], last = recent[recent.length - 1];
    emitter.emit(makeFrame({
      angles_deg: last?.q ?? null,
      mode: !connected || !state ? "offline" : state.simulation ? "sim" : "live",
      laser: connected && state ? !!state.laser_on : null,
      timestamp: last?.timestamp,
    }));
  };
  return {
    kind: "panel",
    start() { target.addEventListener("rearm:state", onState); },
    stop() { target.removeEventListener("rearm:state", onState); },
    subscribe: emitter.subscribe,
  };
}
