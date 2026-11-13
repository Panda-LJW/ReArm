// 纯数学的正运动学：输入关节角，输出每个关节坐标系的 4×4 位姿。不依赖渲染库，可在 Node 里单测。
// 矩阵按行主序存成长度 16 的数组；坐标系与 URDF 一致（Z 向上，单位见 arm-config.js）。

export const identity = () => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

export function multiply(a, b) {
  const out = new Array(16).fill(0);
  for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) for (let k = 0; k < 4; k++) out[r * 4 + c] += a[r * 4 + k] * b[k * 4 + c];
  return out;
}

// URDF 固定变换：先平移 xyz，再按 Rz(yaw)·Ry(pitch)·Rx(roll) 旋转。
export function fromOrigin([x, y, z], [roll, pitch, yaw]) {
  const cr = Math.cos(roll), sr = Math.sin(roll), cp = Math.cos(pitch), sp = Math.sin(pitch), cy = Math.cos(yaw), sy = Math.sin(yaw);
  return [
    cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr, x,
    sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr, y,
    -sp, cp * sr, cp * cr, z,
    0, 0, 0, 1,
  ];
}

// 绕单位轴旋转 angle（罗德里格斯公式）。
export function fromAxisAngle([x, y, z], angle) {
  const n = Math.hypot(x, y, z) || 1; x /= n; y /= n; z /= n;
  const c = Math.cos(angle), s = Math.sin(angle), t = 1 - c;
  return [
    t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0,
    t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0,
    t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0,
    0, 0, 0, 1,
  ];
}

export const position = m => [m[3], m[7], m[11]];
export const clamp = (v, [lo, hi]) => Math.min(hi, Math.max(lo, v));

// angles: { joint1: rad, ... }，缺省的关节按 0 处理。返回 { frames: {jointId: 矩阵}, tool: 矩阵 }。
// frames[id] 是该关节转动之后的坐标系，也就是它所带连杆的坐标系。
export function forward(config, angles = {}) {
  const frames = {};
  let current = identity();
  for (const joint of config.joints) {
    const q = clamp(Number(angles[joint.id]) || 0, joint.limit);
    current = multiply(multiply(current, fromOrigin(joint.xyz, joint.rpy)), fromAxisAngle(joint.axis, q));
    frames[joint.id] = current;
  }
  return { frames, tool: multiply(current, fromOrigin(config.tool.xyz, config.tool.rpy)) };
}

// 上位机读数（度，按 panelMapping 的顺序）→ URDF 关节角（弧度），未驱动的关节取 restPose。
export function panelToUrdf(config, panelDegrees = []) {
  const angles = { ...config.restPose };
  config.panelMapping.forEach((map, i) => {
    const value = Number(panelDegrees[i]);
    if (!Number.isFinite(value)) return;
    const joint = config.joints.find(j => j.id === map.joint);
    angles[map.joint] = clamp(map.sign * value * Math.PI / 180 + map.offset, joint.limit);
  });
  return angles;
}
