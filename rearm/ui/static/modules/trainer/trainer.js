import { trainerSourceFromParams, makeFrame } from "../datasource/index.js";
import { ARM_PARAMS } from "../arm/arm-params.js";
import { checkJoints, endPoses } from "../arm/fk.js";
import { buildPath } from "../arm/trajectory.js";
import { initialState, reduce } from "./store.js";
import { summarize } from "./metrics.js";
import { CONFIG } from "./config.js";
import { createLaserGuard } from "./laser-guard.js";
import { online, latestNode } from "./views/format.js";
import { mount as mountKpis } from "./views/kpis.js";
import { mount as mountJoints } from "./views/joints.js";
import { mount as mountFeed } from "./views/feed.js";
import { mount as mountChart } from "./views/deviation-chart.js";
import { mount as mountCorrections } from "./views/corrections.js";
import { mount as mountCamera } from "./views/camera.js";
import { mount as mountControls, buttonStates } from "./views/controls.js";

const home = () => !["overview", "codes"].includes(location.hash.slice(1));
const mmToM = p => Array.isArray(p) && p.length === 3 && p.every(Number.isFinite) ? p.map(v => v / 1000) : null;
export function initTrainer({ twin = null, params = new URLSearchParams() } = {}) {
  document.documentElement.dataset.claim = "kpis joints feed errchart diag cam actions";
  document.documentElement.dataset.trainer = "on";
  let state = initialState(), source, laserGuard, controls, unsubscribe, timer, raf = 0, disposed = false;
  let pass = null, samples = [], localSeq = 0, commandSeq = 0, panelEstop = false, mismatch = false, suspended = false;
  let demoCache = null, demoPath = [], nodes = [];
  const views = [], listeners = [];
  const ui = { pending: false, panelEstop: false, laserManual: false, active: home() && !document.hidden, hostname: "" };
  const listen = (target, event, fn, options) => { target.addEventListener(event, fn, options); listeners.push(() => target.removeEventListener(event, fn, options)); };
  const viewState = () => ({ ...state, ui: { ...ui, laserManual: laserGuard?.state().manual || false } });
  function event(text, level = "info") {
    state = reduce(state, { type: "event", seq: --localSeq, t: state.t ?? Date.now(), text, level });
  }
  function schedule() { if (!raf && !disposed) raf = requestAnimationFrame(render); }
  function render() {
    raf = 0; if (disposed) return;
    const current = viewState(), config = { ...CONFIG, thresholdMm: state.hello?.threshold_mm ?? CONFIG.thresholdMm };
    const summary = { ...summarize(current, config), thresholdMm: config.thresholdMm };
    if (summary.laserMismatch && !mismatch) event("激光状态不一致", "bad");
    mismatch = !!summary.laserMismatch;
    // Each view is rendered at most once in this animation frame.
    for (const view of views) view.render(viewState(), summary);
    if (!twin) return;
    const joint = state.joint, ready = online(state);
    twin.update(makeFrame({ q_rad: joint?.q, valid: joint?.valid, gripper_mm: joint?.gripper_mm,
      mode: !ready ? "offline" : state.hello.sim ? "sim" : "live", online: ready,
      laser: ready ? state.laser?.on ?? null : false, timestamp: joint?.t / 1000 }));
    if (demoCache !== state.demo) {
      demoCache = state.demo;
      demoPath = buildPath(ARM_PARAMS, state.demo?.samples || []).segments;
      nodes = (state.demo?.nodes || []).flatMap(node => {
        if (!checkJoints(ARM_PARAMS, node.q).ok || node.valid?.some(v => v !== true)) return [];
        const tcp = endPoses(ARM_PARAMS, node.q).tcp;
        return [{ id: node.id, p: [tcp[3], tcp[7], tcp[11]] }];
      });
    }
    const result = ready ? latestNode(state) : null;
    twin.setOverlay({ demoPath, runPath: buildPath(ARM_PARAMS, samples).segments,
      nodes: nodes.map(node => ({ ...node, current: ready && node.id === state.currentNode?.node })),
      laser: { on: ready && state.laser?.on === true },
      spots: result?.valid === true ? { measured: mmToM(result.spot_base_mm), reference: mmToM(result.ref_spot_base_mm), deviation_mm: result.dev_norm_mm ?? null } : {} });
  }
  const reason = reply => /[\u3400-\u9fff]/.test(reply?.msg || "") ? reply.msg : ({
    offline: "主机离线，请等待连接恢复", network: "主机连接失败，请稍后重试", busy: "主机正忙，请先结束当前操作",
    estop: "请先解除急停", no_demo: "请先完成示范", ttl: "激光有效时长无效", unsupported: "主机暂不支持此操作",
  }[reply?.code] || "指令失败，请检查主机状态");
  async function send(cmd, args = {}) {
    if (["laser_on", "laser_off", "laser_renew"].includes(cmd)) {
      const want = cmd !== "laser_off";
      if (!state.laserCommand || state.laserCommand.want !== want) {
        state = reduce(state, { type: "panel_laser", want, t: Date.now(), seq: ++commandSeq });
      }
    }
    schedule();
    let reply;
    try { reply = await source.send(cmd, args); }
    catch { reply = { ok: false, code: "network" }; }
    if (!reply?.ok) { const text = reason(reply); controls?.notify(text); event(text, "bad"); }
    schedule(); return reply;
  }
  function newGuard() {
    laserGuard = createLaserGuard({ send });
    if (state.hello) laserGuard.onMessage(state.hello);
    laserGuard.onMessage({ type: "link", online: online(state) });
    if (state.joint) laserGuard.onMessage(state.joint);
    suspended = false;
  }
  function shutdown(reason) { suspended = true; laserGuard.shutdown(reason); schedule(); }
  function receive(message) {
    const previous = state;
    state = reduce(state, message, Date.now());
    if (message.type === "hello" && state.hello === message) laserGuard.onMessage(message);
    if (message.type === "joint_state" && state.joint === message) {
      if (state.mode === "practice") {
        if (pass !== message.pass || previous.mode !== "practice") { pass = message.pass; samples = []; }
        samples.push({ t: message.t, q: message.q, valid: message.valid });
      }
      if (previous.mode !== state.mode) {
        const text = { demo: "示范开始", practice: "练习开始", estop: "已急停", fault: "机械臂故障" }[state.mode]
          || (previous.mode === "demo" ? "示范结束" : previous.mode === "practice" ? "练习停止" : previous.mode === "estop" ? "已解除急停" : "机械臂空闲");
        event(text, ["estop", "fault"].includes(state.mode) ? "bad" : ["demo", "practice"].includes(state.mode) ? "busy" : "ok");
        if (state.mode === "demo") { state = { ...state, passes: [], demo: null }; samples = []; pass = null; }
        if (state.mode === "practice" && previous.mode !== "practice") state = { ...state, passes: [] };
      }
    }
    if (online(previous) !== online(state)) {
      event(online(state) ? "连接恢复" : "连接断开", online(state) ? "ok" : "bad");
      if (!online(state)) samples = [...samples, { t: state.t, q: null }];
      laserGuard.onMessage({ type: "link", online: online(state) });
    }
    // 只让已归并的最新消息驱动守护器；乱序遥测不重新开灯。
    if ((message.type === "joint_state" && state.joint === message) || message.type === "node_result") laserGuard.onMessage(message);
    schedule();
  }
  async function action(event) {
    const name = event.detail.action, settings = buttonStates(viewState())[name];
    if (!settings || settings.disabled) return;
    ui.pending = true; schedule();
    try {
      if (name === "laser") {
        const on = !(state.laser?.on || laserGuard.state().want);
        if (on && suspended) newGuard();
        laserGuard.manual(on);
      } else {
        const running = state.mode === name;
        if (!running && suspended) newGuard();
        await send(name === "demo" ? running ? "demo_stop" : "demo_start" : running ? "practice_stop" : "practice_start");
      }
    } finally { ui.pending = false; schedule(); }
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    if (laserGuard) laserGuard.shutdown("dispose");
    unsubscribe?.(); source?.stop(); clearInterval(timer); cancelAnimationFrame(raf);
    for (const remove of listeners.reverse()) remove();
    for (const view of views.reverse()) view.dispose?.();
    delete document.documentElement.dataset.claim;
    delete document.documentElement.dataset.trainer;
  }
  try {
    source = trainerSourceFromParams(params);
    if (params.has("backend")) ui.hostname = new URL(params.get("backend")).hostname;
    // 区域根节点保持原位；原有矮屏页签仍可移动同一个 feed 节点。
    views.push(mountKpis(document.querySelector(".kpis")));
    views.push(mountJoints(document.querySelector(".jointcard")));
    views.push(mountFeed(document.getElementById("feed")));
    views.push(mountChart(document.getElementById("errchart").closest(".card")));
    views.push(mountCorrections(document.getElementById("diag").closest(".card")));
    views.push(mountCamera(document.getElementById("cam")));
    controls = mountControls(document); views.push(controls);
    laserGuard = createLaserGuard({ send });
    listen(document, "trainer:command", action);
    listen(window, "pagehide", () => shutdown("pagehide"));
    listen(document, "visibilitychange", () => { ui.active = home() && !document.hidden; if (document.hidden) shutdown("visibility_hidden"); schedule(); });
    listen(window, "hashchange", () => { ui.active = home() && !document.hidden; if (!home()) shutdown("leave_home"); schedule(); });
    listen(document.getElementById("estop"), "click", () => { ui.panelEstop = true; send("estop"); shutdown("estop_click"); }, true);
    listen(document, "rearm:state", e => {
      const value = e.detail?.state?.estop;
      if (typeof value !== "boolean") return;
      if (panelEstop && !value) send("reset_estop");
      panelEstop = value; ui.panelEstop = value; schedule();
    });
    listen(document, "rearm:theme", schedule); listen(window, "resize", schedule);
    unsubscribe = source.subscribe(receive);
    source.start();
    if (!ui.active) shutdown("inactive_page");
    // 定期刷新画面，绘制仍合并进 RAF；告警依据实际收到的激光状态。
    timer = setInterval(schedule, 250); schedule();
    document.dispatchEvent(new CustomEvent("rearm:modules-ready"));
    return { dispose, state: viewState, source };
  } catch (error) { dispose(); throw error; }
}
