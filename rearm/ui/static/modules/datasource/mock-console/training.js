import { POSES, OPEN_MM } from "../fixtures/poses.js";
import { TRAIN_ROUND_MS, trainingImages } from "../fixtures/parts.js";

export function scheduleTraining({ timeline, emit, library, trainId, target, draft }) {
  const started = timeline.time(), rounds = [];
  const values = [4.8, 3.9, 3.1, 2.4, 1.8, 1.4, 1.1, 0.6];
  values.forEach((deviation_mm, i) => {
    // 同一个竖直平面内小角度观察；最后一轮回到观察位并张开。
    const q = [...POSES.observe]; q[1] += i % 2 ? 0 : 0.04; q[3] += i % 2 ? 0 : 0.04;
    timeline.at(started + i * 1200, () =>
      timeline.move({ q, gripper_mm: i === values.length - 1 || i % 2 ? OPEN_MM : 28 }, 1200));
    timeline.at(started + (i + 1) * 1200, () => {
    // 画面每 1.2 秒推进一轮，训练数据使用每轮 5 分钟的训练时钟。
    const elapsed_ms = (i + 1) * TRAIN_ROUND_MS;
    const progress = { train_id: trainId, target, round: i + 1, deviation_mm,
      grasp_ok: i > 0, images: trainingImages(elapsed_ms), elapsed_ms };
    rounds.push(progress); emit("train_progress", progress);
    });
  });
  // 独立队列项保证同步订阅回调触发急停时，完成与入库一同作废。
  timeline.at(started + values.length * 1200, () => {
    const doc = library.complete(target, draft, rounds, timeline.time());
    emit(`${target}_doc`, doc);
  });
  timeline.at(started + values.length * 1200, () => emit("library", library.snapshot()));
  timeline.at(started + values.length * 1200, () => {
    const doc = draft.id ? library.get(target, draft.id) : (target === "part" ? library.parts : library.recipes).at(-1);
    emit("train_done", { train_id: trainId, doc_id: doc.id });
  });
  emit("train_progress", { train_id: trainId, target, round: 0, deviation_mm: null,
    grasp_ok: null, images: 0, elapsed_ms: 0 });
}
