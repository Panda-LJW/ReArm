import { CONFIG } from "./config.js";

// 告警只比较面板本地的指令时间与激光回报接收时间，不读取墙钟或主机 t。
export function summarize(state, config = CONFIG) {
  const results = state.passes.filter(row => row.result).sort((a, b) => a.pass - b.pass);
  const first = results[0]?.result, last = results.at(-1)?.result;
  const firstMeanMm = first?.mean_mm ?? null, lastMeanMm = last?.mean_mm ?? null;
  const lastMaxMm = last?.max_mm ?? null;
  const corrections = state.passes.filter(row => row.correction);
  const expected = state.laserCommand, actual = state.laser;
  return {
    pass: state.joint?.pass ?? state.passes.at(-1)?.pass ?? null,
    lastCompletedPass: results.at(-1)?.pass ?? null,
    lastMeanMm, lastMaxMm, firstMeanMm,
    improvedPct: firstMeanMm > 0 && lastMeanMm !== null ? (firstMeanMm - lastMeanMm) / firstMeanMm * 100 : null,
    corrections: corrections.length ? corrections.filter(row => row.correction.applied === true).length : null,
    belowThreshold: last ? typeof last.below_threshold === "boolean" ? last.below_threshold
      : Number.isFinite(lastMaxMm) && last.valid_nodes === last.total_nodes
        && last.total_nodes > 0 && lastMaxMm <= (config.thresholdMm ?? CONFIG.thresholdMm) : null,
    laserMismatch: expected && actual && Number.isFinite(actual.received_at) && Number.isFinite(expected.t)
      ? expected.want !== actual.on && actual.received_at - expected.t > 1000 : null,
  };
}
