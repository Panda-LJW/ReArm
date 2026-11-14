// 一键演示的脚本和执行器。只描述“按什么顺序发哪些命令、每步对观众说什么”，
// 实际发命令的函数由外面传入，所以可以在 Node 里用假的 post 单测。
// 脚本只用面板已有的公开命令（selfcheck / baseline / inject），不绕过任何检查。

// 根据当前状态生成步骤。还没做过首次标定时，先补一步标定。
export function buildSteps(state = {}) {
  const steps = [];
  if (state.head?.meta?.kind === "initial" || !state.head)
    steps.push({ title: "首次标定", say: "先让它学会自己的尺寸：试打几十发，拟合出参数", actions: [["baseline"]] });
  steps.push(
    { title: "正常状态", say: "打 3 发看看：瞄准是准的", actions: [["selfcheck"]] },
    { title: "故意弄伤", say: "把底座关节装错一格（约 12°），它自己还不知道", actions: [["inject", { kind: "j1", amount: 1 }]] },
    { title: "发现并自愈", say: "再打：它发现不准，自己诊断原因、重新标定、验证后启用新版本", actions: [["selfcheck"]] },
    { title: "验证", say: "修好之后再打 3 发：又准了", actions: [["selfcheck"]] },
    { title: "认出旧状态", say: "把伤复原：它认出这是以前见过的状态，3 发就切回旧版本", actions: [["inject", { kind: "restore", amount: 0 }], ["selfcheck"], ["selfcheck"]] },
  );
  return steps;
}

// 依次执行步骤。post(name, payload) 发命令并在完成后返回；sleep(ms) 等待；
// onStep(index, step, phase) 通知界面（phase: "say" 先念词、"run" 执行中、"done" 这步完成）；
// shouldStop() 返回 true 时在下一个间隙停下。返回 { finished, stoppedAt, error }。
export async function runDemo({ steps, post, sleep, onStep = () => {}, shouldStop = () => false, readMs = 2500, restMs = 1800 }) {
  for (let i = 0; i < steps.length; i++) {
    if (shouldStop()) return { finished: false, stoppedAt: i, error: null };
    onStep(i, steps[i], "say");
    await sleep(readMs);                       // 先给观众读这一步要做什么
    for (const [name, payload] of steps[i].actions) {
      if (shouldStop()) return { finished: false, stoppedAt: i, error: null };
      onStep(i, steps[i], "run");
      try { await post(name, payload || {}); }
      catch (error) { return { finished: false, stoppedAt: i, error }; }
    }
    onStep(i, steps[i], "done");
    await sleep(restMs);                       // 留一点时间看结果
  }
  return { finished: true, stoppedAt: steps.length, error: null };
}
