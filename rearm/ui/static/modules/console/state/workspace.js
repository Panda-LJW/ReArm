import { WORKSPACE } from "../../datasource/fixtures/workspace.js";

// 固定工位由数据源提供；视图只读取 store 中的快照。
export function initialWorkspace() {
  const workspace = structuredClone(WORKSPACE);
  workspace.bounds = [0, 1].map(axis => {
    const values = workspace.props.map(prop => prop.pose[axis]);
    return [Math.min(...values) - 0.08, Math.max(...values) + 0.08];
  });
  return workspace;
}

export function movePart(workspace, step) {
  if (step.status !== "done") return workspace;
  const post = workspace.props.find(prop => prop.kind === "post");
  if (!post || !["pick", "place"].includes(step.action)) return workspace;
  return { ...workspace, props: workspace.props.map(prop => prop.id !== step.part_id ? prop :
    { ...prop, held: step.action === "pick", pose: step.action === "place" ? [...post.pose] : prop.pose }) };
}

export function workspaceBox(workspace, prop) {
  const scale = [workspace.image.width, workspace.image.height]
    .map((size, axis) => size / (workspace.bounds[axis][1] - workspace.bounds[axis][0]));
  const size = prop.size_m.slice(0, 2).map((v, i) => Math.max(12, v * scale[i]));
  const center = prop.pose.slice(0, 2).map((v, i) => (v - workspace.bounds[i][0]) * scale[i]);
  return [center[0] - size[0] / 2, center[1] - size[1] / 2, ...size];
}
