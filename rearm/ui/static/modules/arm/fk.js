// 六轴 URDF 正运动学。行主序 4×4，m / rad，base_link 坐标系；不含安装台高度。
// 复用既有的纯矩阵运算，保留 URDF 固定旋转的原始精度。
import { identity, multiply, fromOrigin, fromAxisAngle, position } from "../twin/kinematics.js";

export function checkJoints(params, q) {
  const issues = [];
  if (Array.isArray(q) && q.length > 6) issues.push({ joint: null, kind: "missing", value: q.length });
  params.joints.forEach((joint, i) => {
    const value = Array.isArray(q) ? q[i] : undefined;
    const kind = value == null ? "missing" : !Number.isFinite(value) ? "nan"
      : value < joint.limit[0] || value > joint.limit[1] ? "out_of_range" : null;
    if (kind) issues.push({ joint: joint.id, kind, value: value ?? null });
  });
  return { ok: issues.length === 0, issues };
}

export function forwardUrdf(params, q) {
  // 调用者先 checkJoints；仍拒绝缺轴/非数值，避免缺测被隐式当成 0。
  // 有限的越界角按原值计算，不夹限位（可用于诊断和独立数值对照）。
  if (!Array.isArray(q) || q.length !== 6 || !Array.from(q).every(Number.isFinite)) {
    throw new TypeError("需要 6 个有限的 URDF 角（rad）");
  }
  const frames = {};
  let current = identity();
  params.joints.forEach((joint, i) => {
    current = multiply(multiply(current, fromOrigin(joint.xyz, joint.rpy)), fromAxisAngle(joint.axis, q[i]));
    frames[joint.id] = current;
  });
  return { frames, end_link: multiply(current, fromOrigin(params.end_link.xyz, params.end_link.rpy)) };
}

export function endPoses(params, q) {
  const { end_link } = forwardUrdf(params, q);
  return {
    end_link,
    tcp: multiply(end_link, params.T_end_tcp),
    camera: multiply(end_link, params.T_end_camera),
    laser: multiply(end_link, params.T_end_laser),
  };
}

export function laserRay(params, q) {
  const { laser } = endPoses(params, q);
  // 激光固定变换的 +X 是光束方向。
  return { origin: position(laser), direction: [laser[0], laser[4], laser[8]] };
}
