// 把面板状态翻译成一句“现在在做什么”和一句“下一步”。纯函数，不碰页面，可在 Node 里单测。
// 输入是主程序广播的 { state, connected }；输出 { tone, now, next }，不需要解说时返回 null。
// tone：ok 正常 | busy 进行中 | bad 需要人处理。
const magnitude = r => (Array.isArray(r) ? Math.hypot(r[0], r[1]) : null);

const BUSY = {
  "发现异常": ["发现异常：连续几发都偏了", "先核对是不是以前见过的状态"],
  "认旧状态": ["正在试打 3 发，核对是不是旧状态", "认得出就直接切回对应版本"],
  "诊断": ["正在诊断：是哪里变了", "找到原因后重新标定"],
  "校准": ["正在重新标定参数", "标定完要过一遍验证"],
  "护栏": ["正在验证新参数靠不靠谱", "通过才启用，不通过保持原版本"],
  "重训残差": ["正在学习细节补偿", "有改善才启用"],
};

export function narrate({ state, connected } = {}) {
  // 断线和急停各有自己的横幅，解说条让位，避免两处说同一件事。
  if (!connected || !state || state.estop) return null;
  const recent = state.recent || [], last = recent[recent.length - 1], alarm = state.alarm_mm ?? 6;
  const healed = Number.isFinite(state.heal_start) ? Math.max(0, (state.shots || 0) - state.heal_start) : null;
  if (BUSY[state.state]) {
    const [now, next] = BUSY[state.state];
    return { tone: "busy", now: healed ? `${now}（已打 ${healed} 发）` : now, next };
  }
  if (state.state === "已拒绝") return { tone: "bad", now: "修复方案没通过验证，仍用原版本", next: "检查机械臂后，再点“自检”" };
  if (state.busy) {
    const what = { baseline: "正在首次标定", selfcheck: "正在自检：打 3 发", preview: "正在预检：试打 3 发", retrain: "正在学习细节补偿", switch: "正在切换版本", inject: "正在注入仿真伤" }[state.active_command];
    return { tone: "busy", now: what || "正在执行操作", next: "完成后这里会更新" };
  }
  if (!last) return { tone: "ok", now: "还没有打靶", next: state.head?.meta?.kind === "initial" ? "先到 ⋯ 做“首次标定”" : "点“自检”打 3 发" };
  const err = magnitude(last.residual);
  if (err == null) return { tone: "bad", now: "最近一发没看到光点", next: "检查摄像头和激光，再点“自检”" };
  if (err > alarm) return { tone: "bad", now: `最近一发偏了 ${err.toFixed(1)} mm，超过阈值`, next: "再点“自检”，连续超限会自动诊断修复" };
  return { tone: "ok", now: `瞄准正常，最近一发误差 ${err.toFixed(2)} mm`, next: "点“自检”再打一组" };
}
