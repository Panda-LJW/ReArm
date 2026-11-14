import { element } from "../../widgets/dom.js";
import { swap } from "../../widgets/motion.js";

// 排序仅作用于展示副本，保留原始记录、缺测值和表头节点。
export function recordTable(doc, kind, title, columns, empty) {
  const section = element(doc, "section", "records-section c-card"), heading = element(doc, "h2", "c-card-head", title);
  const count = element(doc, "span", "records-count c-aside");
  heading.append(count); heading.id = `records-${kind}-title`;
  const scroll = element(doc, "div", "records-scroll c-card-body"), table = element(doc, "table", "records-table c-table");
  scroll.tabIndex = 0; scroll.setAttribute("role", "region"); scroll.setAttribute("aria-labelledby", heading.id);
  table.dataset.records = kind; table.setAttribute("aria-labelledby", heading.id);
  const head = element(doc, "thead"), header = element(doc, "tr"), body = element(doc, "tbody");
  const numeric = index => index >= 3 || (kind === "training" && index === 2);
  const headers = new Map();
  let records = [], format, sortKey = "t", direction = "descending", swapping = false, disposed = false;

  function markSort() {
    for (const [key, cell] of headers) cell.setAttribute("aria-sort", key === sortKey ? direction : "none");
  }
  function sortBy(key) {
    if (disposed) return;
    direction = key === sortKey && direction === "ascending" ? "descending" : "ascending";
    sortKey = key; markSort(); swapping = true;
    void swap(body, () => {
      if (!swapping || disposed) return;
      swapping = false; draw();
    }, doc.defaultView);
  }
  for (const [index, [label, key]] of columns.entries()) {
    const cell = element(doc, "th", numeric(index) ? "num" : ""); cell.scope = "col";
    if (key) {
      const button = element(doc, "button", "records-sort", label);
      button.type = "button"; button.dataset.sort = key;
      cell.append(button); cell.addEventListener("click", () => sortBy(key)); headers.set(key, cell);
    } else cell.textContent = label;
    header.append(cell);
  }
  markSort(); head.append(header); table.append(head, body); scroll.append(table); section.append(heading, scroll);

  function value(row) {
    const number = row[sortKey];
    if (!Number.isFinite(number)) return null;
    if (sortKey === "t") return Number.isFinite(new Date(number).getTime()) ? number : null;
    if (number < 0 || (sortKey === "round" && !Number.isInteger(number))) return null;
    return number;
  }
  function compare(a, b) {
    const left = value(a), right = value(b), sign = direction === "ascending" ? 1 : -1;
    // 无时间记录沿用原先倒序时靠前的行为；其余缺测始终放末尾，不当成 0。
    if (left === null || right === null) {
      if (left === right) return 0;
      return (left === null ? 1 : -1) * (sortKey === "t" ? sign : 1);
    }
    return (left - right) * sign;
  }
  function draw() {
    if (disposed) return;
    const nodes = [...records].reverse().sort(compare).map(record => {
      const row = element(doc, "tr");
      for (const [index, value] of format(record).entries()) {
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
      if (kind === "production") cell.append(element(doc, "p", "records-empty-note", "完成一次生产后这里会出现记录"));
      cell.colSpan = columns.length; row.append(cell); nodes.push(row);
    }
    body.replaceChildren(...nodes);
  }
  return { section, render(next, formatter) {
    if (disposed) return;
    records = next; format = formatter; count.textContent = `${records.length} 条`;
    // 交叉淡入期间收到的新记录在替换时一起绘制，避免旧快照覆盖新内容。
    if (!swapping) draw();
  }, dispose() { disposed = true; } };
}
