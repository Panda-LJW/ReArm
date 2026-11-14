// 只格式化消息里的值；缺测保持为空，不转换成 0。
export const millimeters = value => Number.isFinite(value) && value >= 0 ? `${value.toFixed(1)} mm` : "—";
export function duration(ms) {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const seconds = Math.floor(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
export function time(value) {
  if (!Number.isFinite(value)) return "—";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return [date.getHours(), date.getMinutes(), date.getSeconds()].map(v => String(v).padStart(2, "0")).join(":");
}
