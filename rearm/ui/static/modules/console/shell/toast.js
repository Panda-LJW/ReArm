import { replay } from "../widgets/motion.js";

export function mount(root = document.body) {
  const doc = root.ownerDocument, win = doc.defaultView;
  const region = doc.createElement("div");
  region.className = "console-toasts"; root.append(region);
  const messages = new Map();
  let disposed = false;
  function remove(key) {
    const entry = messages.get(key);
    if (!entry) return;
    win.clearTimeout(entry.timer); entry.node.remove(); messages.delete(key);
  }
  return {
    show(message, key = message) {
      if (disposed) return;
      const text = String(message || "请求未完成");
      let entry = messages.get(key);
      if (!entry) {
        const node = doc.createElement("div"), label = doc.createElement("span"), close = doc.createElement("button");
        node.className = "c-toast"; node.setAttribute("role", "status"); node.setAttribute("aria-atomic", "true");
        close.type = "button"; close.className = "c-btn"; close.textContent = "关闭";
        close.setAttribute("aria-label", "关闭提示"); close.addEventListener("click", () => remove(key));
        node.append(label, close); region.append(node);
        entry = { node, label, timer: null }; messages.set(key, entry); replay(node, "c-enter");
      }
      entry.label.textContent = text;
      win.clearTimeout(entry.timer);
      entry.timer = win.setTimeout(() => remove(key), 3000);
    },
    dispose() { disposed = true; [...messages.keys()].forEach(remove); region.remove(); },
  };
}

// 第三个参数仅控制本地反馈；数据源仍只收到原来的 cmd/args。
export function commandFeedback(send, toast) {
  return async (cmd, args, { errorFeedback = "toast" } = {}) => {
    try {
      const reply = await send(cmd, args);
      if (reply?.ok === false && errorFeedback !== "dialog") {
        toast.show(reply.msg || "请求未完成", reply.code || reply.msg || "failed");
      }
      return reply;
    } catch (error) {
      if (errorFeedback !== "dialog") toast.show(error?.message || "请求未完成");
      throw error;
    }
  };
}
