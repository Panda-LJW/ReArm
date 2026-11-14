// 不使用原生 disabled：按钮仍可聚焦，并由同一个入口拦截激活事件。
export function setUnavailable(button, reason = "") {
  button.setAttribute("aria-disabled", String(Boolean(reason)));
  if (reason) button.dataset.reason = reason;
  else delete button.dataset.reason;
}

export function mount(root = document, ctx = {}) {
  const doc = root.ownerDocument || root, win = doc.defaultView;
  const tip = doc.createElement("div");
  tip.id = "console-disabled-tip"; tip.className = "console-tooltip";
  tip.setAttribute("role", "tooltip"); tip.dataset.tip = ""; tip.hidden = true;
  doc.body.append(tip);
  let owner = null, timer = null;
  const buttonAt = target => target?.closest?.('button,[role="button"]');
  const eligible = button => button?.isConnected && root.contains(button) &&
    button.getAttribute("aria-disabled") === "true" && button.dataset.reason?.trim() &&
    !button.closest("[hidden],[inert],dialog:not([open])");
  function hide() {
    if (timer !== null) win.clearTimeout(timer);
    timer = null;
    if (owner) {
      const ids = (owner.getAttribute("aria-describedby") || "").split(/\s+/).filter(id => id && id !== tip.id);
      if (ids.length) owner.setAttribute("aria-describedby", ids.join(" "));
      else owner.removeAttribute("aria-describedby");
    }
    tip.hidden = true; owner = null;
  }
  function show() {
    timer = null;
    if (!eligible(owner)) return hide();
    // 原生模态框在顶层，原因提示须放在框内才能显示在它上面。
    (owner.closest("dialog[open]") || doc.body).append(tip);
    tip.textContent = owner.dataset.reason; tip.hidden = false;
    const ids = new Set((owner.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
    ids.add(tip.id); owner.setAttribute("aria-describedby", [...ids].join(" "));
    const gap = parseFloat(win.getComputedStyle(tip).getPropertyValue("--sp-2")) || 0;
    const at = owner.getBoundingClientRect(), box = tip.getBoundingClientRect();
    const left = Math.max(gap, Math.min(at.left, win.innerWidth - box.width - gap));
    const below = at.bottom + gap;
    const top = below + box.height + gap <= win.innerHeight ? below : Math.max(gap, at.top - box.height - gap);
    tip.style.left = `${left}px`; tip.style.top = `${top}px`;
  }
  function begin(event) {
    const button = buttonAt(event.target);
    if (!eligible(button) || owner === button) return;
    hide(); owner = button;
    // 留 50ms 事件派发余量，保证 0.8s 前不可见、1.2s 时可见。
    timer = win.setTimeout(show, 850);
  }
  function leave(event) {
    if (buttonAt(event.target) === owner && !owner?.contains(event.relatedTarget)) hide();
  }
  function guard(event) {
    const button = buttonAt(event.target);
    if (button?.getAttribute("aria-disabled") !== "true") return;
    if (event.type.startsWith("key") && !["Enter", " ", "Spacebar"].includes(event.key)) return;
    event.preventDefault(); event.stopImmediatePropagation();
  }
  function escape(event) { if (event.key === "Escape") hide(); }
  const bindings = [
    ["pointerenter", begin], ["pointerleave", leave], ["focusin", begin], ["focusout", leave],
    ["click", guard], ["dblclick", guard], ["keydown", guard], ["keyup", guard], ["keydown", escape],
  ];
  for (const [name, fn] of bindings) root.addEventListener(name, fn, true);
  const observer = new win.MutationObserver(() => {
    if (owner && (!eligible(owner) || (!tip.hidden && tip.textContent !== owner.dataset.reason))) hide();
  });
  observer.observe(doc.body, { subtree: true, childList: true, attributes: true,
    attributeFilter: ["aria-disabled", "data-reason", "hidden", "inert", "open"] });
  win.addEventListener("resize", hide); doc.addEventListener("scroll", hide, true);
  return {
    render() { if (owner && !eligible(owner)) hide(); }, hide,
    dispose() {
      hide(); observer.disconnect(); tip.remove();
      for (const [name, fn] of bindings) root.removeEventListener(name, fn, true);
      win.removeEventListener("resize", hide); doc.removeEventListener("scroll", hide, true);
    },
  };
}
