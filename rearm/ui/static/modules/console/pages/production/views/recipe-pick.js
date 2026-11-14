import { frameView } from "../../../shell/view.js";
import { setUnavailable } from "../../../shell/tooltip.js";
import { startReason } from "../../../state/selectors.js";
import { element } from "../../../widgets/dom.js";

export function mount(root, ctx) {
  const doc = root.ownerDocument, label = element(doc, "label", "production-field");
  const title = element(doc, "span", "production-recipe-title c-card-head", "配方");
  const controls = element(doc, "div", "production-recipe-controls c-card-body");
  const select = element(doc, "select"); select.setAttribute("aria-label", "配方");
  const start = element(doc, "button", "console-button console-primary c-btn primary", "开始");
  start.type = "button"; start.dataset.action = "start";
  const message = element(doc, "p", "production-message"); message.setAttribute("role", "status"); message.hidden = true;
  label.append(title, select); controls.append(label, start); root.append(controls, message);
  let state, recipes, pending = false, disposed = false, check = null, requestId = "";
  const reason = () => !state ? "连接就绪后可操作" : startReason(state) ||
    (!ctx.selection.id ? "请先选择配方" : pending ? "请求已发送，请稍候" : "");
  function sync() {
    state = ctx.store?.getState() || state;
    const why = reason(); setUnavailable(start, why);
    select.setAttribute("aria-disabled", String(Boolean(why)));
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
    if (reason() && event.key !== "Tab") event.preventDefault();
  }
  function open() {
    sync(); if (reason() || !ctx.dialog) return;
    message.hidden = true;
    const content = element(doc, "label", "", "确认工作区附近无人");
    check = element(doc, "input"); check.type = "checkbox"; check.dataset.confirmCheck = "";
    content.prepend(check); check.addEventListener("change", sync);
    ctx.dialog.open({ title: "开始生产", content, confirmEnabled: false, reason: "请先确认工作区附近无人",
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
    disposed = true; check = null;
    select.removeEventListener("change", change); select.removeEventListener("mousedown", guard); select.removeEventListener("keydown", guard);
    start.removeEventListener("click", open); root.replaceChildren();
  }, doc.defaultView);
}
