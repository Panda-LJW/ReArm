// 原始测量帧 → 末端路径。t 为 Unix 毫秒；不排序、不插值、不修补无效帧。
import { checkJoints, endPoses } from "./fk.js";

export function buildPath(params, samples, { point = "tcp", maxGapMs = 500 } = {}) {
  if (!["end_link", "tcp", "camera", "laser"].includes(point)) throw new RangeError("未知末端参考点：" + point);
  if (!Number.isFinite(maxGapMs) || maxGapMs < 0) throw new RangeError("maxGapMs 必须是非负毫秒数");
  const segments = [], dropped = [];
  let segment = null, previous = null;
  for (const sample of samples) {
    const { t, q, valid } = sample;
    const checked = checkJoints(params, q);
    const badValidity = valid !== undefined && (!Array.isArray(valid) || valid.length !== 6 || !Array.from(valid).every(v => v === true));
    const reason = !Number.isFinite(t) ? "invalid_timestamp" : !checked.ok
      ? checked.issues.map(i => `${i.joint || "q"}:${i.kind}`).join(",") : badValidity ? "invalid_joint" : null;
    if (reason) { dropped.push({ t, reason }); segment = null; previous = null; continue; }
    if (previous !== null && (t - previous > maxGapMs || t < previous)) segment = null;
    if (!segment) { segment = []; segments.push(segment); }
    const m = endPoses(params, q)[point];
    segment.push({ t, p: [m[3], m[7], m[11]] });
    previous = t;
  }
  return { segments, dropped };
}
