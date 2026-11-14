import { online } from "../state/selectors.js";

export function createReset(ctx) {
  let pending = false;
  async function perform(demo) {
    if (pending || !online(ctx.store.getState())) return;
    pending = true;
    try {
      // 先清计数再解除急停：状态回到“待命”时，套数已经是 0，不会出现先待命、后清零的一帧。
      if (demo) {
        const reset = await ctx.send("reset_demo");
        if (!reset?.ok) throw new Error(reset?.msg || "重置失败");
      }
      const reply = await ctx.send("reset_estop");
      if (!reply?.ok) throw new Error(reply?.msg || "解除急停失败");
    } catch (error) {
      ctx.dialog.open({ title: "重置未完成", content: error.message });
    } finally { pending = false; }
  }
  return () => {
    const state = ctx.store.getState();
    if (pending || !online(state)) return;
    if (state.hello?.sim === true) { ctx.dialog.close(); return perform(true); }
    if (state.phase === "estop") ctx.dialog.open({ title: "确认解除急停",
      content: "确认工作区安全后解除急停，原流程不会继续。", onConfirm: () => { void perform(false); } });
  };
}
