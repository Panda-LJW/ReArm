import { frameView } from "../../../shell/view.js";
import { setUnavailable } from "../../../shell/tooltip.js";
import { trainReason } from "../../../state/selectors.js";
import { element } from "../../../widgets/dom.js";
import { button } from "./format.js";
import { mount as identify } from "./identify-step.js";
import { mount as trainingRecord } from "./training-record.js";
import { contentSwap } from "./transition.js";

export function mount(root, ctx) {
  const doc = root.ownerDocument, sidebar = element(doc, "ol", "library-flow-steps");
  const content = element(doc, "div", "library-flow-content c-card-body"); root.dataset.newFlow = "";
  root.classList.add("library-flow");
  const steps = [ctx.target === "part" ? "识别零件" : "编排配方", "训练", "入库"].map((text, i) => {
    const item = element(doc, "li", "", `${i + 1} ${text}`); item.dataset.step = String(i + 1);
    if (i < 2) {
      const track = element(doc, "span", "library-step-connector"), fill = element(doc, "span");
      track.setAttribute("aria-hidden", "true"); track.append(fill); item.append(track);
    }
    sidebar.append(item); return item;
  });
  const footer = element(doc, "footer", "library-flow-actions");
  const previous = button(doc, "上一步", () => { sync(); if (step === 2 && !ctx.existing && !navigationReason()) show(1); });
  const next = button(doc, "下一步", () => {
    sync(); if (changing || navigationReason()) return;
    if (step === 1) identifyView?.next();
    else if (step === 2) void begin();
    else if (step === 3) openResult?.click();
  }, true);
  const cancel = button(doc, "取消", () => { sync(); if (!navigationReason()) ctx.cancelFlow?.(); });
  footer.append(previous, next, cancel); root.append(sidebar, content, footer);
  const transition = contentSwap(content), identifyRoot = element(doc, "div", "library-identify-step");
  let state = ctx.store.getState(), step = 0, draft = ctx.existing ? { id: ctx.existing.id } : null;
  let child, identifyView, start, openResult, message, changing = false;
  let pending = false, waiting = false, trainId = null, disposed = false, resetAtStart;
  let previousTrains = new Set();
  function navigationReason() {
    return changing ? "正在切换步骤" : pending || waiting || identifyView?.pending() ? "请等待当前操作完成" : "";
  }
  function show(nextStep) {
    changing = true; sync();
    // 完成记录可能在淡出期间被重置清空，沿用进入完成页时的快照。
    const result = nextStep === 3 ? state.trains.find(r => r.train_id === trainId) : null;
    const completed = result && state[ctx.target === "part" ? "partDocs" : "recipeDocs"][result.doc_id];
    const draw = () => {
      const restoreFocus = content.contains(doc.activeElement);
      if (child !== identifyView) child?.dispose();
      child = null; start = null; openResult = null; content.replaceChildren(); step = nextStep;
      steps.forEach((el, i) => { el.dataset.progress = i + 1 < step ? "done" : i + 1 === step ? "current" : "pending";
        if (i + 1 === step) el.setAttribute("aria-current", "step"); else el.removeAttribute("aria-current"); });
      if (step === 1) {
        content.append(identifyRoot);
        identifyView ||= identify(identifyRoot, { ...ctx, changed: sync, confirm(value) { draft = value; show(2); } });
        child = identifyView;
      }
      if (step === 2) {
        content.append(element(doc, "h2", "", ctx.existing?.name || draft.name),
          element(doc, "p", "library-muted", "确认零件与工装已放好，保持工作区无遮挡。开始训练后查看逐轮偏差，完成后自动入库。"));
        start = button(doc, "开始训练", begin, true); message = element(doc, "p", "library-message");
        message.setAttribute("role", "status"); const record = element(doc, "div");
        content.append(start, message, record); child = trainingRecord(record);
      }
      if (step === 3) {
        openResult = button(doc, "查看文档", () => ctx.openDoc(ctx.target, result.doc_id));
        content.append(element(doc, "h2", "", "训练完成 · 已收录"),
          element(doc, "p", "", `${completed?.name || ctx.existing?.name || draft.name} · v${completed?.version ?? "—"}`), openResult);
        const record = element(doc, "div"); content.append(record); child = trainingRecord(record);
        child.render(completed?.training || { ...result, threshold_mm: state.hello?.threshold_mm });
      }
      changing = false; renderState(ctx.store.getState()); sync();
      if (restoreFocus) (step === 1 ? identifyRoot.querySelector("input") : start || openResult)?.focus({ preventScroll: true });
    };
    if (content.childElementCount) void transition.render(draw); else draw();
  }
  function sync() {
    state = ctx.store.getState();
    const busy = navigationReason();
    if (step === 2 && start) setUnavailable(start, trainReason(state) || (pending || waiting ? "请求已发送，请等待训练进度" : ""));
    setUnavailable(previous, busy || (step !== 2 || ctx.existing ? "当前步骤不可返回" : ""));
    setUnavailable(next, busy || (step === 1 ? identifyView?.reason() || "" : step === 2 ? trainReason(state) : ""));
    setUnavailable(cancel, busy);
  }
  async function begin() {
    sync(); if (changing || trainReason(state) || pending || waiting) return;
    pending = true; waiting = true; trainId = null; resetAtStart = state.reset;
    previousTrains = new Set(state.trains.map(r => r.train_id)); message.textContent = ""; sync();
    try {
      const reply = await ctx.send("train_start", { target: ctx.target, draft });
      if (!reply?.ok) throw new Error(reply?.msg || "开始训练失败");
    } catch (error) {
      if (!disposed) { waiting = false; message.textContent = error.message; }
    } finally { pending = false; if (!disposed) sync(); }
  }
  function renderState(nextState) {
    state = nextState;
    if (changing) return;
    if (step === 1) child.render(state);
    if (step !== 2) return;
    if (waiting && !trainId && state.training?.target === ctx.target) trainId = state.training.train_id;
    if (waiting && !trainId) trainId = state.trains.find(r => r.target === ctx.target && !previousTrains.has(r.train_id))?.train_id;
    const done = trainId && state.trains.find(r => r.train_id === trainId);
    if (done) { waiting = false; show(3); return; }
    if (waiting && (state.phase === "estop" || !state.link.online || state.reset !== resetAtStart)) {
      waiting = false; trainId = null; message.textContent = "训练已中断，未收录。";
    }
    if (waiting && trainId && state.training?.train_id === trainId) {
      child.render({ rounds: state.training.rounds, threshold_mm: state.hello?.threshold_mm });
      message.textContent = "训练中，到时自动结束并收录。";
    } else if (!waiting) child.render({ rounds: [], threshold_mm: state.hello?.threshold_mm });
    sync();
  }
  show(ctx.existing ? 2 : 1);
  return frameView(renderState, () => {
    disposed = true; transition.cancel();
    if (child !== identifyView) child?.dispose();
    identifyView?.dispose(); root.replaceChildren();
  }, doc.defaultView);
}
