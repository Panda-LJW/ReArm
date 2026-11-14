import { frameView } from "../../../shell/view.js";
import { setUnavailable } from "../../../shell/tooltip.js";
import { trainReason } from "../../../state/selectors.js";
import { element } from "../../../widgets/dom.js";
import { button, field, number } from "./format.js";
import { shape } from "./shape.js";
import { recipeFields } from "./recipe-fields.js";

export function mount(root, ctx) {
  const doc = root.ownerDocument, form = element(doc, "div", "library-identify");
  const preview = element(doc, "div", "library-candidate c-viewport"), message = element(doc, "p", "library-message");
  message.setAttribute("role", "status");
  let state = ctx.store.getState(), pending = false, candidate = null, baseline, disposed = false;
  let resetAtCapture = state.reset;
  const name = field(doc, "名称"), code = field(doc, "编号");
  const capture = button(doc, "拍照识别", takePhoto, true);
  const confirm = button(doc, ctx.target === "part" ? "确认零件" : "确认配方", () => {
    sync(); if (reason()) return;
    ctx.confirm({ ...(candidate || recipe?.draft()), name: name.input.value.trim(), code: code.input.value.trim() });
  }, true);
  form.append(name.label, code.label);
  let recipe;
  if (ctx.target === "recipe") {
    let n = state.library.recipes.length + 1;
    while (state.library.recipes.some(r => r.code === `R${String(n).padStart(3, "0")}`)) n++;
    code.input.value = `R${String(n).padStart(3, "0")}`;
    recipe = recipeFields(form, state, sync);
  }
  form.append(confirm); root.append(capture, preview, form, message);
  name.input.addEventListener("input", sync); code.input.addEventListener("input", sync);
  function reason() {
    return trainReason(state) || (pending ? "请等待识别结果" : "") ||
      (ctx.target === "part" && !candidate ? "请先拍照识别" : "") ||
      (!name.input.value.trim() || !code.input.value.trim() ? "请填写名称和编号" : "") ||
      (state.library[ctx.target === "part" ? "parts" : "recipes"].some(r => r.code === code.input.value.trim()) ? "编号已存在，请换一个编号" : "") || recipe?.reason() || "";
  }
  function sync() {
    state = ctx.store.getState();
    capture.hidden = ctx.target !== "part" || Boolean(candidate);
    form.hidden = ctx.target === "part" && !candidate;
    setUnavailable(capture, trainReason(state) || (pending ? "请等待识别结果" : ""));
    setUnavailable(confirm, reason());
  }
  async function takePhoto() {
    sync(); if (trainReason(state) || pending) return;
    pending = true; baseline = state.candidate; resetAtCapture = state.reset; message.textContent = "正在识别零件…"; sync();
    try {
      const reply = await ctx.send("part_capture");
      if (!reply?.ok) throw new Error(reply?.msg || "拍照识别失败");
    } catch (error) {
      if (!disposed) { pending = false; message.textContent = error.message; sync(); }
    }
  }
  sync();
  return frameView(next => {
    state = next;
    if (pending && (next.phase === "estop" || !next.link.online || next.reset !== resetAtCapture)) {
      pending = false; message.textContent = "识别已中断，请重新拍照。";
    }
    if (pending && next.candidate && next.candidate !== baseline) {
      pending = false; candidate = next.candidate;
      name.input.value = candidate.name; code.input.value = candidate.code;
      preview.replaceChildren(shape(doc, candidate), element(doc, "p", "c-chip br", `${candidate.size_mm.map(number).join(" × ")} mm`));
      message.textContent = "模型自己识别，请确认名称和编号。";
    }
    sync();
  }, () => { disposed = true; root.replaceChildren(); }, doc.defaultView);
}
