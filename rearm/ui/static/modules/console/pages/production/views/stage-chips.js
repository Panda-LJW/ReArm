import { frameView } from "../../../shell/view.js";
import { online, statusWord } from "../../../state/selectors.js";
import { element } from "../../../widgets/dom.js";
import { productionSteps } from "./steps.js";

// 四角信息只读取已有快照和本页配方选择，不接管孪生或生产状态。
export function mount(root, ctx) {
  const doc = root.ownerDocument;
  const chips = ["tl", "tr", "bl", "br"].map(position => {
    const chip = element(doc, "div", `production-chip c-chip ${position}`);
    const text = element(doc, "span", "production-chip-text");
    chip.append(text); root.append(chip); return { chip, text };
  });
  const hint = element(doc, "p", "production-view-hint", "拖动旋转，滚轮缩放，双击复位");
  root.append(hint);
  return frameView(state => {
    const connected = online(state), busy = connected && state.phase !== "estop" && (Boolean(state.training) || state.phase !== "idle");
    const id = state.run && state.phase !== "idle" ? state.run.recipe_id : ctx.selection.id;
    const recipe = state.recipeDocs[id] || state.library.recipes.find(item => item.id === id);
    const current = productionSteps(state, recipe).find(row => row.current);
    const values = [statusWord(state), recipe?.name || "—",
      state.hello?.sim === true ? "模拟" : state.hello?.sim === false ? "实时" : "—",
      current?.label || (state.phase === "estop" ? statusWord(state) : "等待开始")];
    chips.forEach(({ chip, text }, i) => {
      if (text.textContent !== values[i]) {
        text.textContent = values[i];
        text.dataset.flash = text.dataset.flash === "a" ? "b" : "a";
      }
      if (i === 0) {
        chip.classList.toggle("bad", state.phase === "estop");
        chip.classList.toggle("busy", busy);
        chip.classList.toggle("ok", connected && !busy && state.phase === "idle");
      }
    });
    root.dataset.busy = String(busy);
  }, () => { for (const { chip } of chips) chip.remove(); hint.remove(); }, doc.defaultView);
}
