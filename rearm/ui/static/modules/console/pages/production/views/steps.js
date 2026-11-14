import { frameView } from "../../../shell/view.js";
import { mount as mountStepper } from "../../../widgets/stepper.js";
import { element } from "../../../widgets/dom.js";

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
  const doc = root.ownerDocument, title = element(doc, "h2", "", "生产步骤");
  const checks = element(doc, "div", "production-checks"), progress = element(doc, "div");
  const items = CHECKS.map(([id, label]) => {
    const el = element(doc, "span"); el.dataset.checkItem = id; checks.append(el); return { id, label, el };
  });
  root.append(title, checks, progress); const stepper = mountStepper(progress);
  return frameView(state => {
    checks.hidden = state.phase !== "selfcheck"; progress.hidden = !checks.hidden;
    for (const { id, label, el } of items) {
      const value = state.selfcheck[id]?.ok;
      el.dataset.ok = String(value === true);
      el.textContent = `${value === true ? "✓" : value === false ? "×" : "·"} ${label}`;
    }
    const id = state.run && state.phase !== "idle" ? state.run.recipe_id : ctx.selection.id;
    stepper.render(productionSteps(state, state.recipeDocs[id]));
  }, () => { stepper.dispose(); root.replaceChildren(); }, doc.defaultView);
}
