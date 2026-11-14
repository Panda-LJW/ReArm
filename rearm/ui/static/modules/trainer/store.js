export function initialState() {
  return { link: { online: false }, stale: true, hello: null, mode: "idle", joint: null,
    demo: null, passes: [], laser: null, laserCommand: null, events: [], currentNode: null, t: null };
}

// 同一槽位只保留最新消息；不同遍/节点的迟到结果仍可补齐历史。
function newer(message, previous) {
  if (!previous) return true;
  if (Number.isFinite(message.t) && Number.isFinite(previous.t) && message.t !== previous.t) {
    return message.t > previous.t;
  }
  return !(Number.isFinite(message.seq) && Number.isFinite(previous.seq)) || message.seq > previous.seq;
}

export function reduce(state, message) {
  if (!message || typeof message !== "object" || Array.isArray(message)) return { ...state };
  if (message.v !== undefined && message.v !== 1) return { ...state };
  const next = { ...state, t: Number.isFinite(message.t) ? Math.max(state.t ?? message.t, message.t) : state.t };
  switch (message.type) {
    case "link":
      return { ...next, link: { ...message }, stale: !message.online };
    case "hello":
      return newer(message, state.hello) ? { ...next, hello: message } : next;
    case "joint_state":
      if (!newer(message, state.joint)) return next;
      return { ...next, joint: message, mode: message.mode,
        currentNode: message.pass != null && message.node != null ? { pass: message.pass, node: message.node } : null };
    case "demo_trajectory":
      return newer(message, state.demo) ? { ...next, demo: message } : next;
    case "laser_state":
      return newer(message, state.laser) ? { ...next, laser: message } : next;
    case "panel_laser":
      return newer(message, state.laserCommand) ? { ...next, laserCommand: message } : next;
    case "node_result":
    case "pass_result":
    case "correction": {
      if (!Number.isInteger(message.pass) || message.pass < 1) return next;
      if (message.type === "node_result" && message.node == null) return next;
      const previous = state.passes.find(item => item.pass === message.pass)
        ?? { pass: message.pass, nodes: {}, result: null, correction: null };
      const key = message.type === "node_result" ? "nodes" : message.type === "pass_result" ? "result" : "correction";
      const old = key === "nodes" ? previous.nodes[message.node] : previous[key];
      if (!newer(message, old)) return next;
      const item = { ...previous, [key]: key === "nodes" ? { ...previous.nodes, [message.node]: message } : message };
      return { ...next, passes: [...state.passes.filter(row => row.pass !== message.pass), item].sort((a, b) => a.pass - b.pass) };
    }
    case "event":
    case "error": {
      if (state.events.some(event => event.type === message.type && event.seq === message.seq && event.t === message.t)) return next;
      return { ...next, events: [...state.events, message].slice(-100) };
    }
    default: return next;
  }
}
