import { frameView } from "../../../shell/view.js";
import { setUnavailable } from "../../../shell/tooltip.js";
import { trainReason, online } from "../../../state/selectors.js";
import { element } from "../../../widgets/dom.js";
import { button, collected } from "./format.js";
import { mount as trainingRecord } from "./training-record.js";

export function mount(root, ctx) {
  const doc = root.ownerDocument, header = element(doc, "header", "library-doc-header");
  const title = element(doc, "h2"), meta = element(doc, "p", "library-muted");
  const message = element(doc, "p", "library-message", "正在读取文档…"); message.setAttribute("role", "status");
  const content = element(doc, "div", "library-doc-body"), summary = element(doc, "section");
  const record = element(doc, "section"), graph = element(doc, "div", "library-training-record");
  record.append(element(doc, "h3", "", ctx.target === "recipe" ? "装配训练记录" : "训练记录"), graph);
  content.append(summary, record);
  let state, current, pending = false, disposed = false, sequence = 0;
  const fresh = () => ctx.store?.getState() || state;
  const retry = button(doc, "重新读取", read);
  const retrain = button(doc, "重新训练", () => {
    if (current && !trainReason(fresh())) ctx.openFlow(ctx.target, current);
  });
  header.append(title, retrain); root.append(header, meta, message, retry, content);
  const training = trainingRecord(graph); content.hidden = true; retry.hidden = true; retrain.hidden = true;
  async function read() {
    if (pending || disposed || !ctx.send) return;
    const request = ++sequence; pending = true; retry.hidden = true;
    message.textContent = "正在读取文档…"; message.hidden = false;
    try {
      const reply = await ctx.send(`${ctx.target}_get`, { id: ctx.id });
      if (!reply?.ok) throw new Error(reply?.msg || "文档读取失败");
      if (!disposed && request === sequence) message.hidden = true;
    } catch (error) {
      if (!disposed && request === sequence) { message.textContent = error.message; retry.hidden = false; }
    } finally { pending = false; }
  }
  void read();
  return frameView(next => {
    state = next;
    const item = next[ctx.target === "part" ? "partDocs" : "recipeDocs"][ctx.id];
    if (item && item !== current) {
      current = item; title.textContent = item.name;
      meta.textContent = `${item.code} · v${item.version} · 收录 ${collected(item.collected_at)}`;
      summary.replaceChildren(); ctx.describe(summary, item, next, ctx);
      training.render(item.training); content.hidden = false; retrain.hidden = false;
    }
    setUnavailable(retrain, trainReason(next)); setUnavailable(retry, online(next) ? "" : "连接就绪后可操作");
  }, () => { disposed = true; sequence++; training.dispose(); root.replaceChildren(); }, doc.defaultView);
}
