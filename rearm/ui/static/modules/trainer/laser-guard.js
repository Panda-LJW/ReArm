import { CONFIG } from "./config.js";

export function createLaserGuard({ send, now = Date.now, setTimer = setInterval,
  clearTimer = clearInterval, config = CONFIG } = {}) {
  const defaults = { ...CONFIG, ...config }, settings = { ...defaults }, measured = new Set();
  let want = false, auto = false, manual = false, activeNode = null;
  let online = false, mode = "idle", renew = null, timeout = null, suspended = false;
  let lastShutdown = -Infinity, openedAt = null;
  const key = node => JSON.stringify([node.pass, node.node]);
  const blocked = () => mode === "estop" || mode === "fault";
  function command(cmd, args = {}) {
    try { Promise.resolve(send(cmd, args)).catch(() => {}); } catch { /* 断线时也尝试关；TTL 是主机兜底。 */ }
  }
  function close(force = false) {
    const needed = want || renew !== null;
    clearTimer(renew); clearTimer(timeout);
    renew = timeout = null;
    want = auto = manual = false;
    activeNode = null;
    if (needed || force) command("laser_off");
  }
  function safetyClose() {
    const t = now(), force = t - lastShutdown >= 200;
    lastShutdown = t;
    close(force);
  }
  function startRenewal() {
    clearTimer(renew);
    renew = setTimer(() => {
      if (want) command("laser_renew", { ttl_ms: settings.laserTtlMs });
    }, Math.min(1000, settings.laserTtlMs / 3));
  }
  function startNodeTimeout() {
    clearTimer(timeout); timeout = null;
    if (!activeNode) return;
    const expire = () => { measured.add(key(activeNode)); close(); };
    const remaining = settings.nodeTimeoutMs - (now() - openedAt);
    if (remaining <= 0) expire();
    else timeout = setTimer(expire, remaining);
  }
  function open(node = null) {
    want = true; auto = node !== null; manual = !auto;
    activeNode = node; openedAt = now();
    startRenewal(); startNodeTimeout();
    if (want) command("laser_on", { ttl_ms: settings.laserTtlMs });
  }
  return {
    onMessage(message) {
      if (message.type === "hello") {
        const positive = (value, fallback) => Number.isFinite(value) && value > 0 ? value : fallback;
        const ttl = positive(message.laser_ttl_ms, defaults.laserTtlMs);
        const wait = positive(message.node_timeout_ms, defaults.nodeTimeoutMs);
        const changedTtl = ttl !== settings.laserTtlMs, changedWait = wait !== settings.nodeTimeoutMs;
        settings.laserTtlMs = ttl; settings.nodeTimeoutMs = wait;
        if (want && changedTtl) startRenewal();
        if (want && changedWait) startNodeTimeout();
      } else if (message.type === "link") {
        online = message.online === true;
        if (!online) {
          if (activeNode) measured.add(key(activeNode));
          safetyClose();
        }
      } else if (message.type === "joint_state") {
        const previous = mode;
        mode = message.mode;
        if (blocked()) {
          if (mode !== previous || want) safetyClose();
          return;
        }
        if (mode !== previous) {
          if (mode === "practice" || previous === "practice") close();
          if (mode === "practice") measured.clear();
        }
        if (mode !== "practice" || !online || suspended) return;
        const node = message.pass != null && message.node != null ? { pass: message.pass, node: message.node } : null;
        if (activeNode && (!node || key(node) !== key(activeNode) || !message.settled)) {
          measured.add(key(activeNode)); close();
        }
        if (node && message.settled && !activeNode && !measured.has(key(node))) open(node);
      } else if (message.type === "node_result") {
        measured.add(key(message));
        if (activeNode && key(activeNode) === key(message)) close();
      }
    },
    manual(on) {
      if (!online || mode === "practice" || blocked()) return false;
      if (on) {
        suspended = false; // 重新手动打开是一次显式意图。
        if (!want) open();
      } else close();
      return true;
    },
    shutdown(reason) {
      // 生命周期关闭后不由后续遥测自行重开；页面重新启用时创建新的 guard。
      suspended = true;
      safetyClose();
    },
    state() { return { want, auto, manual, activeNode: activeNode ? { ...activeNode } : null }; },
  };
}
