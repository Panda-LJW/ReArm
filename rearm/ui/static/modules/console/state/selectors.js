import { WORDS } from "./words.js";

export const online = state => state.link.online === true && state.hello?.proto === 1;
export const readOnlyReason = state => state?.hello?.read_only_reason || state?.link?.read_only_reason || "";
export const demoData = state => state?.hello?.demo_data === true || state?.link?.demo_data === true;
export const sourceName = state => state?.hello?.source || state?.link?.source ||
  (state?.hello?.sim === true ? "本地演示" : state?.hello?.sim === false ? "主机" : "");
export function statusWord(state) {
  if (state.phase === "estop") return WORDS.estop;
  if (state.device) {
    if (!online(state)) return "后端离线";
    const device = state.device;
    return [device.connected === true ? "已连接" : device.connected === false ? "未连接" : "连接未知",
      device.enabled === true ? "已使能" : device.enabled === false ? "未使能" : "使能未知",
      device.busy ? `忙：${device.busy_action || "执行中"}` : ""].filter(Boolean).join(" · ");
  }
  return WORDS[state.training ? "training" : state.phase] || WORDS.idle;
}
export const productionRecords = state => state.runs;
export const trainingRecords = state => [...(state.archivedTrains || []), ...state.trains];
export function productionRecipe(state, selectedId) {
  const id = state.run?.recipe_id || selectedId;
  return state.recipeDocs?.[id] || state.library.recipes.find(recipe => recipe.id === id);
}
export const productionBusy = state => online(state) && state.phase !== "estop" &&
  (Boolean(state.training) || state.phase !== "idle");
export function productionSummary(state) {
  const sets = state.runs.length, passed = state.runs.filter(r => r.ok).length;
  return { sets, passed, passRate: sets ? passed / sets : null,
    deviations: state.runs.slice(-20).map(({ run_id, deviation_mm, ok }) => ({ run_id, deviation_mm, ok })) };
}
export function startReason(state) {
  if (readOnlyReason(state)) return readOnlyReason(state);
  if (!online(state)) return "连接就绪后可操作";
  if (state.phase === "estop") return "请先解除急停";
  if (state.training) return "正在训练，完成后可开始生产";
  return state.phase === "idle" ? "" : "正在生产，完成后可再次开始";
}
export function trainReason(state) {
  if (readOnlyReason(state)) return readOnlyReason(state);
  if (!online(state)) return "连接就绪后可操作";
  if (state.phase === "estop") return "请先解除急停";
  if (state.training) return "正在训练，完成后可再次开始";
  return state.phase === "idle" ? "" : "正在生产，完成后可开始训练";
}
