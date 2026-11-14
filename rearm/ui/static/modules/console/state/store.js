export function initialState() {
  return { link: { online: false }, hello: null, joint: null, phase: "idle", run: null,
    selfcheck: {}, recognition: null, step: null, inspection: null, runs: [], training: null, trains: [],
    library: { parts: [], recipes: [] }, partDocs: {}, recipeDocs: {}, candidate: null, stamps: {}, reset: null };
}
function newer(a, b) {
  return !b || (a.t === b.t ? a.seq > b.seq : a.t > b.t);
}
function replace(rows, key, row) {
  return [...rows.filter(r => r[key] !== row[key]), row].sort((a, b) => a.t - b.t || a.seq - b.seq);
}
function slot(m) {
  if (m.type === "selfcheck_item") return `${m.type}:${m.run_id}:${m.item}`;
  if (["part_doc", "recipe_doc"].includes(m.type)) return `${m.type}:${m.id}`;
  if (m.type === "run_done") return `${m.type}:${m.run_id}`;
  if (m.type === "train_done") return `${m.type}:${m.train_id}`;
  return m.type;
}

// 只归并消息；不读时钟、不触碰 DOM，也不从视图取统计值。
export function reduce(state, message) {
  if (!message || typeof message !== "object" || Array.isArray(message)) return state;
  if (message.type === "link") return { ...state, link: { ...message } };
  if (message.v !== 1 || !Number.isFinite(message.t) || !Number.isInteger(message.seq)) return state;
  if (!newer(message, state.reset) || !newer(message, state.stamps[slot(message)])) return state;
  const m = structuredClone(message);
  const next = { ...state, stamps: { ...state.stamps, [slot(m)]: { t: m.t, seq: m.seq } } };
  switch (m.type) {
    case "hello": return { ...next, hello: m };
    case "joint_state": return { ...next, joint: m };
    case "demo_reset": return { ...initialState(), link: state.link, hello: state.hello, joint: state.joint,
      library: state.library, partDocs: state.partDocs, recipeDocs: state.recipeDocs, reset: { t: m.t, seq: m.seq } };
    case "run_state": {
      const changed = m.run_id !== state.run?.run_id;
      return { ...next, run: m, phase: m.phase, step: null,
        ...(changed ? { selfcheck: {}, recognition: null, inspection: null } : {}),
        ...(m.phase === "estop" || (m.phase === "idle" && m.run_id === null) ? { training: null, candidate: null } : {}) };
    }
    case "selfcheck_item":
      return m.run_id === state.run?.run_id && state.phase !== "estop" ?
        { ...next, selfcheck: { ...state.selfcheck, [m.item]: m } } : state;
    case "recognition":
      return m.run_id === state.run?.run_id && state.phase !== "estop" ? { ...next, recognition: m } : state;
    case "step_state":
      return m.run_id === state.run?.run_id && ["pick", "place"].includes(state.phase) ? { ...next, step: m } : state;
    case "inspect_result":
      return m.run_id === state.run?.run_id && state.phase !== "estop" ? { ...next, inspection: m } : state;
    case "run_done": {
      if (state.phase === "estop") return state;
      const { run_id, recipe_id, ok, deviation_mm, duration_ms, t, seq } = m;
      return { ...next, runs: replace(state.runs, "run_id", { run_id, recipe_id, ok, deviation_mm, duration_ms, t, seq }) };
    }
    case "library": return { ...next, library: { parts: m.parts, recipes: m.recipes } };
    case "part_doc": return { ...next, partDocs: { ...state.partDocs, [m.id]: m } };
    case "recipe_doc": return { ...next, recipeDocs: { ...state.recipeDocs, [m.id]: m } };
    case "part_candidate": return state.phase === "estop" ? state : { ...next, candidate: m };
    case "train_progress": {
      if (state.phase === "estop" || state.trains.some(row => row.train_id === m.train_id)) return state;
      const old = state.training?.train_id === m.train_id ? state.training : { rounds: [] };
      return { ...next, training: { train_id: m.train_id, target: m.target, last: m,
        rounds: m.round === 0 ? old.rounds : replace(old.rounds, "round", m) } };
    }
    case "train_done": {
      const active = state.training;
      if (!active || active.train_id !== m.train_id) return state;
      const { target, rounds, last } = active;
      return { ...next, training: null, trains: replace(state.trains, "train_id", { ...m, target,
        rounds, round: last.round, deviation_mm: last.deviation_mm, elapsed_ms: last.elapsed_ms, images: last.images }) };
    }
    default: return state;
  }
}

export function createStore() {
  let state = initialState();
  const listeners = new Set();
  return {
    getState: () => state,
    dispatch(message) {
      const next = reduce(state, message);
      if (next !== state) { state = next; for (const listener of [...listeners]) listener(state); }
      return state;
    },
    subscribe(listener) { listeners.add(listener); listener(state); return () => listeners.delete(listener); },
  };
}
