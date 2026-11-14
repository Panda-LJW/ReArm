import { ARM_PARAMS } from "../../arm/arm-params.js";
import { endPoses } from "../../arm/fk.js";

// 先选限位内的关节角，再正算布置物体；不对目标位置做逆解。单位 rad / m。
// J5/J6 为零时，-J2 + J3 + J4 = π/2 使相机 +X 向下。
const down = (yaw, shoulder, elbow) => [yaw, shoulder, elbow, Math.PI / 2 + shoulder - elbow, 0, 0];
const grasp = yaw => ({ above: down(yaw, -1.75, -0.43), contact: down(yaw, -2.25, -0.45) });
export const POSES = {
  folded: [0, 0, 0, 0, 0, 0],
  observe: down(0, -1.3, -1.2),
  parts: { plate: grasp(-0.45), tube: grasp(0.45), sleeve: grasp(-0.8), block: grasp(0.8) },
  post: grasp(0),
  // 第二层仍先选关节角；FK 对照 5 mm 公差，末端朝向保持向下。
  postStack: { above: down(0, -1.75, -0.43), contact: down(0, -2.13, -0.43) },
};
export const OPEN_MM = ARM_PARAMS.gripper.openingMm[1];
export function tcpPosition(q) {
  const m = endPoses(ARM_PARAMS, q).tcp;
  return [m[3], m[7], m[11]];
}
export function keyPoses() {
  return [POSES.folded, POSES.observe, ...Object.values(POSES.parts).flatMap(p => [p.above, p.contact]),
    POSES.post.above, POSES.post.contact, POSES.postStack.above, POSES.postStack.contact];
}
