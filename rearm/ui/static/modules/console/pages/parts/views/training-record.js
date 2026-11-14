import { frameView } from "../../../shell/view.js";
import { element } from "../../../widgets/dom.js";
import { mount as chart } from "../../../widgets/line-chart.js";
import { button, detail, duration, number, collected } from "./format.js";

export function mount(root) {
  root.classList.add("library-training-record");
  const doc = root.ownerDocument, graph = element(doc, "div"), metrics = element(doc, "dl", "library-metrics c-kpis");
  const attempts = element(doc, "div", "library-attempts"), videoSlot = element(doc, "div");
  root.append(metrics, graph, attempts, videoSlot); const curve = chart(graph);
  let previous, video = null;
  return frameView(record => {
    if (record === previous) return; previous = record;
    const training = record || {}, rounds = training.rounds || [], last = rounds.at(-1);
    curve.render(training);
    const previousValues = [...metrics.querySelectorAll("dd")].map(el => el.textContent);
    metrics.replaceChildren(detail(doc, "轮次", String(last?.round || 0)),
      detail(doc, "最近偏差", `${number(last?.deviation_mm)} mm`),
      detail(doc, "图像数", String(training.images ?? last?.images ?? 0)),
      detail(doc, "用时", duration(training.elapsed_ms ?? last?.elapsed_ms ?? 0)));
    if (Number.isFinite(training.success_rate)) metrics.append(detail(doc, "成功率", `${Math.round(training.success_rate * 100)}%`));
    if (Number.isFinite(training.recorded_at)) metrics.append(detail(doc, "训练时间", collected(training.recorded_at)));
    if ([...metrics.querySelectorAll("dd")].some((el, i) => el.textContent !== previousValues[i])) {
      const alternate = metrics.classList.toggle("library-values-a"); metrics.classList.toggle("library-values-b", !alternate);
    }
    attempts.replaceChildren(element(doc, "h3", "c-card-head", "试抓记录"));
    const rows = training.grasp_records || rounds.map(r => ({ round: r.round, ok: r.grasp_ok }));
    if (!rows.length) attempts.append(element(doc, "p", "library-muted", "—"));
    else {
      const list = element(doc, "ul");
      for (const row of rows) list.append(element(doc, "li", `c-tag${row.ok === true ? " ok" : row.ok === false ? " bad" : ""}`, `第 ${row.round} 轮 · ${row.ok === true ? "成功" : row.ok === false ? "失败" : "—"}`));
      attempts.append(list);
    }
    video?.pause(); video = null; videoSlot.replaceChildren();
    if (typeof training.video_url === "string" && training.video_url.trim()) {
      video = element(doc, "video"); video.controls = true; video.muted = true; video.preload = "none";
      video.src = training.video_url; video.hidden = true;
      const play = button(doc, "播放训练录像", () => { video.hidden = false; void video.play()?.catch(() => {}); });
      video.addEventListener("error", () => { videoSlot.replaceChildren(); });
      videoSlot.append(play, video);
    }
  }, () => { video?.pause(); curve.dispose(); root.replaceChildren(); }, doc.defaultView);
}
