import { frameView } from "../../../shell/view.js";
import { element } from "../../../widgets/dom.js";
import { button, collected } from "./format.js";
import { shape } from "./shape.js";

export function mount(root, ctx) {
  const doc = root.ownerDocument, table = element(doc, "table", "library-table");
  const head = element(doc, "thead"), row = element(doc, "tr"), body = element(doc, "tbody");
  for (const name of ["外形", "名称", "编号", "版本", "收录时间"]) {
    const th = element(doc, "th", "", name); th.scope = "col"; row.append(th);
  }
  head.append(row); table.append(head, body);
  const empty = element(doc, "p", "library-muted"); root.append(table, empty);
  let previous;
  return frameView(state => {
    const rows = state.library[ctx.target === "part" ? "parts" : "recipes"];
    if (rows === previous) return; previous = rows;
    table.hidden = rows.length === 0; empty.hidden = rows.length > 0;
    empty.textContent = state.hello ? `还没有${ctx.target === "part" ? "零件" : "配方"}，可从右上角新增。` : "连接就绪后显示列表。";
    body.replaceChildren(...rows.map(item => {
      const tr = element(doc, "tr"), thumb = element(doc, "td"), title = element(doc, "td");
      thumb.append(shape(doc, item, ctx.target === "recipe"));
      const open = button(doc, item.name, () => ctx.openDoc(ctx.target, item.id)); open.className = "library-open";
      if (ctx.target === "part") open.dataset.part = item.id; else open.dataset.recipeDoc = item.id;
      title.append(open); tr.append(thumb, title, element(doc, "td", "library-code", item.code),
        element(doc, "td", "", `v${item.version}`), element(doc, "td", "library-date", collected(item.collected_at)));
      return tr;
    }));
  }, () => root.replaceChildren(), doc.defaultView);
}
