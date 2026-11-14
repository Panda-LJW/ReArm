// 面板和模拟主机共用的纯数字格式：先舍入，再决定符号，避免 −0.00。
export function number(value, digits = 1, signed = false) {
  if (!Number.isFinite(value)) return "—";
  const magnitude = Math.abs(value).toFixed(digits);
  const sign = Number(magnitude) === 0 ? "" : value < 0 ? "−" : signed ? "+" : "";
  return sign + magnitude;
}
