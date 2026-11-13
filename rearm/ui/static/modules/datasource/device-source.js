// 下位机数据源：按《docs/下位机接口文档.md》的 WebSocket 文本帧接收遥测。
// 默认不会被启用；只有地址栏显式带 ?twin=device&device=ws://… 时才连接。只收不发，不下发任何指令。
import { makeFrame, createEmitter } from "./frame.js";

export const PROTOCOL_VERSION = 1;
export const HEARTBEAT_TIMEOUT_MS = 1000;

// 把一条遥测报文整理成 JointFrame；格式不对返回 null。纯函数，便于测试。
export function parseTelemetry(message) {
  let data = message;
  if (typeof message === "string") { try { data = JSON.parse(message); } catch { return null; } }
  if (!data || data.v !== PROTOCOL_VERSION || data.type !== "telemetry" || !Array.isArray(data.joints)) return null;
  const angles = [...data.joints].sort((a, b) => a.id - b.id).map(j => Number(j.pos_deg));
  if (!angles.length || !angles.every(Number.isFinite)) return null;
  return makeFrame({ angles_deg: angles, mode: data.sim ? "sim" : "live", laser: typeof data.laser === "boolean" ? data.laser : null, timestamp: Number(data.t_ms) / 1000 });
}

export function createDeviceSource({ url, WebSocketImpl = globalThis.WebSocket, timeoutMs = HEARTBEAT_TIMEOUT_MS, retryMs = 1000 } = {}) {
  const emitter = createEmitter();
  let socket = null, watchdog = null, retry = null, stopped = true, lastAngles = null;
  const offline = () => emitter.emit(makeFrame({ angles_deg: lastAngles, mode: "offline" }));
  const feed = () => { clearTimeout(watchdog); watchdog = setTimeout(offline, timeoutMs); };
  function open() {
    if (stopped || !url) return offline();
    socket = new WebSocketImpl(url);
    socket.onmessage = event => {
      const frame = parseTelemetry(event.data);
      if (!frame) return; // 心跳或未知报文：不刷新姿态
      lastAngles = frame.angles_deg; feed(); emitter.emit(frame);
    };
    socket.onerror = () => socket?.close();
    socket.onclose = () => { clearTimeout(watchdog); offline(); if (!stopped) retry = setTimeout(open, retryMs); };
  }
  return {
    kind: "device",
    start() { if (!stopped) return; stopped = false; offline(); open(); },
    stop() { stopped = true; clearTimeout(watchdog); clearTimeout(retry); socket?.close(); socket = null; },
    subscribe: emitter.subscribe,
  };
}
