// JointFrame：数据源发给显示模块的唯一数据形状。真实接口、面板、模拟器都要先整理成它。
//   timestamp   Unix 秒
//   q_rad       长度 6 的 URDF 角（rad），或 null；数值合法性由显示/轨迹入口检查
//   valid       长度 6 的布尔数组，缺省全 true；显式缺测保留为 false
//   gripper_mm  两指内侧间距（mm），或 null
//   angles_deg  上位机约定的关节角数组 [J1, J2, J3, ...]，单位度；没有读数时为 null
//   mode        "live" 真机实时 | "sim" 模拟数据 | "offline" 数据中断
//   online      数据链路是否正常；false 时显示端应提示离线并保留最后姿态
//   laser       激光是否出光；未知为 null
export const MODES = ["live", "sim", "offline"];

export function makeFrame({ q_rad = null, valid, gripper_mm = null, angles_deg = null, mode = "offline", online, laser = null, timestamp } = {}) {
  const clean = Array.isArray(angles_deg) && angles_deg.length && angles_deg.every(v => Number.isFinite(Number(v))) ? angles_deg.map(Number) : null;
  const safeMode = MODES.includes(mode) ? mode : "offline";
  return {
    timestamp: Number.isFinite(timestamp) ? timestamp : Date.now() / 1000,
    q_rad: Array.isArray(q_rad) && q_rad.length === 6 ? Array.from(q_rad) : null,
    valid: valid === undefined ? Array(6).fill(true) : Array.from({ length: 6 }, (_, i) => Array.isArray(valid) && valid.length === 6 && valid[i] === true),
    gripper_mm: Number.isFinite(gripper_mm) ? gripper_mm : null,
    angles_deg: clean,
    mode: safeMode,
    online: typeof online === "boolean" ? online && safeMode !== "offline" : safeMode !== "offline",
    laser: typeof laser === "boolean" ? laser : null,
  };
}

// 所有数据源共用的小型发布器：subscribe(cb) 返回取消函数；新订阅者立即拿到最近一帧。
export function createEmitter() {
  const listeners = new Set();
  let last = null;
  return {
    emit(frame) { last = frame; for (const cb of [...listeners]) cb(frame); },
    subscribe(cb) { listeners.add(cb); if (last) cb(last); return () => listeners.delete(cb); },
    last: () => last,
  };
}
