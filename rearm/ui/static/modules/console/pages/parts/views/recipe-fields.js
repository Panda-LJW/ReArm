import { element } from "../../../widgets/dom.js";
import { setUnavailable } from "../../../shell/tooltip.js";
import { button, field } from "./format.js";
import { enhanceSelect } from "../../../widgets/select.js";

export function recipeFields(root, state, changed) {
  const doc = root.ownerDocument, fixture = field(doc, "工装", "select");
  const fixtures = state.workspace.props.filter(p => p.kind === "fixture");
  for (const row of fixtures) {
    const option = element(doc, "option", "", row.name); option.value = row.id; fixture.input.append(option);
  }
  const choices = element(doc, "fieldset", "library-choices"), order = element(doc, "ol", "library-order");
  choices.append(element(doc, "legend", "", "选择零件"));
  let selected = [];
  const post = state.workspace.props.find(p => p.kind === "post");
  function drawOrder() {
    order.replaceChildren(...selected.map((id, index) => {
      const name = state.library.parts.find(p => p.id === id)?.name || id, li = element(doc, "li");
      const move = delta => {
        const to = index + delta; if (to < 0 || to >= selected.length) return;
        [selected[index], selected[to]] = [selected[to], selected[index]]; drawOrder(); changed();
      };
      const up = button(doc, "上移", () => move(-1)), down = button(doc, "下移", () => move(1));
      up.setAttribute("aria-label", `上移${name}`); down.setAttribute("aria-label", `下移${name}`);
      setUnavailable(up, index === 0 ? "已经是第一步" : "");
      setUnavailable(down, index === selected.length - 1 ? "已经是最后一步" : "");
      li.append(element(doc, "span", "", `${name} → ${post?.name || "—"}`), up, down); return li;
    }));
  }
  for (const part of state.library.parts) {
    const label = element(doc, "label"), input = element(doc, "input"); input.type = "checkbox"; input.value = part.id;
    label.append(input, element(doc, "span", "", `${part.name} · ${part.code}`)); choices.append(label);
    input.addEventListener("change", () => {
      selected = input.checked ? [...selected, part.id] : selected.filter(id => id !== part.id); drawOrder(); changed();
    });
  }
  fixture.input.addEventListener("change", changed);
  root.append(fixture.label, choices, element(doc, "h3", "", "装配顺序"), order);
  const picker = enhanceSelect(fixture.input);
  return { draft: () => ({ fixture_id: fixture.input.value,
    steps: selected.map((part_id, i) => ({ index: i + 1, part_id, target_id: post?.id, target_name: post?.name })) }),
  reason: () => { picker.render(); return !fixture.input.value ? "请先选择工装" : !selected.length ? "请至少选择一个零件" : !post ? "缺少放置位置" : ""; } };
}
