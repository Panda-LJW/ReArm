import { frameView } from "../../shell/view.js";
import { initialState } from "../../state/store.js";
import { productionRecords, trainingRecords } from "../../state/selectors.js";
import { element } from "../../widgets/dom.js";
import { duration, millimeters, time } from "../../widgets/format.js";

function recordTable(doc, kind, title, columns, empty) {
  const section = element(doc, "section", "records-section"), heading = element(doc, "h2", "", title);
  heading.id = `records-${kind}-title`;
  const scroll = element(doc, "div", "records-scroll"), table = element(doc, "table", "records-table");
  scroll.tabIndex = 0; scroll.setAttribute("role", "region"); scroll.setAttribute("aria-labelledby", heading.id);
  table.dataset.records = kind; table.setAttribute("aria-labelledby", heading.id);
  const head = element(doc, "thead"), row = element(doc, "tr"), body = element(doc, "tbody");
  for (const label of columns) { const cell = element(doc, "th", "", label); cell.scope = "col"; row.append(cell); }
  head.append(row); table.append(head, body); scroll.append(table); section.append(heading, scroll);
  return { section, render(rows) {
    const nodes = rows.map(values => {
      const row = element(doc, "tr");
      for (const value of values) row.append(element(doc, "td", value === "—" ? "records-missing" : "", value));
      return row;
    });
    if (!nodes.length) {
      const row = element(doc, "tr"), cell = element(doc, "td", "records-empty", empty);
      cell.colSpan = columns.length; row.append(cell); nodes.push(row);
    }
    body.replaceChildren(...nodes);
  } };
}

const nameOf = (id, items, docs) => items.find(item => item.id === id)?.name || docs[id]?.name || id || "—";
function trainingObject(row, state) {
  if (row.target === "part") return `零件 · ${nameOf(row.doc_id, state.library.parts, state.partDocs)}`;
  if (row.target === "recipe") return `配方 · ${nameOf(row.doc_id, state.library.recipes, state.recipeDocs)}`;
  return row.doc_id || "—";
}

export function mount(root, ctx = {}) {
  const doc = root.ownerDocument, css = element(doc, "link");
  css.rel = "stylesheet"; css.href = new URL("./records.css", import.meta.url).href; doc.head.append(css);
  const runs = recordTable(doc, "production", "生产记录", ["时间", "配方", "结果", "偏差", "用时"], "还没有生产记录");
  const trains = recordTable(doc, "training", "训练记录", ["时间", "对象", "轮数", "最终偏差", "用时"], "还没有训练记录");
  root.replaceChildren(element(doc, "h1", "", "记录"), runs.section, trains.section);
  let previous = null;
  const view = frameView(next => {
    const state = next || initialState();
    // 高频关节消息不重建记录行，保留阅读位置和文本选择。
    if (!previous || state.runs !== previous.runs || state.library.recipes !== previous.library.recipes || state.recipeDocs !== previous.recipeDocs) {
      runs.render([...productionRecords(state)].reverse().map(row => [time(row.t),
        nameOf(row.recipe_id, state.library.recipes, state.recipeDocs),
        row.ok === true ? "到位" : row.ok === false ? "未到位" : "—", millimeters(row.deviation_mm), duration(row.duration_ms)]));
    }
    if (!previous || state.trains !== previous.trains || state.library !== previous.library ||
        state.partDocs !== previous.partDocs || state.recipeDocs !== previous.recipeDocs) {
      trains.render([...trainingRecords(state)].reverse().map(row => [time(row.t), trainingObject(row, state),
        Number.isInteger(row.round) && row.round >= 0 ? `${row.round} 轮` : "—", millimeters(row.deviation_mm), duration(row.elapsed_ms)]));
    }
    previous = state;
  }, () => { css.remove(); root.replaceChildren(); }, doc.defaultView);
  view.render(ctx.store?.getState() || initialState());
  return view;
}
