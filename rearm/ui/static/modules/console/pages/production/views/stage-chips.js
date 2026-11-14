import { frameView } from "../../../shell/view.js";
import { online, statusWord, productionRecipe, productionBusy } from "../../../state/selectors.js";
import { element } from "../../../widgets/dom.js";
import { productionSteps } from "./steps.js";
import { swap } from "../../../widgets/motion.js";

// 四角信息只读取已有快照和本页配方选择，不接管孪生或生产状态。
export function mount(root, ctx) {
  const doc = root.ownerDocument;
  const chips = ["tl", "tr", "bl", "br"].map(position => {
    const chip = element(doc, "div", `production-chip c-chip ${position}`);
    const text = element(doc, "span", "production-chip-text");
    chip.append(text); root.append(chip); return { chip, text, value: undefined };
  });
  const hint = element(doc, "p", "production-view-hint", "拖动旋转，滚轮缩放，双击复位");
  root.append(hint);
  const win = doc.defaultView;
  let previousRuns, completedId = null, timer = null, latest, disposed = false;
  function clearCompletion() {
    if (timer !== null) win.clearTimeout(timer);
    timer = null; completedId = null;
  }
  function display(item, value, immediate = false) {
    if (item.value === value) return;
    const first = item.value === undefined; item.value = value;
    const write = () => {
      if (disposed || item.value !== value) return;
      item.text.textContent = value;
      item.text.dataset.flash = item.text.dataset.flash === "a" ? "b" : "a";
    };
    if (first || immediate) {
      item.text.classList.remove("c-swap-out", "c-swap-in"); write();
    } else void swap(item.text, write, win);
  }
  const view = frameView(state => {
    latest = state;
    const connected = online(state), busy = productionBusy(state);
    const recipe = productionRecipe(state, ctx.selection.id);
    const current = productionSteps(state, recipe).find(row => row.current);
    if (previousRuns !== state.runs) {
      const added = previousRuns && state.runs.findLast(run => !previousRuns.some(previous => previous.run_id === run.run_id));
      if (!state.runs.length) clearCompletion();
      if (added) {
        clearCompletion(); completedId = added.run_id;
        timer = win.setTimeout(() => { timer = null; completedId = null; if (!disposed) view.render(latest); }, 1800);
      }
      previousRuns = state.runs;
    }
    if (!connected || state.phase === "estop" || state.training ||
        (state.run?.run_id && completedId && state.run.run_id !== completedId)) clearCompletion();
    const values = [statusWord(state), recipe?.name || "—",
      state.hello?.sim === true ? "模拟" : state.hello?.sim === false ? "实时" : "—",
      completedId ? "完成 ✓" : current?.label || (state.phase === "estop" ? statusWord(state) : "等待开始")];
    chips.forEach((item, i) => {
      const { chip } = item;
      display(item, values[i], state.phase === "estop");
      if (i === 0) {
        chip.classList.toggle("bad", state.phase === "estop");
        chip.classList.toggle("busy", busy);
        chip.classList.toggle("ok", connected && !busy && state.phase === "idle");
      }
    });
    root.dataset.busy = String(busy);
  }, () => {
    disposed = true; clearCompletion();
    for (const { chip } of chips) chip.remove(); hint.remove();
  }, win);
  return view;
}
