import { frameView } from "../../shell/view.js";
import { initialState } from "../../state/store.js";
import { productionRecords, trainingRecords } from "../../state/selectors.js";
import { element } from "../../widgets/dom.js";
import { duration, millimeters, time } from "../../widgets/format.js";

function recordTable(doc, kind, title, columns, empty) {
  const section = element(doc, "section", "records-section c-card"), heading = element(doc, "h2", "c-card-head", title);
  const count = element(doc, "span", "records-count c-aside");
  heading.append(count);
  heading.id = `records-${kind}-title`;
  const scroll = element(doc, "div", "records-scroll c-card-body"), table = element(doc, "table", "records-table c-table");
  scroll.tabIndex = 0; scroll.setAttribute("role", "region"); scroll.setAttribute("aria-labelledby", heading.id);
  table.dataset.records = kind; table.setAttribute("aria-labelledby", heading.id);
  const head = element(doc, "thead"), row = element(doc, "tr"), body = element(doc, "tbody");
  const numeric = index => index >= 3 || (kind === "training" && index === 2);
  for (const [index, label] of columns.entries()) {
    const cell = element(doc, "th", numeric(index) ? "num" : "", label); cell.scope = "col"; row.append(cell);
  }
  head.append(row); table.append(head, body); scroll.append(table); section.append(heading, scroll);
  return { section, render(rows) {
    count.textContent = `${rows.length} 条`;
    const nodes = rows.map(values => {
      const row = element(doc, "tr");
      for (const [index, value] of values.entries()) {
        const cell = element(doc, "td", numeric(index) ? "num" : "");
        cell.classList.toggle("records-missing", value === "—");
        if (kind === "production" && index === 2) {
          const status = value === "到位" ? " ok" : value === "未到位" ? " bad" : "";
          cell.append(element(doc, "span", `c-tag${status}`, value));
        } else cell.textContent = value;
        row.append(cell);
      }
      return row;
    });
    if (!nodes.length) {
      const row = element(doc, "tr"), cell = element(doc, "td", "records-empty c-empty", empty);
      cell.colSpan = columns.length; row.append(cell); nodes.push(row);
    }
    body.replaceChildren(...nodes);
  } };
}

// 只汇总现有记录用于展示；未知结果不计入到位率，缺测不参与平均值。
function recordSummary(doc) {
  const root = element(doc, "div", "records-summary c-kpis"), values = {};
  for (const [key, label, unit, note] of [
    ["sets", "完成套数", "套", "已完成的生产记录"],
    ["rate", "到位率", "%", "仅统计已知结果"],
    ["deviation", "平均偏差", "mm", "仅统计有效生产偏差"],
    ["trains", "训练记录", "条", "含已收录的训练记录"],
  ]) {
    const item = element(doc, "div", "c-kpi"), value = element(doc, "div", "c-kpi-value records-kpi-value");
    const number = element(doc, "span", "records-kpi-number", "—");
    value.append(number, element(doc, "small", "", unit)); values[key] = number;
    item.append(element(doc, "div", "c-kpi-label", label), value, element(doc, "div", "c-kpi-note", note)); root.append(item);
  }
  return { root, render(state) {
    const runs = productionRecords(state), known = runs.filter(row => typeof row.ok === "boolean");
    const deviations = runs.map(row => row.deviation_mm).filter(value => Number.isFinite(value) && value >= 0);
    const next = { sets: String(runs.length), trains: String(trainingRecords(state).length),
      rate: known.length ? (known.filter(row => row.ok).length / known.length * 100).toFixed(1) : "—",
      deviation: deviations.length ? (deviations.reduce((sum, value) => sum + value, 0) / deviations.length).toFixed(1) : "—" };
    for (const [key, text] of Object.entries(next)) {
      if (values[key].textContent === text) continue;
      // 替换变化的数值节点以触发 CSS 高亮，不添加计时器或修改状态。
      const number = element(doc, "span", "records-kpi-number", text);
      values[key].replaceWith(number); values[key] = number;
    }
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
  const summary = recordSummary(doc);
  root.replaceChildren(element(doc, "h1", "records-title", "记录"), summary.root, runs.section, trains.section);
  let previous = null;
  const view = frameView(next => {
    const state = next || initialState();
    if (!previous || state.runs !== previous.runs || state.trains !== previous.trains || state.archivedTrains !== previous.archivedTrains) {
      summary.render(state);
    }
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
