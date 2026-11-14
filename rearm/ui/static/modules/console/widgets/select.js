import { element } from "./dom.js";

let sequence = 0;
const instances = new WeakMap();

// 原生 select 仍是唯一数据源；直接设置 value 后，页面 render 时调用 render()。
// meta(option) 返回已有数据的简短说明，空值不占位置。
export function enhanceSelect(select, { meta = () => "" } = {}) {
  if (instances.has(select)) return instances.get(select);
  const doc = select.ownerDocument, win = doc.defaultView, id = `c-select-${++sequence}`;
  const original = ["aria-hidden", "tabindex"].map(name => [name, select.getAttribute(name)]);
  const wrapper = element(doc, "span", "c-select"), trigger = element(doc, "button", "c-select-trigger");
  const name = element(doc, "span", "c-select-name"), detail = element(doc, "span", "c-select-meta");
  const chevron = element(doc, "span", "c-select-chevron"), list = element(doc, "div", "c-select-list");
  trigger.type = "button"; trigger.id = `${id}-trigger`; trigger.setAttribute("role", "combobox");
  trigger.setAttribute("aria-haspopup", "listbox"); trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-controls", id); chevron.setAttribute("aria-hidden", "true");
  list.id = id; list.setAttribute("role", "listbox"); list.setAttribute("aria-labelledby", trigger.id);
  trigger.append(name, detail, chevron); select.before(wrapper); wrapper.append(select, trigger, list);
  list.inert = true; list.setAttribute("aria-hidden", "true");
  select.classList.add("c-select-native"); select.setAttribute("aria-hidden", "true"); select.tabIndex = -1;
  let opened = false, disposed = false, active = -1, rows = [], signature = "", removeTimer = null;
  let query = "", typedAt = 0, selectedOption = null;
  const options = () => [...select.options];
  const blocked = () => select.disabled || select.getAttribute("aria-disabled") === "true";
  const available = option => option && !option.disabled && !option.parentElement?.disabled && !option.hidden && !option.parentElement?.hidden;
  function highlight(index, reveal = false) {
    active = index;
    rows.forEach((row, i) => row.classList.toggle("is-active", i === active));
    if (opened && rows[active]) trigger.setAttribute("aria-activedescendant", rows[active].id);
    else trigger.removeAttribute("aria-activedescendant");
    if (reveal) rows[active]?.scrollIntoView?.({ block: "nearest" });
  }
  function position() {
    if (!opened) return;
    if (!trigger.isConnected || trigger.closest('[hidden],[inert]')) return close();
    const box = trigger.getBoundingClientRect(), style = win.getComputedStyle(list);
    list.style.width = `${box.width}px`; list.style.left = `${box.left}px`;
    const gap = parseFloat(style.getPropertyValue("--sp-1")) || 4;
    const below = win.innerHeight - box.bottom - gap * 2, above = box.top - gap * 2;
    const height = Math.min(list.scrollHeight, 280);
    const up = below < height && above > below;
    list.dataset.side = up ? "up" : "down";
    list.style.maxHeight = `${Math.max(0, Math.min(280, up ? above : below))}px`;
    list.style.top = up ? "auto" : `${box.bottom + gap}px`;
    list.style.bottom = up ? `${win.innerHeight - box.top + gap}px` : "auto";
  }
  function render() {
    if (disposed) return;
    const opts = options(), label = select.getAttribute("aria-label") || select.labels?.[0]?.textContent.trim() || "选择";
    trigger.setAttribute("aria-label", label); trigger.setAttribute("aria-disabled", String(blocked()));
    if (select.dataset.reason) trigger.dataset.reason = select.dataset.reason; else delete trigger.dataset.reason;
    const values = opts.map(option => [option.label, String(meta(option) ?? ""), available(option), option.hidden]);
    const next = JSON.stringify(values);
    if (signature !== next) {
      signature = next;
      rows = values.map(([text, info, enabled, hidden], index) => {
        const row = element(doc, "div", "c-select-option"), tick = element(doc, "span", "c-select-tick", "✓");
        row.id = `${id}-${index}`; row.dataset.index = String(index); row.setAttribute("role", "option");
        row.setAttribute("aria-disabled", String(!enabled)); row.hidden = hidden; tick.setAttribute("aria-hidden", "true");
        const aside = element(doc, "span", "c-select-meta", info); aside.hidden = !info;
        row.append(element(doc, "span", "c-select-name", text), aside, tick); return row;
      });
      list.replaceChildren(...rows);
    }
    const index = select.selectedIndex;
    name.textContent = opts[index]?.label || ""; detail.textContent = values[index]?.[1] || ""; detail.hidden = !detail.textContent;
    rows.forEach((row, i) => row.setAttribute("aria-selected", String(i === index)));
    if (!opened || opts[index] !== selectedOption || !available(opts[active])) active = available(opts[index]) ? index : opts.findIndex(available);
    selectedOption = opts[index];
    if (blocked()) close();
    highlight(active); position();
  }
  // 复用调用方挂在原生 select 上的 guard，不绕过忙碌/运行中拦截。
  function allowed(event) {
    const keyboard = event.type === "keydown";
    const forwarded = keyboard ? new win.KeyboardEvent("keydown", { key: event.key, code: event.code,
      ctrlKey: event.ctrlKey, altKey: event.altKey, metaKey: event.metaKey, shiftKey: event.shiftKey,
      repeat: event.repeat, bubbles: true, cancelable: true }) : new win.MouseEvent("mousedown", { bubbles: true, cancelable: true });
    const accepted = select.dispatchEvent(forwarded); render(); return accepted && !blocked();
  }
  function outside(event) { if (!wrapper.contains(event.target) && !list.contains(event.target)) close(); }
  const lifecycle = new win.MutationObserver(() => {
    if (!trigger.isConnected || trigger.closest('[hidden],[inert]')) close();
  });
  function open() {
    render(); if (opened || blocked() || !options().some(available)) return;
    win.clearTimeout(removeTimer); removeTimer = null;
    (select.closest("dialog[open]") || doc.body).append(list);
    opened = true; list.inert = false; list.setAttribute("aria-hidden", "false");
    trigger.setAttribute("aria-expanded", "true"); position();
    void list.offsetHeight; list.dataset.open = "true"; highlight(active, true);
    doc.addEventListener("pointerdown", outside, true); doc.addEventListener("click", outside, true);
    doc.addEventListener("focusin", outside, true); doc.addEventListener("scroll", position, true); win.addEventListener("resize", position);
    lifecycle.observe(doc.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden", "inert"] });
  }
  function close(restoreFocus = false) {
    if (!opened) return;
    opened = false; query = ""; trigger.setAttribute("aria-expanded", "false"); trigger.removeAttribute("aria-activedescendant");
    list.dataset.open = "false"; list.inert = true; list.setAttribute("aria-hidden", "true"); lifecycle.disconnect();
    doc.removeEventListener("pointerdown", outside, true); doc.removeEventListener("click", outside, true);
    doc.removeEventListener("focusin", outside, true); doc.removeEventListener("scroll", position, true); win.removeEventListener("resize", position);
    const time = win.getComputedStyle(list).transitionDuration.split(",").map(s => parseFloat(s) * (s.trim().endsWith("ms") ? 1 : 1000));
    const delay = win.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? 0 : Math.max(0, ...time.filter(Number.isFinite));
    if (delay) removeTimer = win.setTimeout(() => { wrapper.append(list); removeTimer = null; }, delay); else wrapper.append(list);
    if (restoreFocus) trigger.focus();
  }
  function choose(index, event) {
    if (!allowed(event) || !available(options()[index])) return;
    select.value = options()[index].value;
    select.dispatchEvent(new win.Event("change", { bubbles: true })); render(); close(true);
  }
  function keydown(event) {
    if (event.key === "Tab") { close(); return; }
    if (event.key === "Escape") { if (opened) { event.preventDefault(); event.stopPropagation(); close(true); } return; }
    if (event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
    if (!allowed(event)) { event.preventDefault(); return; }
    const wasOpen = opened, key = event.key;
    if (["Enter", " ", "ArrowDown", "ArrowUp", "Home", "End"].includes(key)) {
      event.preventDefault();
      if ((key === "Enter" || key === " ") && wasOpen) { choose(active, event); return; }
      open();
      const indices = options().flatMap((option, i) => available(option) ? [i] : []), at = indices.indexOf(active);
      if (key === "Home") highlight(indices[0], true);
      else if (key === "End") highlight(indices.at(-1), true);
      else if (wasOpen && key.startsWith("Arrow")) highlight(indices[Math.max(0, Math.min(indices.length - 1, at + (key === "ArrowDown" ? 1 : -1)))], true);
    } else if (key.length === 1) {
      event.preventDefault(); open();
      const now = Date.now(); query = now - typedAt > 700 ? key : query + key; typedAt = now;
      const search = [...query].every(char => char === key) ? key : query;
      const opts = options(), from = search.length === 1 ? active + 1 : active;
      for (let n = 0; n < opts.length; n++) {
        const i = (Math.max(0, from) + n) % opts.length;
        if (available(opts[i]) && opts[i].label.toLocaleLowerCase().startsWith(search.toLocaleLowerCase())) { highlight(i, true); break; }
      }
    }
  }
  const toggle = event => { if (allowed(event)) { if (opened) close(); else open(); } };
  const pick = event => { const row = event.target.closest('[role="option"]'); if (row) choose(Number(row.dataset.index), event); };
  const hover = event => { const row = event.target.closest('[role="option"]'); if (row && available(options()[Number(row.dataset.index)])) highlight(Number(row.dataset.index)); };
  const keepFocus = event => event.preventDefault();
  trigger.addEventListener("mousedown", event => { if (!allowed(event)) event.preventDefault(); });
  trigger.addEventListener("click", toggle); trigger.addEventListener("keydown", keydown); trigger.addEventListener("focus", render);
  list.addEventListener("mousedown", keepFocus); list.addEventListener("click", pick); list.addEventListener("pointermove", hover);
  select.addEventListener("change", render);
  const observer = new win.MutationObserver(render);
  observer.observe(select, { childList: true, subtree: true, characterData: true, attributes: true,
    attributeFilter: ["label", "value", "selected", "disabled", "hidden", "aria-disabled", "aria-label", "data-reason"] });
  const view = { render, dispose() {
    if (disposed) return;
    close(); disposed = true; win.clearTimeout(removeTimer); observer.disconnect(); lifecycle.disconnect(); list.remove();
    select.removeEventListener("change", render); select.classList.remove("c-select-native");
    for (const [name, value] of original) { if (value === null) select.removeAttribute(name); else select.setAttribute(name, value); }
    wrapper.replaceWith(select); instances.delete(select);
  } };
  instances.set(select, view); render(); return view;
}
