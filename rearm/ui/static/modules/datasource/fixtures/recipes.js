import { trainingRecord } from "./parts.js";

export const FIXTURE = { id: "disc-fixture", name: "圆盘定位工装", post_id: "post" };
export const RECIPES = [{ id: "plate-tube", name: "薄片 + 空心圆柱配套件", code: "R001",
  fixture_id: FIXTURE.id, fixture_name: FIXTURE.name,
  steps: [{ index: 1, part_id: "plate", target_id: "post", target_name: "定位柱" },
    { index: 2, part_id: "tube", target_id: "post", target_name: "定位柱" }],
  part_ids: ["plate", "tube"],
  training: trainingRecord([5.2, 4.4, 3.6, 2.9, 2.3, 1.8, 1.4, 1.1, 0.6, 0.4]),
  collected_at: 1794614640000, version: 1,
}];
