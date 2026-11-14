// 接口 v1 原始消息的数据源；连接失败只报告离线，不选择其他数据源。
import { createEmitter } from "./frame.js";

export function commandUrl(wsUrl) {
  if (typeof wsUrl !== "string" || !/^wss?:\/\//.test(wsUrl)) {
    throw new TypeError("backend 参数必须是 ws:// 或 wss:// 地址");
  }
  const url = new URL(wsUrl);
  url.protocol = url.protocol === "wss:" ? "https:" : "http:";
  url.pathname = "/api/v1/command";
  url.search = "";
  url.hash = "";
  return url.href;
}

export function createHostSource({ url, WebSocketImpl = globalThis.WebSocket,
  fetchImpl = globalThis.fetch, offlineAfterMs = 3000, retryMs = 1000 } = {}) {
  const endpoint = commandUrl(url), emitter = createEmitter();
  let socket = null, watchdog = null, retry = null, stopped = true, online = null, reasonLast = null, seq = 0;
  function link(value, reason) {
    if (online === value && (value || reasonLast === reason)) return;
    online = value; reasonLast = reason;
    emitter.emit({ type: "link", online: value, reason });
  }
  function feed() {
    clearTimeout(watchdog);
    watchdog = setTimeout(() => link(false, "timeout"), offlineAfterMs);
  }
  function disconnect(candidate, reason) {
    if (socket !== candidate || stopped) return;
    socket = null;
    clearTimeout(watchdog);
    if (candidate) {
      candidate.onopen = candidate.onmessage = candidate.onerror = candidate.onclose = null;
      try { candidate.close(); } catch { /* 仍然安排重连 */ }
    }
    link(false, reason);
    retry = setTimeout(open, retryMs);
  }
  function open() {
    if (stopped) return;
    let candidate;
    try { candidate = new WebSocketImpl(url); }
    catch { disconnect(null, "connect_failed"); return; }
    socket = candidate;
    feed();
    candidate.onopen = () => {
      if (socket !== candidate || stopped) return;
      feed(); link(true, "connected");
    };
    candidate.onmessage = event => {
      if (socket !== candidate || stopped) return;
      feed(); // 链路超时按任何收到的消息计时；无效载荷不进入状态归并。
      let message = event.data;
      try { if (typeof message === "string") message = JSON.parse(message); } catch { return; }
      if (!message || typeof message !== "object" || Array.isArray(message) || message.v !== 1) return;
      link(true, "message");
      emitter.emit(message);
    };
    candidate.onerror = () => disconnect(candidate, "error");
    candidate.onclose = () => disconnect(candidate, "closed");
  }
  return {
    kind: "host",
    start() { if (!stopped) return; stopped = false; link(false, "connecting"); open(); },
    stop() {
      stopped = true;
      clearTimeout(watchdog); clearTimeout(retry);
      const previous = socket;
      socket = null;
      if (previous) {
        previous.onopen = previous.onmessage = previous.onerror = previous.onclose = null;
        try { previous.close(); } catch { /* 停止后不重连 */ }
      }
      link(false, "stopped");
    },
    subscribe: emitter.subscribe,
    async send(cmd, args = {}) {
      const body = { ...args, v: 1, cmd, seq: ++seq, t: Date.now() };
      try {
        const response = await fetchImpl(endpoint, { method: "POST",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        return await response.json();
      } catch (error) {
        return { ok: false, code: "network", msg: String(error?.message ?? error) };
      }
    },
  };
}
