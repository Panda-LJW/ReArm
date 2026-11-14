import { POSES, OPEN_MM } from "../fixtures/poses.js";
import { WORKSPACE, recognitionTargets } from "../fixtures/workspace.js";

export const SELF_CHECKS = ["comm", "j1", "j2", "j3", "j4", "j5", "j6", "gripper", "depth_camera"];

export function scheduleProduction({ timeline, emit, recipe, parts, runId, result }) {
  const start = timeline.time(), total = recipe.steps.length;
  const at = (ms, fn) => timeline.at(start + ms, fn);
  const state = (phase, step_index = 0, part_id = null) => emit("run_state", {
    run_id: runId, recipe_id: recipe.id, phase, step_index, step_total: total, part_id,
  });
  const move = (q, gripper_mm, duration) => timeline.move({ q, gripper_mm }, duration);
  at(0, () => state("selfcheck"));
  SELF_CHECKS.forEach((item, i) => at((i + 1) * 300, () => emit("selfcheck_item", { run_id: runId, item, ok: true })));
  at(3000, () => { move(POSES.observe, OPEN_MM, 4000); state("to_observe"); });
  at(7000, () => state("recognize"));
  at(7200, () => emit("recognition", { run_id: runId, image: WORKSPACE.image,
    targets: recognitionTargets(recipe.part_ids) }));
  recipe.steps.forEach((step, i) => {
    const part = parts.find(p => p.id === step.part_id), pick = POSES.parts[part.id] || POSES.parts.block;
    const offset = 9500 + i * 10000, closed = Math.min(OPEN_MM, Math.min(...part.size_mm.slice(0, 2)));
    const report = (action, status) => emit("step_state", { run_id: runId, index: i + 1,
      action, part_id: part.id, status, force_n: part.force_n, ...(action === "pick" ? { angle_deg: 0 } : {}) });
    at(offset, () => { move(pick.above, OPEN_MM, 2000); state("pick", i + 1, part.id); });
    at(offset, () => report("pick", "started"));
    at(offset + 2000, () => move(pick.contact, OPEN_MM, 2000));
    at(offset + 4000, () => move(pick.contact, closed, 500));
    at(offset + 4500, () => { move(pick.above, closed, 500); report("pick", "done"); });
    at(offset + 5000, () => { move(POSES.post.above, closed, 2000); state("place", i + 1, part.id); });
    at(offset + 5000, () => report("place", "started"));
    at(offset + 7000, () => move(POSES.post.contact, closed, 2000));
    at(offset + 9000, () => move(POSES.post.contact, OPEN_MM, 500));
    at(offset + 9500, () => { move(POSES.post.above, OPEN_MM, 500); report("place", "done"); });
  });
  const inspectAt = 9500 + total * 10000;
  at(inspectAt, () => { move(POSES.observe, OPEN_MM, 2000); state("inspect"); });
  at(inspectAt + 3000, () => emit("inspect_result", { run_id: runId, ...result }));
  at(inspectAt + 3000, () => state("done", total));
  at(inspectAt + 3000, () => emit("run_done", { run_id: runId, recipe_id: recipe.id,
    ...result, duration_ms: timeline.time() - start }));
  at(inspectAt + 4500, () => { move(POSES.folded, OPEN_MM, 4000); state("to_fold", total); });
  at(inspectAt + 8500, () => state("idle"));
}
