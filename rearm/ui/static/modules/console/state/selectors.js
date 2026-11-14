import { WORDS } from "./words.js";

export const online = state => state.link.online === true && state.hello?.proto === 1;
export const statusWord = state => WORDS[state.phase === "estop" ? "estop" : state.training ? "training" : state.phase] || WORDS.idle;
export const productionRecords = state => state.runs;
export const trainingRecords = state => [...(state.archivedTrains || []), ...state.trains];
export function productionSummary(state) {
  const sets = state.runs.length, passed = state.runs.filter(r => r.ok).length;
  return { sets, passed, passRate: sets ? passed / sets : null,
    deviations: state.runs.slice(-20).map(({ run_id, deviation_mm, ok }) => ({ run_id, deviation_mm, ok })) };
}
export function startReason(state) {
  if (!online(state)) return "连接就绪后可操作";
  if (state.phase === "estop") return "请先解除急停";
  if (state.training) return "正在训练，完成后可开始生产";
  return state.phase === "idle" ? "" : "正在生产，完成后可再次开始";
}
export function trainReason(state) {
  if (!online(state)) return "连接就绪后可操作";
  if (state.phase === "estop") return "请先解除急停";
  if (state.training) return "正在训练，完成后可再次开始";
  return state.phase === "idle" ? "" : "正在生产，完成后可开始训练";
}
