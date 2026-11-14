// 虚拟推进与真实计时器经过同一个队列；任务撤销还会清空插值，急停不续跑。
const ease = t => t * t * (3 - 2 * t);
const clonePose = p => ({ q: [...p.q], gripper_mm: p.gripper_mm });
export function createTimeline(initialTime, initialPose) {
  let clock = initialTime, pose = clonePose(initialPose), motion = null, queue = [], serial = 0;
  function sample() {
    if (!motion) return clonePose(pose);
    const k = ease(Math.min(1, Math.max(0, (clock - motion.start) / motion.duration)));
    pose = { q: motion.from.q.map((v, i) => v + (motion.to.q[i] - v) * k),
      gripper_mm: motion.from.gripper_mm + (motion.to.gripper_mm - motion.from.gripper_mm) * k };
    if (k === 1) motion = null;
    return clonePose(pose);
  }
  return {
    time: () => clock, pose: sample,
    at(at, fn) { queue.push({ at, fn, serial: ++serial }); queue.sort((a, b) => a.at - b.at || a.serial - b.serial); },
    cancel() { sample(); motion = null; queue = []; },
    setPose(next) { pose = clonePose(next); motion = null; },
    move(to, duration) { motion = { from: sample(), to: clonePose(to), start: clock, duration }; },
    advance(ms, active = () => true) {
      if (!Number.isFinite(ms) || ms < 0) throw new RangeError("推进时间必须为非负毫秒");
      const target = clock + ms;
      while (active() && queue.length && queue[0].at <= target) {
        const event = queue.shift(); clock = event.at; sample(); event.fn();
      }
      if (active()) { clock = target; sample(); }
    },
  };
}
