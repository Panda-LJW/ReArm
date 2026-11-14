import { frameView } from "../../shell/view.js";
import { setUnavailable } from "../../shell/tooltip.js";
import { initialState } from "../../state/store.js";
import { trainReason } from "../../state/selectors.js";
import { element } from "../../widgets/dom.js";
import { button } from "./views/format.js";
import { mount as partList } from "./views/part-list.js";
import { mount as recipeList } from "./views/recipe-list.js";
import { mount as partDoc } from "./views/part-doc.js";
import { mount as recipeDoc } from "./views/recipe-doc.js";
import { mount as newFlow } from "./views/new-flow.js";

export function mount(root, ctx = {}) {
  const doc = root.ownerDocument, css = element(doc, "link");
  css.rel = "stylesheet"; css.href = new URL("./parts.css", import.meta.url).href; doc.head.append(css);
  let state = ctx.store?.getState() || initialState(), tab = "parts", mode = "list", detailView, flowView, flowTarget;
  const header = element(doc, "header", "library-header"), tabs = element(doc, "div", "library-tabs");
  tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "零件库分类");
  const listSlot = element(doc, "div", "library-scroll"), docSlot = element(doc, "article", "library-scroll");
  const flowSlot = element(doc, "div", "library-scroll"), panels = element(doc, "div", "library-panels");
  const local = { ...ctx, store: ctx.store || { getState: () => state }, openDoc, openFlow };
  const partRoot = element(doc, "section"), recipeRoot = element(doc, "section");
  partRoot.id = "library-parts"; recipeRoot.id = "library-recipes";
  partRoot.setAttribute("role", "tabpanel"); recipeRoot.setAttribute("role", "tabpanel");
  const lists = [partList(partRoot, local), recipeList(recipeRoot, local)]; listSlot.append(partRoot, recipeRoot);
  const tabButtons = ["parts", "recipes"].map((id, i) => {
    const control = button(doc, i ? "配方" : "零件", () => { tab = id; mode = "list"; sync(); });
    control.dataset.tab = id; control.setAttribute("role", "tab"); control.setAttribute("aria-controls", `library-${id}`);
    control.id = `library-tab-${id}`; [partRoot, recipeRoot][i].setAttribute("aria-labelledby", control.id);
    control.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault(); const target = event.key === "Home" ? 0 : event.key === "End" ? 1 : 1 - i;
      tabButtons[target].click(); tabButtons[target].focus();
    }); tabs.append(control); return control;
  });
  const back = button(doc, "返回列表", () => { mode = "list"; sync(); });
  const resume = button(doc, "查看新增流程", () => { mode = "flow"; sync(); });
  const add = button(doc, "新增零件", () => {
    state = local.store.getState(); if (!trainReason(state)) openFlow(tab === "parts" ? "part" : "recipe");
  }, true);
  header.append(element(doc, "h1", "", "零件库"), tabs, back, resume, add);
  panels.append(listSlot, docSlot, flowSlot); root.replaceChildren(header, panels);
  function sync() {
    partRoot.hidden = tab !== "parts"; recipeRoot.hidden = tab !== "recipes";
    tabButtons.forEach(el => { el.setAttribute("aria-selected", String(el.dataset.tab === tab)); el.tabIndex = el.dataset.tab === tab ? 0 : -1; });
    listSlot.hidden = mode !== "list"; docSlot.hidden = mode !== "doc"; flowSlot.hidden = mode !== "flow";
    back.hidden = mode === "list"; add.hidden = mode !== "list";
    add.textContent = tab === "parts" ? "新增零件" : "新增配方";
    resume.hidden = !flowView || mode === "flow" || flowTarget !== (tab === "parts" ? "part" : "recipe");
    setUnavailable(add, trainReason(state));
  }
  function openDoc(target, id) {
    detailView?.dispose(); docSlot.replaceChildren(); tab = target === "part" ? "parts" : "recipes"; mode = "doc";
    detailView = (target === "part" ? partDoc : recipeDoc)(docSlot, { ...local, id });
    detailView.render(local.store.getState()); sync();
  }
  function openFlow(target, existing) {
    flowView?.dispose(); flowSlot.replaceChildren(); flowTarget = target; mode = "flow";
    flowView = newFlow(flowSlot, { ...local, target, existing }); flowView.render(local.store.getState()); sync();
  }
  sync();
  return frameView(next => {
    state = next || initialState(); lists.forEach(view => view.render(state));
    detailView?.render(state); flowView?.render(state); sync();
  }, () => { lists.forEach(view => view.dispose()); detailView?.dispose(); flowView?.dispose(); css.remove(); root.replaceChildren(); }, doc.defaultView);
}
