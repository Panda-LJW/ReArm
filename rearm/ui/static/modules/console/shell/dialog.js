import { setUnavailable } from "./tooltip.js";

let sequence = 0;

export function mount(root = document.body, ctx = {}) {
  const doc = root.ownerDocument, dialog = doc.createElement("dialog");
  dialog.className = "console-dialog"; dialog.setAttribute("aria-modal", "true");
  // 三项能力齐备才启用原生开/关过渡；旧浏览器沿用立即显示/关闭。
  const win = doc.defaultView;
  if (typeof win.CSSStartingStyleRule === "function" &&
      win.CSS?.supports("transition-behavior", "allow-discrete") && win.CSS?.supports("overlay", "auto")) {
    dialog.dataset.motion = "";
  }
  dialog.setAttribute("role", "dialog"); dialog.tabIndex = -1;
  const title = doc.createElement("h2"), content = doc.createElement("div"), actions = doc.createElement("div");
  title.id = `console-dialog-title-${++sequence}`;
  dialog.setAttribute("aria-labelledby", title.id);
  content.className = "console-dialog-content"; actions.className = "console-dialog-actions";
  const cancel = doc.createElement("button"), confirm = doc.createElement("button");
  cancel.type = confirm.type = "button";
  cancel.className = "console-button"; confirm.className = "console-button console-primary";
  cancel.textContent = "取消"; confirm.dataset.action = "confirm";
  actions.append(cancel, confirm); dialog.append(title, content, actions); root.append(dialog);
  let options = {}, returnFocus = null, disposed = false;
  const focusable = () => [...dialog.querySelectorAll('button,a[href],input,select,textarea,[tabindex]')]
    .filter(el => el.tabIndex >= 0 && !el.closest("[hidden],[inert]") &&
      doc.defaultView.getComputedStyle(el).visibility !== "hidden" && doc.defaultView.getComputedStyle(el).display !== "none");
  function close() {
    if (!dialog.open) return;
    dialog.close();
    if (returnFocus?.isConnected) returnFocus.focus();
  }
  function cancelAction() { if (dialog.open) { close(); options.onCancel?.(); } }
  function confirmAction() {
    if (!dialog.open || confirm.getAttribute("aria-disabled") === "true") return;
    // 调用者负责数据指令；通用框只负责确认结果和焦点。
    if (options.onConfirm?.() !== false) close();
  }
  function keydown(event) {
    if (!dialog.open) return;
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); cancelAction(); }
    if (event.key !== "Tab") return;
    const elements = focusable(), first = elements[0] || dialog, last = elements.at(-1) || dialog;
    if (event.shiftKey && (doc.activeElement === first || doc.activeElement === dialog)) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && (doc.activeElement === last || doc.activeElement === dialog)) {
      event.preventDefault(); first.focus();
    }
  }
  function keepFocus(event) {
    if (dialog.open && !dialog.contains(event.target)) (focusable()[0] || dialog).focus();
  }
  const nativeCancel = event => { event.preventDefault(); cancelAction(); };
  dialog.addEventListener("keydown", keydown); dialog.addEventListener("cancel", nativeCancel);
  doc.addEventListener("focusin", keepFocus);
  cancel.addEventListener("click", cancelAction); confirm.addEventListener("click", confirmAction);
  function setConfirmEnabled(enabled, reason = "请先确认所需条件") {
    setUnavailable(confirm, enabled ? "" : reason);
  }
  return {
    open(next = {}) {
      if (disposed) return;
      if (dialog.open) close();
      options = next; returnFocus = doc.activeElement;
      title.textContent = next.title || "确认操作";
      if (typeof next.content === "string") content.textContent = next.content;
      else content.replaceChildren(...(next.content ? [next.content] : []));
      confirm.textContent = next.confirmText || "确认";
      setConfirmEnabled(next.confirmEnabled !== false, next.reason);
      dialog.showModal(); (focusable()[0] || dialog).focus();
    },
    render() {}, setConfirmEnabled, close,
    dispose() {
      if (disposed) return;
      close(); disposed = true;
      doc.removeEventListener("focusin", keepFocus);
      dialog.removeEventListener("keydown", keydown); dialog.removeEventListener("cancel", nativeCancel);
      cancel.removeEventListener("click", cancelAction); confirm.removeEventListener("click", confirmAction);
      dialog.remove();
    },
  };
}
