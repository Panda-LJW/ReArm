import { element } from "../../../widgets/dom.js";
import { mount as documentView } from "./library-doc.js";
import { button } from "./format.js";
import { shape } from "./shape.js";

function describe(root, item, state, ctx) {
  const doc = root.ownerDocument, parts = state.library.parts;
  const appearance = element(doc, "div", "library-appearance c-viewport"); appearance.append(shape(doc, item, true));
  root.append(appearance, element(doc, "h3", "c-card-head", "工装"), element(doc, "p", "", item.fixture_name),
    element(doc, "h3", "c-card-head", "装配顺序"));
  const steps = element(doc, "ol", "library-order");
  for (const step of item.steps || []) steps.append(element(doc, "li", "",
    `${parts.find(p => p.id === step.part_id)?.name || step.part_id} → ${step.target_name}`));
  const links = element(doc, "div", "library-part-links");
  for (const id of item.part_ids || []) {
    const open = button(doc, parts.find(p => p.id === id)?.name || id, () => ctx.openDoc("part", id));
    open.dataset.partLink = id; links.append(open);
  }
  root.append(steps, element(doc, "h3", "c-card-head", "用到的零件"), links);
}
export const mount = (root, ctx) => documentView(root, { ...ctx, target: "recipe", describe });
