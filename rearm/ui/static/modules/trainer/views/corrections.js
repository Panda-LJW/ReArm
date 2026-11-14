import { online, number, correctionText, preserve, element } from "./format.js";

export function mount(root) {
  const content = root.querySelector("#diag"), title = root.querySelector("#diagtitle"), aside = root.querySelector("#diagaside"), tab = root.querySelector('[data-t="diag"]');
  const dispose = preserve([content, title, aside, tab]); let previous = "";
  title.textContent = tab.textContent = "本遍修正";
  return { dispose, render(state) {
    const rows = state.passes.filter(row => row.correction).slice().reverse(), last = rows[0]?.correction;
    const key = JSON.stringify([online(state), rows]); if (key === previous) return; previous = key;
    content.replaceChildren(); aside.textContent = last ? `第 ${last.pass} 遍` : "";
    if (!online(state)) { content.append(element("div", "empty", "离线")); return; }
    if (!last) { content.append(element("div", "empty", "练习一遍后，这里显示另一台主机做了什么修正")); return; }
    const explanation = element("p", "trainer-explanation");
    explanation.textContent = last.llm_text || "主机未提供说明";
    const items = element("ul", "trainer-correction-items");
    for (const item of last.items || []) {
      const row = element("li"); row.append(element("span", "", item.target), element("span", "num", `${item.delta > 0 ? "+" : ""}${number(item.delta, 2)} ${item.unit}`));
      if (item.note) row.title = item.note;
      items.append(row);
    }
    content.append(explanation, items);
    if (rows.length > 1) {
      const history = element("div", "trainer-correction-history");
      history.setAttribute("aria-label", "更早的修正");
      for (const row of rows.slice(1)) history.append(element("p", "", `第 ${row.pass} 遍：${correctionText(row.correction)}`));
      content.append(history);
    }
  } };
}
