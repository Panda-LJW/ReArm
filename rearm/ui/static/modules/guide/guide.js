// 解说条：在自己的挂载位里显示“现在 / 下一步”，仿真时提供“演示”按钮按脚本走完一次自愈。
// 只听主程序广播的 rearm:state，只通过公开的 /api/command 发命令，不读写别的模块。
import { narrate } from "./narration.js";
import { buildSteps, runDemo } from "./demo-script.js";

const ICON = { ok: "✓", busy: "◔", bad: "▲", demo: "▶" };
// 命令被拒绝时给观众看的话。后端的英文原因不直接露出来。
const REFUSED = [
  [/emergency stop/, "已急停，演示停止"],
  [/busy/, "机械臂正忙，演示停止"],
  [/simulation-only/, "只有仿真模式能演示"],
];

async function post(name, payload) {
  const response = await fetch("/api/command/" + name, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (response.ok) return response.json().catch(() => ({}));
  const detail = (await response.json().catch(() => ({}))).detail || "";
  throw new Error((REFUSED.find(([pattern]) => pattern.test(detail)) || [null, "这一步没有成功，演示停止"])[1]);
}

export function initGuide({ slot, params = new URLSearchParams() }) {
  slot.innerHTML = `<div class="guide" role="status" hidden><i class="guide-icon" aria-hidden="true"></i><span class="guide-now"></span><span class="guide-next"></span><span class="guide-step" hidden></span><button type="button" class="guide-demo" hidden></button></div>`;
  const bar = slot.firstElementChild, [icon, now, next, stepEl, button] = bar.children;
  let latest = { state: null, connected: false }, demo = null, notice = null, noticeTimer = 0;
  const pause = Math.min(10000, Math.max(0, Number(params.get("demo_pause")) || 2500));

  function render() {
    const { state, connected } = latest;
    const usable = connected && state && !state.estop;
    // 演示进行中：解说条念脚本；否则按状态解说。
    const line = demo ? { tone: demo.phase === "run" ? "busy" : "demo", now: `${demo.step.title}：${demo.step.say}`, next: "" } : notice ? { tone: "bad", now: notice, next: "" } : narrate(latest);
    bar.hidden = !line;
    if (line) {
      bar.dataset.tone = line.tone; icon.textContent = ICON[line.tone];
      now.textContent = line.now; next.textContent = line.next ? "下一步：" + line.next : "";
    }
    stepEl.hidden = !demo; if (demo) stepEl.textContent = `演示 ${demo.index + 1} / ${demo.total}`;
    // “演示”只在仿真里出现（要用到伤注入）；机器忙或急停时不能开始，但进行中的演示随时能停。
    button.hidden = !(state && state.simulation && connected);
    button.textContent = demo ? "停止演示" : "▶ 演示";
    button.disabled = demo ? demo.stopping : !usable || !!state?.busy;
    button.title = demo ? "当前这一步做完后停下" : "自动走一遍：正常 → 弄伤 → 发现并自愈 → 验证 → 认出旧状态";
  }

  async function start() {
    const steps = buildSteps(latest.state || {});
    demo = { index: 0, total: steps.length, step: steps[0], phase: "say", stopping: false };
    notice = null; render();
    const result = await runDemo({
      steps, post, sleep: ms => new Promise(resolve => setTimeout(resolve, ms)), readMs: pause, restMs: Math.round(pause * 0.7),
      onStep: (index, step, phase) => { demo = { ...demo, index, step, phase }; render(); },
      // 急停、断线时立刻不再往下走
      shouldStop: () => demo.stopping || !latest.connected || !!latest.state?.estop,
    });
    demo = null;
    notice = result.error ? result.error.message : result.finished ? null : "演示已停止";
    clearTimeout(noticeTimer); if (notice) noticeTimer = setTimeout(() => { notice = null; render(); }, 6000);
    render();
  }
  button.onclick = () => { if (demo) { demo.stopping = true; render(); } else start(); };
  document.addEventListener("rearm:state", event => { latest = event.detail || latest; render(); });
  render();
  return { isRunning: () => !!demo };
}
