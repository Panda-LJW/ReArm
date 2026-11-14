import { CONFIG } from "./config.js";

// 时间来自 store.t（最新收到的 Unix 毫秒），不读取墙钟，heartbeat 也会推进告警计时。
export function summarize(state, config = CONFIG) {
  const results = state.passes.filter(row => row.result).sort((a, b) => a.pass - b.pass);
  const first = results[0]?.result, last = results.at(-1)?.result;
  const firstMeanMm = first?.mean_mm ?? null, lastMeanMm = last?.mean_mm ?? null;
  const lastMaxMm = last?.max_mm ?? null;
  const corrections = state.passes.filter(row => row.correction);
  const expected = state.laserCommand, actual = state.laser;
  return {
    pass: state.joint?.pass ?? state.passes.at(-1)?.pass ?? null,
    lastMeanMm, lastMaxMm, firstMeanMm,
    improvedPct: firstMeanMm > 0 && lastMeanMm !== null ? (firstMeanMm - lastMeanMm) / firstMeanMm * 100 : null,
    corrections: corrections.length ? corrections.filter(row => row.correction.applied === true).length : null,
    belowThreshold: last ? lastMaxMm !== null && last.valid_nodes === last.total_nodes
      && last.total_nodes > 0 && lastMaxMm < (config.thresholdMm ?? CONFIG.thresholdMm) : null,
    laserMismatch: expected && actual && Number.isFinite(state.t) && Number.isFinite(expected.t)
      ? expected.want !== actual.on && state.t - expected.t > 1000 : null,
  };
}
