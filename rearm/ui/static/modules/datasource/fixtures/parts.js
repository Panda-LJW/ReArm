export const THRESHOLD_MM = 1;
export const CAPTURE = { name: "环形垫片", code: "P005", size_mm: [28, 28, 6],
  outline: [[0, 7], [7, 0], [21, 0], [28, 7], [28, 21], [21, 28], [7, 28], [0, 21]] };

export function trainingRecord(values, { t = 1794614400000, roundMs = 1200 } = {}) {
  const rounds = values.map((deviation_mm, i) => ({ round: i + 1, deviation_mm,
    grasp_ok: i > 0, images: (i + 1) * 24, elapsed_ms: (i + 1) * roundMs }));
  return { threshold_mm: THRESHOLD_MM, rounds, grasp_records: rounds.map(({ round, grasp_ok }) => ({ round, ok: grasp_ok })),
    images: rounds.at(-1).images, elapsed_ms: rounds.at(-1).elapsed_ms,
    success_rate: rounds.filter(r => r.grasp_ok).length / rounds.length, recorded_at: t };
}

// 两指各自的法向夹持力；质量为演示估计值，不是实物称重结果。
export function forceBasis(force_n, material = "铝合金", friction = 0.03) {
  return { estimated_mass_kg: force_n * friction * 2 / (9.81 * 6), material,
    friction_coefficient: friction, safety_factor: 6, gravity_m_s2: 9.81, fingers: 2 };
}
const rows = [
  ["plate", "薄片", "P001", "ring", [36, 36, 5], 11.6, "铝合金", 0.03, [4.8, 3.9, 3.1, 2.4, 1.9, 1.4, 1.1, 0.7]],
  ["tube", "空心圆柱", "P002", "tube", [26, 26, 35], 12.3, "铝合金", 0.05, [5.4, 4.5, 3.7, 3.0, 2.4, 1.9, 1.5, 1.1, 0.6]],
  ["sleeve", "短轴套", "P003", "tube", [30, 30, 18], 12.1, "钢", 0.08, [5.7, 4.8, 4.0, 3.3, 2.7, 2.2, 1.8, 1.4, 1.1, 0.5]],
  ["block", "方垫块", "P004", "box", [30, 24, 16], 11.8, "钢", 0.224, [6.1, 5.3, 4.5, 3.8, 3.2, 2.7, 2.2, 1.8, 1.4, 1.1, 0.8]],
];
export const PARTS = rows.map(([id, name, code, shape, size_mm, force_n, material, friction, values], i) => ({
  id, name, code, shape, size_mm, photo_url: null,
  outline: shape === "box" ? [[0, 0], [30, 0], [30, 24], [0, 24]] :
    Array.from({ length: 16 }, (_, k) => [size_mm[0] / 2 * (1 + Math.cos(k * Math.PI / 8)),
      size_mm[1] / 2 * (1 + Math.sin(k * Math.PI / 8))]),
  force_n, force_basis: forceBasis(force_n, material, friction), opening: "full",
  training: trainingRecord(values), collected_at: 1794614400000 + i * 60000, version: 1,
}));
