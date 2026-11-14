import { ARM_PARAMS } from "../arm/arm-params.js";
import { createEmitter } from "./frame.js";
import { POSES, OPEN_MM } from "./fixtures/poses.js";
import { THRESHOLD_MM } from "./fixtures/parts.js";
import { WORKSPACE } from "./fixtures/workspace.js";
import { createTimeline } from "./mock-console/timeline.js";
import { createLibrary, clone } from "./mock-console/library.js";
import { scheduleProduction } from "./mock-console/production.js";
import { scheduleTraining } from "./mock-console/training.js";

export function createMockConsole({ now = Date.now, setTimer = setInterval, clearTimer = clearInterval, seed = 1 } = {}) {
  const emitter = createEmitter(), commands = [], library = createLibrary();
  const folded = () => ({ q: [...POSES.folded], gripper_mm: OPEN_MM });
  const timeline = createTimeline(now(), folded());
  let running = false, timer = null, seq = 0, commandSeq = 0, runSerial = 0, trainSerial = 0;
  let phase = "idle", training = false, capturing = false, completed = 0, randomState = seed >>> 0;
  let run = { run_id: null, recipe_id: null, step_index: 0, step_total: 0, part_id: null };
  let previous = null;
  const random = () => { randomState = (Math.imul(randomState, 1664525) + 1013904223) >>> 0; return randomState / 4294967296; };
  function emit(type, fields = {}) {
    if (type === "run_state") { phase = fields.phase; run = fields; }
    if (type === "run_done") completed++;
    if (type === "train_done") training = false;
    const message = { ...clone(fields), v: 1, type, seq: ++seq, t: timeline.time() };
    emitter.emit(message); return message;
  }
  function joint() {
    const pose = timeline.pose(), t = timeline.time(), dt = previous ? (t - previous.t) / 1000 : 0;
    const dq = pose.q.map((v, i) => dt > 0 ? (v - previous.q[i]) / dt : 0);
    previous = { q: pose.q, t };
    emit("joint_state", { mode: phase === "estop" ? "estop" : phase !== "idle" || training || capturing ? "practice" : "idle", ...pose, dq,
      current: Array(6).fill(0.2), temp: Array(6).fill(28), valid: Array(6).fill(true),
      gripper_valid: true, pass: null, node: null, settled: dq.every(v => Math.abs(v) < 1e-8), fault: null });
  }
  function frame() {
    timeline.at(timeline.time() + 50, () => { if (running) { frame(); joint(); } });
  }
  function halt() {
    timeline.cancel(); training = false; capturing = false; previous = null;
    if (running) frame();
  }
  function idle() { emit("run_state", { run_id: null, recipe_id: null, phase: "idle", step_index: 0, step_total: 0, part_id: null }); }
  const advance = ms => timeline.advance(ms, () => running);
  return {
    kind: "mock", commands, advance, subscribe: emitter.subscribe,
    start() {
      if (running) return;
      timeline.advance(Math.max(0, now() - timeline.time())); running = true;
      emitter.emit({ type: "link", online: true, reason: "connected" });
      emit("hello", { proto: 1, host_version: "console-v1", arm: { model: ARM_PARAMS.name, joints: 6 },
        threshold_mm: THRESHOLD_MM, camera: { ...WORKSPACE.image, url: null, format: null }, sim: true });
      emit("library", library.snapshot()); emit("run_state", { ...run, phase }); joint(); frame();
      timer = setTimer(() => advance(Math.max(0, now() - timeline.time())), 50);
    },
    stop() {
      if (!running) return;
      running = false; clearTimer(timer); timer = null; halt();
      if (phase !== "estop") idle();
      emitter.emit({ type: "link", online: false, reason: "stopped" });
    },
    async send(cmd, args = {}) {
      const request = { ...clone(args), v: 1, cmd, seq: ++commandSeq, t: timeline.time() };
      commands.push(request);
      const reply = (ok, code = "ok", msg = "") => ({ v: 1, ok, code, msg, seq: request.seq });
      if (!running) return reply(false, "offline", "连接已关闭");
      if (phase === "estop" && !["reset_estop", "reset_demo"].includes(cmd)) return reply(false, "estop", "请先解除急停");
      const busy = phase !== "idle" || training || capturing;
      switch (cmd) {
        case "estop": halt(); emit("run_state", { ...run, phase: "estop" }); joint(); break;
        case "reset_estop": if (phase === "estop") { halt(); idle(); joint(); } break;
        case "reset_demo":
          halt(); completed = 0; randomState = seed >>> 0; timeline.setPose(folded());
          emit("demo_reset"); idle(); joint(); break;
        case "library_get": emit("library", library.snapshot()); break;
        case "part_get":
        case "recipe_get": {
          const target = cmd === "part_get" ? "part" : "recipe", doc = library.get(target, args.id);
          if (!doc) return reply(false, "not_found", "文档不存在");
          emit(`${target}_doc`, doc); break;
        }
        case "run_start": {
          if (busy) return reply(false, "busy", "正在执行其他操作");
          const recipe = library.get("recipe", args.recipe_id);
          if (!recipe) return reply(false, "not_found", "配方不存在");
          const ok = completed === 0 || random() < 0.9;
          const deviation_mm = completed === 0 ? 0.4 : Math.round((ok ? 0.3 + random() * 0.3 : 1.1 + random() * 0.8) * 10) / 10;
          scheduleProduction({ timeline, emit, recipe, parts: library.parts,
            runId: `run-${++runSerial}`, result: { ok, deviation_mm } });
          advance(0); break;
        }
        case "part_capture":
          if (busy) return reply(false, "busy", "正在执行其他操作");
          capturing = true;
          timeline.move({ q: POSES.observe, gripper_mm: OPEN_MM }, 1500);
          timeline.at(timeline.time() + 1500, () => { capturing = false; emit("part_candidate", library.candidate()); }); break;
        case "train_start":
          if (busy) return reply(false, "busy", "正在执行其他操作");
          if (!library.validate(args.target, args.draft)) return reply(false, "invalid_args", "请检查名称、编号和训练对象");
          training = true;
          scheduleTraining({ timeline, emit, library, trainId: `train-${++trainSerial}`, target: args.target, draft: clone(args.draft) });
          break;
        default: return reply(false, "unknown_command", "未知指令");
      }
      return reply(true);
    },
  };
}
