import { PARTS, CAPTURE, forceBasis, trainingRecord } from "../fixtures/parts.js";
import { RECIPES, FIXTURE } from "../fixtures/recipes.js";

export const clone = value => structuredClone(value);
export function createLibrary() {
  const parts = clone(PARTS), recipes = clone(RECIPES);
  const list = target => target === "part" ? parts : recipes;
  const summary = doc => Object.fromEntries(["id", "name", "code", "shape", "size_mm", "collected_at", "version"]
    .filter(key => doc[key] !== undefined).map(key => [key, doc[key]]));
  return {
    parts, recipes,
    snapshot: () => ({ parts: parts.map(summary), recipes: recipes.map(summary) }),
    get: (target, id) => list(target).find(d => d.id === id),
    candidate: () => ({ ...clone(CAPTURE), code: `P${String(parts.length + 1).padStart(3, "0")}` }),
    validate(target, draft) {
      if (!["part", "recipe"].includes(target) || !draft || typeof draft !== "object") return false;
      const existing = draft.id && list(target).find(d => d.id === draft.id);
      if (draft.id && !existing) return false;
      if (existing) return true;
      if (typeof draft.name !== "string" || !draft.name.trim() || typeof draft.code !== "string" || !draft.code.trim()) return false;
      if (list(target).some(d => d.code === draft.code.trim())) return false;
      if (target === "part") return Array.isArray(draft.size_mm) && draft.size_mm.length === 3 &&
        draft.size_mm.every(v => Number.isFinite(v) && v > 0) && Array.isArray(draft.outline) && draft.outline.length >= 3 &&
        draft.outline.every(p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite));
      return draft.fixture_id === FIXTURE.id && Array.isArray(draft.steps) && draft.steps.length > 0 &&
        draft.steps.every(s => s && parts.some(p => p.id === s.part_id) && s.target_id === "post");
    },
    complete(target, draft, rounds, t) {
      const docs = list(target), old = docs.find(d => d.id === draft.id);
      // 明确字段构建文档，识别角度、运行轨迹和任意外来字段不进入文档。
      const doc = old ? clone(old) : { id: `${target}-${docs.length + 1}`, name: draft.name.trim(), code: draft.code.trim() };
      if (!old && target === "part") Object.assign(doc, {
        shape: "ring", size_mm: clone(draft.size_mm), outline: clone(draft.outline), photo_url: null,
        force_n: 12, force_basis: forceBasis(12), opening: "full",
      });
      if (!old && target === "recipe") Object.assign(doc, { fixture_id: FIXTURE.id, fixture_name: FIXTURE.name,
        steps: draft.steps.map((s, i) => ({ index: i + 1, part_id: s.part_id, target_id: "post", target_name: "定位柱" })),
        part_ids: [...new Set(draft.steps.map(s => s.part_id))] });
      doc.training = trainingRecord(rounds.map(r => r.deviation_mm), { t });
      doc.collected_at = t; doc.version = (old?.version || 0) + 1;
      if (old) docs[docs.indexOf(old)] = doc; else docs.push(doc);
      return clone(doc);
    },
  };
}
