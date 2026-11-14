import { frameView } from "../../../shell/view.js";
import { element } from "../../../widgets/dom.js";
import { mount as chart } from "../../../widgets/line-chart.js";
import { flash, replay, reducedMotion } from "../../../widgets/motion.js";
import { button, detail, duration, number, collected } from "./format.js";

export function mount(root) {
  root.classList.add("library-training-record");
  const doc = root.ownerDocument, graph = element(doc, "div"), metrics = element(doc, "dl", "library-metrics c-kpis");
  const attempts = element(doc, "div", "library-attempts"), videoSlot = element(doc, "div");
  root.append(metrics, graph, attempts, videoSlot); const curve = chart(graph);
  const win = doc.defaultView;
  let previous, video = null, drawn = false, drawFrame = null;
  return frameView(record => {
    if (record === previous) return; previous = record;
    const training = record || {}, rounds = training.rounds || [], last = rounds.at(-1);
    curve.render(training);
    if (!drawn && drawFrame === null) drawFrame = win.requestAnimationFrame(() => {
      drawFrame = null;
      const line = graph.querySelector("polyline");
      if (!line || line.getAttribute("points").trim().split(/\s+/).length < 2) return;
      drawn = true; line.setAttribute("pathLength", "1");
      if (!reducedMotion(win)) replay(line, "library-curve-draw");
    });
    const values = [["轮次", String(last?.round || 0)], ["最近偏差", `${number(last?.deviation_mm)} mm`],
      ["图像数", String(training.images ?? last?.images ?? 0)], ["用时", duration(training.elapsed_ms ?? last?.elapsed_ms ?? 0)]];
    if (Number.isFinite(training.success_rate)) values.push(["成功率", `${Math.round(training.success_rate * 100)}%`]);
    if (Number.isFinite(training.recorded_at)) values.push(["训练时间", collected(training.recorded_at)]);
    const pairs = new Map([...metrics.children].map(el => [el.querySelector("dt").textContent, el]));
    metrics.replaceChildren(...values.map(([label, value]) => {
      const pair = pairs.get(label) || detail(doc, label, value), number = pair.querySelector("dd");
      number.textContent = value; flash(number, value); return pair;
    }));
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
  }, () => { if (drawFrame !== null) win.cancelAnimationFrame(drawFrame); video?.pause(); curve.dispose(); root.replaceChildren(); }, win);
}
