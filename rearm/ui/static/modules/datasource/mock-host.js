// 浏览器内模拟主机：只有本地计时和运动学，不访问网络。advance 与实时计时共用同一个事件循环。
import { ARM_PARAMS } from "../arm/arm-params.js";
import { endPoses, laserRay } from "../arm/fk.js";
import { CONFIG } from "../trainer/config.js";
import { number } from "../trainer/format.js";
import { createEmitter } from "./frame.js";

const DEMO_MS = 6000, HOLD_MS = 800, MEASURE_MS = 400;
// 开口取总行程的比例；关节是各自限位内的比例，避免另存一份硬件限位。
const POSES = [
  [0.50, 0.48, 0.53, 0.48, 0.50, 0.50],
  [0.55, 0.55, 0.43, 0.55, 0.45, 0.55],
  [0.57, 0.60, 0.39, 0.59, 0.48, 0.57],
  [0.46, 0.47, 0.55, 0.43, 0.56, 0.46],
  [0.50, 0.48, 0.53, 0.48, 0.50, 0.50],
];
const OPENINGS = [0.9, 0.9, 0.2, 0.2, 0.9];
const ease = x => x * x * (3 - 2 * x);
const mix = (a, b, k) => a + (b - a) * k;
const clone = value => JSON.parse(JSON.stringify(value));
function poseAt(elapsed) {
  const phase = Math.min(4, Math.max(0, elapsed / DEMO_MS * 4));
  const i = Math.min(3, Math.floor(phase)), k = ease(phase - i);
  return {
    q: ARM_PARAMS.joints.map((joint, axis) => mix(...joint.limit, mix(POSES[i][axis], POSES[i + 1][axis], k))),
    gripper_mm: mix(...ARM_PARAMS.gripper.openingMm, mix(OPENINGS[i], OPENINGS[i + 1], k)),
  };
}
function spot(q) {
  const { origin, direction } = laserRay(ARM_PARAMS, q);
  return origin.map((v, i) => (v + direction[i] * 0.25) * 1000);
}
function end(q) {
  const matrix = endPoses(ARM_PARAMS, q).end_link;
  return [matrix[3], matrix[7], matrix[11]].map(v => v * 1000);
}
// 用示范节点的相机坐标作为共同投影平面，参考/实测点才可在同一画面比较。
// 相机局部 +X 向前、+Y 向左、+Z 向上；R 的转置把基座坐标变回相机坐标。
function pixels(point, q, camera) {
  const matrix = endPoses(ARM_PARAMS, q).camera;
  const relative = point.map((v, i) => v / 1000 - matrix[i * 4 + 3]);
  const [depth, left, up] = [0, 1, 2].map(axis => relative.reduce((sum, v, i) => sum + matrix[i * 4 + axis] * v, 0));
  if (depth <= 0) return null;
  const fx = camera.width / (2 * Math.tan(ARM_PARAMS.camera.horizontalFovDeg * Math.PI / 360));
  const fy = camera.height / (2 * Math.tan(ARM_PARAMS.camera.verticalFovDeg * Math.PI / 360));
  return [camera.width / 2 - fx * left / depth, camera.height / 2 - fy * up / depth];
}

export function createMockHost({ now = Date.now, setTimer = setInterval, clearTimer = clearInterval,
  rateHz = 20, seed = 1, camera = {} } = {}) {
  if (!Number.isFinite(rateHz) || rateHz <= 0) throw new RangeError("rateHz 必须大于 0");
  const emitter = createEmitter(), received = [], period = 1000 / rateHz;
  const cameraInfo = { url: null, format: null,
    width: Number.isFinite(camera.width) && camera.width > 0 ? camera.width : 640,
    height: Number.isFinite(camera.height) && camera.height > 0 ? camera.height : 480 };
  let clock = now(), timer = null, running = false, seq = 0, commandSeq = 0, demoId = 0;
  let nextFrame = Infinity, nextStatus = Infinity, mode = "idle", pose = poseAt(0);
  let demoStart = null, samples = [], demo = null, practice = null;
  let laser = false, expires = Infinity, laserReason = "initial", randomState = seed >>> 0;
  let previousPose = null, previousTime = null;
  const random = () => { randomState = (Math.imul(randomState, 1664525) + 1013904223) >>> 0; return randomState / 4294967296; };
  function emit(type, fields = {}) {
    const message = { ...fields, v: 1, type, seq: ++seq, t: clock };
    emitter.emit(message);
    return message;
  }
  function laserState() {
    emit("laser_state", { on: laser, source: "software", remaining_ms: laser ? Math.max(0, expires - clock) : 0, reason: laserReason });
  }
  function setLaser(on, reason, ttl = CONFIG.laserTtlMs) {
    laser = on; expires = on ? clock + ttl : Infinity; laserReason = reason;
    if (practice?.phase === "hold" && !practice.done) {
      practice.resultAt = on ? clock + MEASURE_MS : Infinity;
    }
    laserState();
  }
  function joint() {
    const dt = previousTime === null ? 0 : (clock - previousTime) / 1000;
    const dq = pose.q.map((v, i) => dt > 0 ? (v - previousPose[i]) / dt : 0);
    previousPose = [...pose.q]; previousTime = clock;
    const message = emit("joint_state", { mode, q: [...pose.q], dq,
      current: dq.map(v => 0.2 + Math.abs(v) * 0.15), temp: Array(6).fill(28), valid: Array(6).fill(true),
      gripper_mm: pose.gripper_mm, gripper_valid: true, pass: practice?.pass ?? null,
      node: practice?.phase === "hold" ? demo.nodes[practice.index].id : null,
      settled: practice?.phase === "hold", fault: null });
    if (mode === "demo") samples.push({ t: message.t, q: [...message.q], gripper_mm: message.gripper_mm });
  }
  function finishDemo() {
    if (mode !== "demo") return;
    // 真实流程是人点第二次才结束；动作走完后停在终点等人点结束。停住的那段不算进示范轨迹。
    const moving = samples.filter(sample => sample.t <= samples[0].t + DEMO_MS);
    if (moving.length > 1) samples = moving;
    const nodes = [0.2, 0.45, 0.7, 1].map((fraction, index) => {
      const sample = samples[Math.round((samples.length - 1) * fraction)], ref = spot(sample.q);
      return { ...clone(sample), id: index + 1, gripper_state: sample.gripper_mm < 20 ? "closed" : "open",
        ref_spot_base_mm: ref, ref_spot_px: pixels(ref, sample.q, cameraInfo), end_base_mm: end(sample.q) };
    });
    demo = { demo_id: `mock-${++demoId}`, samples: clone(samples), nodes };
    mode = "idle"; demoStart = null;
    emit("demo_trajectory", clone(demo)); joint();
  }
  function recordedAt(offset) {
    const target = demo.samples[0].t + offset;
    let index = demo.samples.findIndex(sample => sample.t >= target);
    if (index < 0) index = demo.samples.length - 1;
    const b = demo.samples[index], a = demo.samples[Math.max(0, index - 1)];
    const k = b.t === a.t ? 0 : Math.min(1, Math.max(0, (target - a.t) / (b.t - a.t)));
    return { q: a.q.map((v, i) => mix(v, b.q[i], k)), gripper_mm: mix(a.gripper_mm, b.gripper_mm, k) };
  }
  function biased(recorded, magnitude) {
    // 绕 J1 的转动让光点沿基座 Z 轴转动；弦长反算角度，使实际 FK 偏差等于目标毫米数。
    const ref = spot(recorded.q), origin = ARM_PARAMS.joints[0].xyz;
    const radius = Math.hypot(ref[0] - origin[0] * 1000, ref[1] - origin[1] * 1000);
    const delta = 2 * Math.asin(Math.min(1, magnitude / (2 * radius)));
    const q = [...recorded.q];
    q[0] += Math.min(delta, ARM_PARAMS.joints[0].limit[1] - q[0]);
    return { q, gripper_mm: recorded.gripper_mm };
  }
  function updatePose() {
    if (mode === "demo") pose = poseAt(clock - demoStart);
    if (mode === "practice" && practice.phase === "move") {
      pose = biased(recordedAt(practice.offset + clock - practice.started), practice.errors[practice.index]);
    }
  }
  const errorsFor = pass => demo.nodes.map(() => Math.max(2.5, 18 * 0.62 ** (pass - 1)) + (random() - 0.5) * 0.2);
  function beginPass(pass, errors = errorsFor(pass)) {
    practice = { pass, index: 0, phase: "move", offset: 0, started: clock,
      until: clock + demo.nodes[0].t - demo.samples[0].t, results: [],
      errors };
    updatePose(); joint();
  }
  function arrive() {
    const p = practice, node = demo.nodes[p.index];
    pose = biased(node, p.errors[p.index]);
    Object.assign(p, { phase: "hold", started: clock, deadline: clock + CONFIG.nodeTimeoutMs,
      resultAt: laser ? clock + MEASURE_MS : Infinity, done: false });
    joint(); // 守护器同步收到停稳帧后，可在此节点开启激光。
  }
  function measure(valid) {
    const p = practice, node = demo.nodes[p.index], measured = valid ? spot(pose.q) : null;
    const dev = measured?.map((v, i) => v - node.ref_spot_base_mm[i]) ?? null;
    p.done = true; p.until = Math.max(p.started + HOLD_MS, clock);
    const result = { pass: p.pass, node: node.id, spot_px: measured ? pixels(measured, node.q, cameraInfo) : null,
      depth_mm: valid ? 250 : null, spot_base_mm: measured, ref_spot_base_mm: [...node.ref_spot_base_mm],
      dev_mm: dev, dev_norm_mm: dev ? Math.hypot(...dev) : null,
      valid, invalid_reason: valid ? null : "spot_not_found", image_url: null, end_base_mm: end(pose.q) };
    p.results.push(result);
    emit("node_result", result);
  }
  function finishPass() {
    const p = practice, valid = p.results.filter(result => result.valid), values = valid.map(result => result.dev_norm_mm);
    const max = values.length ? Math.max(...values) : null;
    emit("pass_result", { pass: p.pass, max_mm: max, mean_mm: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
      valid_nodes: valid.length, total_nodes: demo.nodes.length,
      below_threshold: valid.length === demo.nodes.length && max < CONFIG.thresholdMm });
    // 消费者可在结果回调里停止练习；不再生成下一遍或声称已施加修正。
    if (mode !== "practice" || practice !== p) return;
    const worst = valid.reduce((a, b) => !a || b.dev_norm_mm > a.dev_norm_mm ? b : a, null);
    const nextErrors = errorsFor(p.pass + 1);
    const items = valid.map(result => {
      const index = demo.nodes.findIndex(node => node.id === result.node), node = demo.nodes[index];
      const delta = (biased(node, nextErrors[index]).q[0] - biased(node, p.errors[index]).q[0]) * 180 / Math.PI;
      return { target: "J1", delta, unit: "deg", note: `节点 ${node.id} 的下一遍目标角修正` };
    });
    const worstItem = worst ? items[valid.indexOf(worst)] : null;
    emit("correction", { pass: p.pass, applied: !!worst,
      items,
      llm_text: worst ? `第 ${p.pass} 遍在节点 ${worst.node} 偏差 ${number(worst.dev_norm_mm)} mm，下一遍 J1 目标角调整 ${number(worstItem.delta, 2)}°。`
        : `第 ${p.pass} 遍未找到激光点，本遍未应用修正。` });
    emit("event", { name: "pass_finished", text: `第 ${p.pass} 遍结束，${valid.length}/${demo.nodes.length} 个节点测量有效。`, level: values.length ? "info" : "warning" });
    if (mode === "practice" && practice === p) beginPass(p.pass + 1, nextErrors);
  }
  function nextPracticeEvent() {
    if (!practice) return Infinity;
    return practice.phase === "move" || practice.done ? practice.until : Math.min(practice.resultAt, practice.deadline);
  }
  function practiceEvent() {
    if (practice.phase === "move") return arrive();
    if (!practice.done) return measure(laser && clock >= practice.resultAt && practice.resultAt <= practice.deadline);
    const p = practice;
    if (p.index + 1 === demo.nodes.length) return finishPass();
    p.offset = demo.nodes[p.index].t - demo.samples[0].t;
    p.index++;
    p.until = clock + demo.nodes[p.index].t - demo.samples[0].t - p.offset;
    p.phase = "move"; p.started = clock;
    joint();
  }
  function advance(ms) {
    if (!Number.isFinite(ms) || ms < 0) throw new RangeError("advance 需要非负毫秒数");
    if (!running) return;
    const target = clock + ms;
    while (running) {
      const next = Math.min(nextFrame, nextStatus, expires, nextPracticeEvent());
      if (next > target) break;
      clock = next; updatePose();
      if (laser && clock >= expires) setLaser(false, "ttl_expired");
      if (practice && clock >= nextPracticeEvent()) practiceEvent();
      if (!running) break;
      if (clock >= nextFrame) { nextFrame += period; joint(); }
      if (clock >= nextStatus) { nextStatus += 1000; emit("heartbeat"); laserState(); }
    }
    clock = target; updatePose();
  }
  function halt() { practice = null; demoStart = null; mode = "idle"; }
  return {
    kind: "mock", advance,
    start() {
      if (running) return;
      running = true; clock = Math.max(clock, now()); nextFrame = clock + period; nextStatus = clock + 1000;
      emitter.emit({ type: "link", online: true, reason: "mock" });
      emit("hello", { proto: 1, host_version: "mock-v1", arm: { model: ARM_PARAMS.name, joints: 6 },
        threshold_mm: CONFIG.thresholdMm, camera: { ...cameraInfo }, sim: true,
        laser_ttl_ms: CONFIG.laserTtlMs, node_timeout_ms: CONFIG.nodeTimeoutMs });
      joint(); emit("heartbeat"); laserState();
      timer = setTimer(() => advance(Math.max(0, now() - clock)), period);
    },
    stop() {
      if (!running) return;
      running = false; clearTimer(timer); timer = null;
      const wasEstop = mode === "estop";
      halt(); if (wasEstop) mode = "estop";
      setLaser(false, "stopped");
      emitter.emit({ type: "link", online: false, reason: "stopped" });
    },
    subscribe: emitter.subscribe,
    commands() { return clone(received); },
    async send(cmd, args = {}) {
      const request = { ...args, v: 1, cmd, seq: ++commandSeq, t: clock };
      received.push(clone(request));
      const reply = (ok, code = "ok", msg = "") => ({ v: 1, ok, code, msg, seq: request.seq });
      if (!running) return reply(false, "offline", "模拟主机未启动");
      if (mode === "estop" && cmd !== "reset_estop") return reply(false, "estop", "请先解除急停");
      switch (cmd) {
        case "demo_start":
          if (mode !== "idle") return reply(false, "busy", "示范与练习互斥");
          mode = "demo"; demoStart = clock; samples = []; pose = poseAt(0); joint(); break;
        case "demo_stop": finishDemo(); break;
        case "practice_start":
          if (mode !== "idle") return reply(false, "busy", "示范与练习互斥");
          if (!demo) return reply(false, "no_demo", "请先完成示范");
          mode = "practice"; beginPass(1); break;
        case "practice_stop": if (mode === "practice") { halt(); joint(); } break;
        case "estop": halt(); mode = "estop"; setLaser(false, "estop"); joint(); break;
        case "reset_estop": if (mode === "estop") { mode = "idle"; joint(); } break;
        case "laser_on":
        case "laser_renew": {
          const ttl = args.ttl_ms ?? CONFIG.laserTtlMs;
          if (!Number.isFinite(ttl) || ttl <= 0) return reply(false, "ttl", "ttl_ms 必须大于 0");
          if (cmd === "laser_renew" && !laser) return reply(false, "laser_off", "激光已关闭，不能续期");
          // 续期不重新启动正在进行的测量。
          const resultAt = practice?.resultAt;
          setLaser(true, cmd, ttl);
          if (cmd === "laser_renew" && practice?.phase === "hold") practice.resultAt = resultAt;
          break;
        }
        case "laser_off": setLaser(false, "command"); break;
        case "mark_node": return reply(false, "unsupported", "模拟主机自动分成 4 个节点");
        default: return reply(false, "unknown_command", "未知指令");
      }
      return reply(true);
    },
  };
}
