import { POSES, tcpPosition } from "./poses.js";
import { PARTS } from "./parts.js";
import { FIXTURE } from "./recipes.js";

const post = tcpPosition(POSES.post.contact);
const partProps = PARTS.map(part => ({ id: part.id, kind: "part", name: part.name, shape: part.shape,
  size_m: part.size_mm.map(v => v / 1000), pose: tcpPosition(POSES.parts[part.id].contact), held: false }));
export const WORKSPACE = {
  image: { width: 640, height: 480 },
  table_z_m: post[2] - 0.025,
  props: [{ id: FIXTURE.id, kind: "fixture", name: FIXTURE.name, shape: "disc", size_m: [0.09, 0.09, 0.01],
    pose: [post[0], post[1], post[2] - 0.02], held: false },
  { id: "post", kind: "post", name: "定位柱", shape: "post", size_m: [0.008, 0.008, 0.05],
    pose: [...post], held: false }, ...partProps],
};
// 俯视示意坐标只由 FK 布局求得；框是图像像素，不冒充实物相机标定结果。
const bounds = [0, 1].map(axis => {
  const values = WORKSPACE.props.map(p => p.pose[axis]);
  return [Math.min(...values) - 0.08, Math.max(...values) + 0.08];
});
export function recognitionTargets(partIds) {
  return WORKSPACE.props.filter(p => p.kind !== "part" || partIds.includes(p.id)).map(prop => {
    const scale = [WORKSPACE.image.width, WORKSPACE.image.height].map((n, i) => n / (bounds[i][1] - bounds[i][0]));
    const center = prop.pose.slice(0, 2).map((v, i) => (v - bounds[i][0]) * scale[i]);
    const size = prop.size_m.slice(0, 2).map((v, i) => Math.max(12, v * scale[i]));
    return { id: prop.id, kind: prop.kind, name: prop.name, confidence: 0.97,
      box_px: [center[0] - size[0] / 2, center[1] - size[1] / 2, ...size],
      angle_deg: prop.kind === "part" ? 0 : null };
  });
}
