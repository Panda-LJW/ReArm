// 状态文案唯一来源；这里只映射词语，不归并业务状态。
export const WORDS = Object.freeze({
  idle: "待命", selfcheck: "自检中", to_observe: "就绪", recognize: "识别中",
  pick: "抓取中", place: "放置中", inspect: "检查中", done: "完成",
  to_fold: "完成", estop: "急停", training: "训练中",
});
