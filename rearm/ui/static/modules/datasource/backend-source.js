import { ARM_PARAMS } from "../arm/arm-params.js";
import { createEmitter } from "./frame.js";
import { createMockConsole } from "./mock-console.js";

const READ_ONLY = "第一档只读：生产指令由后端第二档提供";
const STATE_URL = "/backend/api/state", COMMAND_URL = "/backend/api/cmd";
const CAMERA_URL = "/backend/api/camera/color.mjpg";
const six = values => Array.from({ length: 6 }, (_, i) => Number.isFinite(values?.[i]) ? values[i] : null);
const boolean = value => typeof value === "boolean" ? value : null;

function gripperState(state) {
  const refs = state.gripper_refs, q7 = state.telemetry?.q_rad?.[6];
  // 后端记录齿轮打滑：绝对 J7 零位不可信，只用当次力矩标定，不能沿用上一帧参考。
  const calibrated = !!refs && [refs.touch, refs.open, refs.mm_per_rad].every(Number.isFinite) &&
    refs.mm_per_rad > 0 && refs.touch !== refs.open;
  const valid = calibrated && !state.stale && Number.isFinite(q7) &&
    q7 >= Math.min(refs.touch, refs.open) - 0.3 && q7 <= Math.max(refs.touch, refs.open) + 0.3;
  const [lo, hi] = ARM_PARAMS.gripper.openingMm;
  return { gripper_mm: valid ? Math.min(hi, Math.max(lo, Math.abs(q7 - refs.touch) * refs.mm_per_rad)) : null,
    gripper_valid: valid, gripper_source: calibrated ? "当次力矩标定" : "未标定" };
}

function detectionBox(detection) {
  const { center_px: center, long_mm: long, short_mm: short, mm_per_px: scale, angle_deg: angle } = detection;
  if (!Array.isArray(center) || !center.slice(0, 2).every(Number.isFinite) || center.length < 2 ||
      ![long, short, scale, angle].every(Number.isFinite) || Math.min(long, short, scale) <= 0) return null;
  const radians = angle * Math.PI / 180, c = Math.abs(Math.cos(radians)), s = Math.abs(Math.sin(radians));
  const width = (long * c + short * s) / scale, height = (long * s + short * c) / scale;
  return [center[0] - width / 2, center[1] - height / 2, width, height];
}

// 传输与演示库组合；mock 的姿态、链路、生产事件不流入真机快照。
export function createBackendSource({ fetch: request = globalThis.fetch, now = Date.now,
  setTimer = setInterval, clearTimer = clearInterval } = {}) {
  const emitter = createEmitter(), commands = [];
  const demo = createMockConsole({ now, setTimer: () => null, clearTimer: () => {} });
  const metadata = { source: "后端面板", address: "/backend", read_only_reason: READ_ONLY, demo_data: true };
  let running = false, timer = null, pending = null, seq = 0, commandSeq = 0, generation = 0;
  let failures = 0, lastSuccess = 0, online = false, phase = "idle", greeted = false;
  const posts = new Set();
  function emit(type, fields = {}) {
    emitter.emit({ ...structuredClone(fields), v: 1, type, seq: ++seq, t: now() });
  }
  function link(value, reason) { online = value; emit("link", { ...metadata, online: value, reason }); }
  function runState() {
    emit("run_state", { run_id: null, recipe_id: null, phase, step_index: 0, step_total: 0, part_id: null });
  }
  demo.subscribe(message => {
    if (["library", "part_doc", "recipe_doc"].includes(message.type)) emit(message.type, message);
  });
  function snapshot(state) {
    const camera = state.camera || {}, intrinsics = camera.color_intrinsics;
    const image = intrinsics?.width > 0 && intrinsics?.height > 0 ?
      { width: intrinsics.width, height: intrinsics.height } : null;
    if (!greeted) {
      greeted = true;
      emit("hello", { ...metadata, proto: 1, host_version: "backend-readonly", sim: false,
        arm: { model: ARM_PARAMS.name, joints: 6 }, threshold_mm: null, camera: image });
      runState();
    }
    const telemetry = state.telemetry, q = six(telemetry?.q_rad), dq = six(telemetry?.dq_rad_s);
    const valid = q.map(value => !!telemetry && !state.stale && value !== null);
    emit("joint_state", { q, dq, valid, temp: six(telemetry?.t_rotor_c), current: six(telemetry?.tau_nm),
      temp_unit: "°C", current_unit: "N·m", ...gripperState(state),
      mode: phase === "estop" ? "estop" : "idle", pass: null, node: null,
      settled: valid.every(Boolean) && dq.every(value => value !== null && Math.abs(value) < 1e-8), fault: state.last_error ?? null });
    emit("device_state", { connected: boolean(state.connected), enabled: boolean(state.enabled), busy: boolean(state.busy),
      busy_action: state.busy_action ?? null, pose_error_deg: state.pose_error_deg ?? null,
      camera: { enabled: boolean(camera.enabled), fresh: boolean(camera.fresh), error: camera.error ?? null,
        image, url: camera.enabled && camera.fresh ? CAMERA_URL : null } });
    emit("recognition", { run_id: null, live: true, image, targets: (state.vision?.last?.detections || []).map(detection => ({
      id: detection.part_id, name: detection.part_id === 0 ? "未知物体" : detection.name || `零件 ${detection.part_id}`,
      confidence: null, box_px: detectionBox(detection),
    })) });
    emit("last_pick", { pick: state.last_pick ?? null });
  }
  async function poll() {
    const current = { controller: new AbortController(), at: now() }; pending = current;
    try {
      const response = await request(STATE_URL, { signal: current.controller.signal, cache: "no-store" });
      if (!response.ok) throw new Error(`后端状态读取失败（HTTP ${response.status}）`);
      const state = await response.json();
      if (!state || Array.isArray(state) || typeof state !== "object" || typeof state.connected !== "boolean")
        throw new Error("后端状态格式无效");
      if (!running || pending !== current) return;
      snapshot(state); failures = 0; lastSuccess = now(); link(true, "已连接");
    } catch (error) {
      if (!running || pending !== current) return;
      if (++failures >= 3 || now() - lastSuccess >= 3000) link(false, error.message || "后端不可达");
    } finally { if (pending === current) pending = null; }
  }
  function tick() {
    if (!running) return;
    if (now() - lastSuccess >= 3000 && (online || failures < 3)) link(false, "后端超过 3 秒无响应");
    if (pending && now() - pending.at >= 3000) { pending.controller.abort(); pending = null; }
    if (!pending) void poll();
  }
  return {
    kind: "backend", commands, subscribe: emitter.subscribe,
    start() {
      if (running) return;
      running = true; generation++; failures = 0; lastSuccess = now(); greeted = false;
      link(false, "正在连接后端"); demo.start(); timer = setTimer(tick, 200); tick();
    },
    stop() {
      if (!running) return;
      running = false; generation++; clearTimer(timer); timer = null;
      pending?.controller.abort(); pending = null;
      for (const cancel of posts) cancel();
      demo.stop(); link(false, "连接已关闭");
    },
    async send(cmd, args = {}) {
      const command = { ...structuredClone(args), v: 1, cmd, seq: ++commandSeq, t: now() }; commands.push(command);
      const reply = (ok, code = "ok", msg = "") => ({ v: 1, ok, code, msg, seq: command.seq });
      if (!["library_get", "part_get", "recipe_get", "estop", "reset_estop"].includes(cmd))
        return reply(false, "read_only", READ_ONLY);
      if (!running) return reply(false, "offline", "连接已关闭");
      if (["library_get", "part_get", "recipe_get"].includes(cmd)) {
        const result = await demo.send(cmd, args); return reply(result.ok, result.code, result.msg);
      }
      if (cmd === "reset_estop") {
        phase = "idle"; runState(); return reply(true, "ok", "已清除前端急停状态，请在后端面板重新使能");
      }
      const controller = new AbortController(), currentGeneration = generation;
      let timeout, cancel;
      const aborted = new Promise((_, reject) => {
        cancel = () => { controller.abort(); reject(new Error("请求已取消")); };
        timeout = setTimer(() => { controller.abort(); reject(new Error("后端 3 秒未确认，请检查后端面板")); }, 3000);
      });
      posts.add(cancel);
      try {
        await Promise.race([aborted, (async () => {
          const response = await request(COMMAND_URL, { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "estop" }), signal: controller.signal });
          const body = await response.json().catch(() => ({}));
          if (!response.ok || body?.ok === false || body?.error)
            throw new Error(body?.msg || body?.detail || body?.error || `HTTP ${response.status}`);
        })()]);
        if (!running || generation !== currentGeneration) return reply(false, "offline", "急停未确认：连接已关闭");
        phase = "estop"; runState(); return reply(true, "ok", "急停指令已送达后端");
      } catch (error) { return reply(false, "estop_failed", `急停失败：${error.message || "后端不可达"}`); }
      finally { clearTimer(timeout); posts.delete(cancel); }
    },
  };
}
