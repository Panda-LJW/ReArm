import { canvasContext, px, token } from "./canvas.js";
import { online, number, preserve, element } from "./format.js";

export function niceTicks(maxValue, threshold) {
  // 含 0 共 3–5 个刻度；极小或空范围按最小整数步长 1 展开。
  const limit = Math.max(2, ...[maxValue, threshold].filter(Number.isFinite));
  const target = limit / 4, scale = 10 ** Math.max(0, Math.floor(Math.log10(target)));
  const step = [1, 2, 5, 10].map(value => value * scale).find(value => value >= target);
  const count = Math.ceil(limit / step), top = count * step;
  return { top, step, ticks: Array.from({ length: count + 1 }, (_, i) => i * step) };
}

export function mount(root) {
  const canvas = root.querySelector("#errchart"), heading = root.querySelector("h3"), legend = root.querySelector(".legendline");
  const restore = preserve([heading, legend]), label = canvas.getAttribute("aria-label");
  const move = canvas.onmousemove, leave = canvas.onmouseleave;
  canvas.onmousemove = canvas.onmouseleave = null;
  heading.replaceChildren(document.createTextNode("偏差"), element("span", "aside", "每一遍 · mm · 线性刻度"));
  legend.replaceChildren(...[["平均偏差", "--data"], ["最大偏差", "--geo"], ["阈值", "--warn"]].map(([text, color]) => {
    const el = element("span", "", text); el.style.setProperty("--c", `var(${color})`); return el;
  }));
  return { dispose() { restore(); canvas.onmousemove = move; canvas.onmouseleave = leave; canvas.setAttribute("aria-label", label); }, render(state, summary) {
    const rows = state.passes.filter(row => row.result).map(row => row.result);
    const { ctx: g, width: w, height: h } = canvasContext(canvas), font = Math.max(px("--fs-chart"), px("--fs-sm"));
    g.font = `${font}px ${token("--sans")}`; g.fillStyle = token("--mute");
    const empty = !online(state) ? "离线" : "完成一遍练习后显示";
    canvas.setAttribute("aria-label", !online(state) || !rows.length ? `偏差：${empty}` :
      `偏差：${rows.length} 遍，最近平均 ${number(summary.lastMeanMm)} 毫米，最大 ${number(summary.lastMaxMm)} 毫米，阈值 ${summary.thresholdMm} 毫米`);
    if (!online(state) || !rows.length) { g.textAlign = "center"; g.fillText(empty, w / 2, h / 2); return; }
    const maxValue = Math.max(0, ...rows.flatMap(r => [r.mean_mm, r.max_mm]).filter(Number.isFinite));
    const { top, ticks } = niceTicks(maxValue, summary.thresholdMm);
    const left = Math.max(g.measureText(number(top, 0)).width + font, font * 2.5), right = font * 2.5, bottom = font * 1.8, upper = font * 1.4;
    const x = i => left + (w - left - right) * (rows.length === 1 ? 0.5 : i / (rows.length - 1));
    const y = value => upper + (h - upper - bottom) * (1 - value / top);
    g.lineWidth = 1; g.textAlign = "left";
    for (const v of ticks) {
      g.strokeStyle = token("--grid"); g.beginPath(); g.moveTo(left, y(v)); g.lineTo(w - right, y(v)); g.stroke();
      if (v !== summary.thresholdMm) { g.fillStyle = token("--mute"); g.fillText(number(v, 0), 0, y(v) + font * 0.3); }
    }
    g.strokeStyle = token("--warn"); g.setLineDash([font * .4, font * .3]);
    g.beginPath(); g.moveTo(left, y(summary.thresholdMm)); g.lineTo(w - right, y(summary.thresholdMm)); g.stroke();
    g.fillStyle = token("--warn"); g.fillText(`阈值 ${summary.thresholdMm}`, left, Math.max(font, y(summary.thresholdMm) - font * .4));
    for (const [field, color, dashed] of [["mean_mm", "--data", false], ["max_mm", "--geo", true]]) {
      g.strokeStyle = g.fillStyle = token(color); g.lineWidth = 2; g.setLineDash(dashed ? [font * .5, font * .35] : []);
      g.beginPath(); let connected = false;
      rows.forEach((row, i) => { if (!Number.isFinite(row[field])) { connected = false; return; }
        if (connected) g.lineTo(x(i), y(row[field])); else g.moveTo(x(i), y(row[field])); connected = true;
      }); g.stroke();
      rows.forEach((row, i) => { if (Number.isFinite(row[field])) { g.beginPath(); g.arc(x(i), y(row[field]), 2.5, 0, Math.PI * 2); g.fill(); } });
    }
    g.setLineDash([]); g.textAlign = "center"; g.fillStyle = token("--mute");
    const labelWidth = g.measureText(`第 ${rows.at(-1).pass} 遍`).width + font;
    const every = Math.max(1, Math.ceil(labelWidth * rows.length / Math.max(1, w - left - right)));
    rows.forEach((row, i) => { if (i % every === 0) g.fillText(`第 ${row.pass} 遍`, x(i), h - font * .3); });
  } };
}
