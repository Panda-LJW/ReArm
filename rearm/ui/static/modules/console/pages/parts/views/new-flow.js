import { frameView } from "../../../shell/view.js";
import { setUnavailable } from "../../../shell/tooltip.js";
import { trainReason } from "../../../state/selectors.js";
import { element } from "../../../widgets/dom.js";
import { button } from "./format.js";
import { mount as identify } from "./identify-step.js";
import { mount as trainingRecord } from "./training-record.js";

export function mount(root, ctx) {
  const doc = root.ownerDocument, sidebar = element(doc, "ol", "library-flow-steps");
  const content = element(doc, "div", "library-flow-content c-card-body"); root.dataset.newFlow = "";
  root.classList.add("library-flow");
  const steps = [ctx.target === "part" ? "识别零件" : "编排配方", "训练", "入库"].map((text, i) => {
    const item = element(doc, "li", "", `${i + 1} ${text}`); item.dataset.step = String(i + 1); sidebar.append(item); return item;
  });
  root.append(sidebar, content);
  let state = ctx.store.getState(), step = 0, draft = ctx.existing ? { id: ctx.existing.id } : null;
  let child, start, message, pending = false, waiting = false, trainId = null, disposed = false, resetAtStart;
  let previousTrains = new Set();
  function show(nextStep) {
    child?.dispose(); child = null; content.replaceChildren(); step = nextStep;
    steps.forEach((el, i) => { el.dataset.progress = i + 1 < step ? "done" : i + 1 === step ? "current" : "pending";
      if (i + 1 === step) el.setAttribute("aria-current", "step"); else el.removeAttribute("aria-current"); });
    if (step === 1) child = identify(content, { ...ctx, confirm(value) { draft = value; show(2); } });
    if (step === 2) {
      content.append(element(doc, "h2", "", ctx.existing?.name || draft.name));
      start = button(doc, "开始训练", begin, true); message = element(doc, "p", "library-message");
      message.setAttribute("role", "status"); const record = element(doc, "div");
      content.append(start, message, record); child = trainingRecord(record); sync();
    }
    if (step === 3) {
      const result = state.trains.find(r => r.train_id === trainId);
      const item = state[ctx.target === "part" ? "partDocs" : "recipeDocs"][result.doc_id];
      content.append(element(doc, "h2", "", "训练完成 · 已收录"),
        element(doc, "p", "", `${item?.name || ctx.existing?.name || draft.name} · v${item?.version ?? "—"}`),
        button(doc, "查看文档", () => ctx.openDoc(ctx.target, result.doc_id)));
      const record = element(doc, "div"); content.append(record); child = trainingRecord(record);
      child.render(item?.training || { ...result, threshold_mm: state.hello?.threshold_mm });
    }
  }
  function sync() {
    state = ctx.store.getState();
    if (step === 2) setUnavailable(start, trainReason(state) || (pending || waiting ? "请求已发送，请等待训练进度" : ""));
  }
  async function begin() {
    sync(); if (trainReason(state) || pending || waiting) return;
    pending = true; waiting = true; trainId = null; resetAtStart = state.reset;
    previousTrains = new Set(state.trains.map(r => r.train_id)); message.textContent = ""; sync();
    try {
      const reply = await ctx.send("train_start", { target: ctx.target, draft });
      if (!reply?.ok) throw new Error(reply?.msg || "开始训练失败");
    } catch (error) {
      if (!disposed) { waiting = false; message.textContent = error.message; }
    } finally { pending = false; if (!disposed) sync(); }
  }
  show(ctx.existing ? 2 : 1);
  return frameView(next => {
    state = next;
    if (step === 1) child.render(next);
    if (step !== 2) return;
    if (waiting && !trainId && next.training?.target === ctx.target) trainId = next.training.train_id;
    if (waiting && !trainId) trainId = next.trains.find(r => r.target === ctx.target && !previousTrains.has(r.train_id))?.train_id;
    const done = trainId && next.trains.find(r => r.train_id === trainId);
    if (done) { waiting = false; show(3); return; }
    if (waiting && (next.phase === "estop" || !next.link.online || next.reset !== resetAtStart)) {
      waiting = false; trainId = null; message.textContent = "训练已中断，未收录。";
    }
    if (waiting && trainId && next.training?.train_id === trainId) {
      child.render({ rounds: next.training.rounds, threshold_mm: next.hello?.threshold_mm });
      message.textContent = "训练中，到时自动结束并收录。";
    } else if (!waiting) child.render({ rounds: [], threshold_mm: next.hello?.threshold_mm });
    sync();
  }, () => { disposed = true; child?.dispose(); root.replaceChildren(); }, doc.defaultView);
}
