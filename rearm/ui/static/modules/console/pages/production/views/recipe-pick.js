import { frameView } from "../../../shell/view.js";
import { setUnavailable } from "../../../shell/tooltip.js";
import { startReason, demoData } from "../../../state/selectors.js";
import { element } from "../../../widgets/dom.js";
import { enhanceSelect } from "../../../widgets/select.js";

export function mount(root, ctx) {
  const doc = root.ownerDocument, label = element(doc, "label", "production-field");
  const title = element(doc, "span", "production-recipe-title c-card-head", "配方");
  const demo = element(doc, "span", "c-aside", "演示数据"); demo.hidden = true; title.append(demo);
  const controls = element(doc, "div", "production-recipe-controls c-card-body");
  const select = element(doc, "select"); select.setAttribute("aria-label", "配方");
  const start = element(doc, "button", "console-button console-primary c-btn primary", "开始");
  start.type = "button"; start.dataset.action = "start";
  const message = element(doc, "p", "production-message"); message.setAttribute("role", "status"); message.hidden = true;
  label.append(title, select); controls.append(label, start); root.append(controls, message);
  let state, recipes, pending = false, disposed = false, check = null, requestId = "";
  const recipe = id => ({ ...state?.library.recipes.find(item => item.id === id), ...state?.recipeDocs?.[id] });
  function metadata(id) {
    const item = recipe(id), values = [];
    if (Array.isArray(item.part_ids)) values.push(`${item.part_ids.length} 个零件`);
    if (Array.isArray(item.steps)) values.push(`${item.steps.length} 步`);
    return values.join(" · ");
  }
  const picker = enhanceSelect(select, { meta: option => metadata(option.value) });
  const reason = () => !state ? "连接就绪后可操作" : startReason(state) ||
    (!ctx.selection.id ? "请先选择配方" : pending ? "请求已发送，请稍候" : "");
  function sync() {
    state = ctx.store?.getState() || state;
    const why = reason(); setUnavailable(start, why);
    setUnavailable(select, why); picker.render();
    if (check?.isConnected) ctx.dialog?.setConfirmEnabled(check.checked && !why, why || "请先确认工作区附近无人");
  }
  async function readRecipe() {
    const id = ctx.selection.id;
    if (!id || requestId === id || !ctx.send) return;
    requestId = id;
    try {
      const reply = await ctx.send("recipe_get", { id });
      if (!reply?.ok) throw new Error(reply?.msg || "配方读取失败");
    } catch (error) {
      if (!disposed) { message.textContent = error.message; message.hidden = false; }
    }
  }
  function change() {
    if (reason()) { select.value = ctx.selection.id; return; }
    ctx.selection.id = select.value; message.hidden = true; void readRecipe(); sync();
  }
  function guard(event) {
    sync();
    if (reason() && event.key !== "Tab") event.preventDefault();
  }
  function open() {
    sync(); if (reason() || !ctx.dialog) return;
    message.hidden = true;
    const content = element(doc, "div", "c-production-confirm"), summary = element(doc, "div", "c-confirm-summary");
    summary.append(element(doc, "div", "c-confirm-name", recipe(ctx.selection.id).name || select.selectedOptions[0]?.label || ""));
    const info = metadata(ctx.selection.id);
    if (info) summary.append(element(doc, "p", "c-confirm-meta", info));
    const safety = element(doc, "label", "c-confirm-check");
    check = element(doc, "input"); check.type = "checkbox"; check.dataset.confirmCheck = "";
    check.autofocus = true; check.className = "c-visually-hidden";
    const box = element(doc, "span", "c-confirm-box"), mark = doc.createElementNS("http://www.w3.org/2000/svg", "svg");
    mark.setAttribute("viewBox", "0 0 16 16"); mark.setAttribute("aria-hidden", "true");
    const path = doc.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M3 8l3 3 7-7"); path.setAttribute("pathLength", "1"); mark.append(path); box.append(mark);
    box.setAttribute("aria-hidden", "true");
    safety.append(check, box, element(doc, "span", "", "确认工作区附近无人")); content.append(summary, safety);
    check.addEventListener("change", sync);
    check.addEventListener("keydown", event => {
      if (event.key !== "Enter" || event.repeat || event.isComposing || event.altKey || event.ctrlKey || event.metaKey) return;
      event.preventDefault(); sync();
      if (check.checked && !reason()) content.closest("dialog")?.querySelector('[data-action="confirm"]')?.click();
    });
    ctx.dialog.open({ title: "开始生产", content, safety: true, confirmText: "开始生产", trigger: start,
      confirmEnabled: false, reason: "请先确认工作区附近无人",
      onConfirm() {
        sync(); if (!check.checked || reason()) return false;
        pending = true; sync();
        Promise.resolve().then(() => ctx.send("run_start", { recipe_id: ctx.selection.id })).then(reply => {
          if (!reply?.ok) throw new Error(reply?.msg || "开始生产失败");
        }).catch(error => {
          if (!disposed) { message.textContent = error.message; message.hidden = false; }
        }).finally(() => { pending = false; if (!disposed) sync(); });
      } });
  }
  select.addEventListener("change", change); select.addEventListener("mousedown", guard); select.addEventListener("keydown", guard);
  start.addEventListener("click", open); setUnavailable(start, "连接就绪后可操作");
  return frameView(next => {
    state = next;
    demo.hidden = !demoData(state);
    if (recipes !== next.library.recipes) {
      recipes = next.library.recipes;
      select.replaceChildren(...recipes.map(recipe => {
        const option = element(doc, "option", "", recipe.name); option.value = recipe.id; option.dataset.recipe = ""; return option;
      }));
      if (!recipes.some(r => r.id === ctx.selection.id)) ctx.selection.id = recipes[0]?.id || "";
      select.value = ctx.selection.id; void readRecipe();
    }
    sync();
  }, () => {
    disposed = true; check = null; picker.dispose();
    select.removeEventListener("change", change); select.removeEventListener("mousedown", guard); select.removeEventListener("keydown", guard);
    start.removeEventListener("click", open); root.replaceChildren();
  }, doc.defaultView);
}
