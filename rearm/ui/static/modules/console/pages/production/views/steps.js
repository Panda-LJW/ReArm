import { frameView } from "../../../shell/view.js";
import { mount as mountStepper } from "../../../widgets/stepper.js";
import { element } from "../../../widgets/dom.js";
import { productionRecipe } from "../../../state/selectors.js";
import { reducedMotion } from "../../../widgets/motion.js";

const CHECKS = [["comm", "通信"], ...Array.from({ length: 6 }, (_, i) => [`j${i + 1}`, `J${i + 1}`]),
  ["gripper", "夹爪"], ["depth_camera", "深度相机"]];

export function productionSteps(state, recipe) {
  const parts = new Map(state.library.parts.map(part => [part.id, part.name]));
  const rows = [{ phase: "selfcheck", label: "自检" }, { phase: "to_observe", label: "到观察位" },
    { phase: "recognize", label: "识别" }, ...(recipe?.steps || []).flatMap((step, i) =>
      ["pick", "place"].map(phase => ({ phase, index: i + 1,
        label: `${phase === "pick" ? "抓取" : "放置"} · ${parts.get(step.part_id) || "零件"}` }))),
    { phase: "inspect", label: "检查" }, { phase: "done", label: "完成" }, { phase: "to_fold", label: "收回" }];
  const index = rows.findIndex(row => row.phase === state.phase && (!row.index || row.index === state.run?.step_index));
  const finished = state.phase === "idle" && state.runs.some(run => run.run_id === state.run?.run_id);
  return rows.map((row, i) => ({ label: row.label, current: i === index, done: finished || (index >= 0 && i < index) }));
}

export function mount(root, ctx) {
  const doc = root.ownerDocument, title = element(doc, "h2", "c-card-head", "生产步骤");
  const count = element(doc, "span", "c-aside production-steps-count");
  const bar = element(doc, "div", "c-progress"), fill = element(doc, "span");
  bar.setAttribute("role", "progressbar"); bar.setAttribute("aria-label", "生产步骤"); bar.setAttribute("aria-valuemin", "0");
  bar.append(fill); title.append(count);
  const body = element(doc, "div", "production-steps-body c-card-body");
  const checks = element(doc, "div", "production-checks"), progress = element(doc, "div");
  const items = CHECKS.map(([id, label]) => {
    const el = element(doc, "span"); el.dataset.checkItem = id; checks.append(el); return { id, label, el };
  });
  body.append(checks, progress); root.append(title, bar, body); const stepper = mountStepper(progress);
  let active = "";
  return frameView(state => {
    checks.hidden = state.phase !== "selfcheck"; progress.hidden = !checks.hidden;
    for (const { id, label, el } of items) {
      const value = state.selfcheck[id]?.ok;
      el.dataset.ok = String(value === true);
      el.textContent = `${value === true ? "✓" : value === false ? "×" : "·"} ${label}`;
    }
    const recipe = productionRecipe(state, ctx.selection.id), rows = productionSteps(state, recipe);
    const index = rows.findIndex(row => row.current), completed = rows.filter(row => row.done).length;
    const value = index < 0 ? completed : index + 1;
    count.textContent = `${value} / ${rows.length}`;
    bar.setAttribute("aria-valuemax", String(rows.length)); bar.setAttribute("aria-valuenow", String(value));
    fill.style.width = `${value / rows.length * 100}%`;
    stepper.render(rows);
    const current = progress.querySelector('[aria-current="step"]');
    if (current && !current.querySelector(".production-step-dot")) {
      const dot = element(doc, "span", "production-step-dot c-pulse");
      dot.setAttribute("aria-hidden", "true"); current.append(dot);
    }
    const next = current && !progress.hidden && !root.closest("[hidden]") ? `${recipe?.id}:${state.run?.run_id}:${index}` : "";
    if (next && next !== active) current.scrollIntoView?.({ block: "nearest", behavior: reducedMotion(doc.defaultView) ? "auto" : "smooth" });
    active = next;
  }, () => { stepper.dispose(); root.replaceChildren(); }, doc.defaultView);
}
