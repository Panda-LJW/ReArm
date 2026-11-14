import { frameView } from "../../../shell/view.js";
import { element } from "../../../widgets/dom.js";
import { button, collected } from "./format.js";
import { shape } from "./shape.js";
import { reducedMotion } from "../../../widgets/motion.js";

export function mount(root, ctx) {
  const doc = root.ownerDocument, table = element(doc, "table", "library-table c-table");
  const heading = element(doc, "h2", "c-card-head", ctx.target === "part" ? "零件" : "配方");
  const scroll = element(doc, "div", "library-list-body c-card-body");
  const head = element(doc, "thead"), row = element(doc, "tr"), body = element(doc, "tbody");
  for (const name of ["外形", "名称", "编号", "版本", "收录时间"]) {
    const th = element(doc, "th", "", name); th.scope = "col"; row.append(th);
  }
  head.append(row); table.append(head, body);
  const empty = element(doc, "p", "library-muted c-empty"); scroll.append(table, empty); root.append(heading, scroll);
  let previous, selected;
  function select(id, focus = false, reveal = focus) {
    selected = id;
    for (const open of body.querySelectorAll(".library-open")) {
      const active = (open.dataset.part || open.dataset.recipeDoc) === id;
      open.tabIndex = active ? 0 : -1;
      open.closest("tr").classList.toggle("library-row-selected", active);
      if (active) {
        if (focus) open.focus({ preventScroll: true });
        if (reveal && !root.closest("[hidden]")) open.closest("tr").scrollIntoView?.({ block: "nearest",
          inline: "nearest", behavior: reducedMotion(doc.defaultView) ? "auto" : "smooth" });
      }
    }
  }
  const view = frameView(state => {
    const rows = state.library[ctx.target === "part" ? "parts" : "recipes"];
    if (rows === previous) return; previous = rows;
    table.hidden = rows.length === 0; empty.hidden = rows.length > 0;
    empty.textContent = state.hello ? `还没有${ctx.target === "part" ? "零件" : "配方"}，可从右上角新增。` : "连接就绪后显示列表。";
    const focused = body.contains(doc.activeElement);
    if (!rows.some(item => item.id === selected)) selected = rows[0]?.id;
    body.replaceChildren(...rows.map(item => {
      const tr = element(doc, "tr", "c-focus-row"), thumb = element(doc, "td"), title = element(doc, "td");
      thumb.append(shape(doc, item, ctx.target === "recipe"));
      const open = button(doc, item.name, () => { select(item.id, true); ctx.openDoc(ctx.target, item.id); }); open.className = "library-open";
      if (ctx.target === "part") open.dataset.part = item.id; else open.dataset.recipeDoc = item.id;
      open.addEventListener("focus", () => select(item.id));
      tr.addEventListener("click", event => { if (!open.contains(event.target)) open.click(); });
      open.addEventListener("keydown", event => {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        if (event.key === "Enter") { event.preventDefault(); open.click(); return; }
        if (!["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const index = rows.findIndex(row => row.id === item.id);
        const next = event.key === "Home" ? 0 : event.key === "End" ? rows.length - 1 :
          Math.max(0, Math.min(rows.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)));
        select(rows[next].id, true);
      });
      title.append(open); tr.append(thumb, title, element(doc, "td", "library-code", item.code),
        element(doc, "td", "library-version", `v${item.version}`), element(doc, "td", "library-date", collected(item.collected_at)));
      return tr;
    }));
    select(selected, focused);
  }, () => root.replaceChildren(), doc.defaultView);
  view.select = select;
  return view;
}
