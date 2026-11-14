import { initialState } from "../../state/store.js";
import { element } from "../../widgets/dom.js";
import { stagger } from "../../widgets/motion.js";
import { mount as recipePick } from "./views/recipe-pick.js";
import { mount as keyNumber } from "./views/key-number.js";
import { mount as steps } from "./views/steps.js";
import { mount as observe } from "./views/observe-view.js";
import { mount as stageChips } from "./views/stage-chips.js";
import { mount as lastPick } from "./views/last-pick.js";

export function mount(root, ctx = {}) {
  const doc = root.ownerDocument, css = element(doc, "link");
  css.rel = "stylesheet"; css.href = new URL("./production.css", import.meta.url).href; doc.head.append(css);
  const motion = element(doc, "link");
  motion.rel = "stylesheet"; motion.href = new URL("./production-motion.css", import.meta.url).href; doc.head.append(motion);
  const viewport = element(doc, "div", "production-viewport c-card c-viewport");
  const stage = element(doc, "div", "production-twin", "机械臂画面加载中…"); stage.dataset.twinStage = "";
  const side = element(doc, "aside", "production-side"); side.setAttribute("aria-label", "生产操作和结果");
  viewport.append(stage); root.replaceChildren(viewport, side);
  const local = { ...ctx, selection: { id: "" } };
  const views = [recipePick, keyNumber, steps, observe].map((mount, i) => {
    const section = element(doc, "section", `production-section production-section-${i} c-card${i === 1 ? " c-kpis" : ""}`);
    side.append(section); return mount(section, local);
  });
  views.push(stageChips(viewport, local));
  let pickView = null;
  stagger([viewport, side.children[1], side.children[0], side.children[2], side.children[3]]);
  // 容器只分发快照；叶子视图各自合并到同一帧，不能每层额外延迟一帧。
  return {
    render(state) {
      if (state?.device && !pickView) {
        const section = element(doc, "section", "production-section production-section-4 c-card");
        side.append(section); pickView = lastPick(section); views.push(pickView); stagger([section]);
      }
      for (const view of views) view.render(state || initialState());
    },
    dispose() { for (const view of views) view.dispose(); css.remove(); motion.remove(); root.replaceChildren(); },
  };
}
