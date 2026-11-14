// 旧孪生配置的兼容出口；全部参数只在 ../arm/arm-params.js 维护。
// 来源：ReBot_Arm_DM.urdf。关节链直接共享对象，tool 保留旧字段 fingerTravel。
// 占位：简化外形尺寸，沿用原显示。
// 占位：安装台高度，只参与画面布置。
// 占位：旧面板 sign/offset，待真机校零。
// 占位：旧三轴未驱动的腕部姿态，沿用原映射。
import { ARM_PARAMS } from "../arm/arm-params.js";

export const ARM_CONFIG = {
  ...ARM_PARAMS,
  tool: { ...ARM_PARAMS.end_link, fingerTravel: ARM_PARAMS.gripper.fingerTravel[1] },
  panelMapping: ARM_PARAMS.legacyPanelMapping,
  restPose: ARM_PARAMS.legacyRestPose,
};
