import { frameView } from "../../shell/view.js";
import { initialState } from "../../state/store.js";
import { element } from "../../widgets/dom.js";
import { mount as recipePick } from "./views/recipe-pick.js";
import { mount as keyNumber } from "./views/key-number.js";
import { mount as steps } from "./views/steps.js";
import { mount as observe } from "./views/observe-view.js";

export function mount(root, ctx = {}) {
  const doc = root.ownerDocument, css = element(doc, "link");
  css.rel = "stylesheet"; css.href = new URL("./production.css", import.meta.url).href; doc.head.append(css);
  const stage = element(doc, "div", "production-twin", "机械臂画面加载中…"); stage.dataset.twinStage = "";
  const side = element(doc, "aside", "production-side"); side.setAttribute("aria-label", "生产操作和结果");
  root.replaceChildren(stage, side);
  const local = { ...ctx, selection: { id: "" } };
  const views = [recipePick, keyNumber, steps, observe].map((mount, i) => {
    const section = element(doc, "section", `production-section production-section-${i}`);
    side.append(section); return mount(section, local);
  });
  return frameView(state => { for (const view of views) view.render(state || initialState()); },
    () => { for (const view of views) view.dispose(); css.remove(); root.replaceChildren(); }, doc.defaultView);
}
