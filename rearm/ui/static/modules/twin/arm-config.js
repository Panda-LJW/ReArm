// 机械臂数字孪生的全部几何与映射参数。只有数据，没有逻辑；换臂或实测后只改这个文件。
//
// 来源：Seeed reBot Arm B601-DM 的公开 URDF（box2ai-robotics/rebot-joycon 快照 dd97975，
// URDF/reBot_B601_DM/ReBot_Arm_DM.urdf）。连杆原点、转轴、限位均为官方设计值，
// 尚未在实物上逐项测量。标了「占位」的条目是本项目自行假设的，接真机前必须核对。
export const ARM_CONFIG = {
  name: "reBot Arm B601-DM",
  source: "URDF ReBot_Arm_DM.urdf @ rebot-joycon dd97975（官方设计值，未实测）",
  units: { length: "m", angle: "rad" },
  // URDF 关节链，自底座向末端。origin 是相对父连杆的固定变换，axis 是关节自身坐标系下的转轴。
  joints: [
    { id: "joint1", label: "J1 底座", type: "revolute", xyz: [-0.00008416, 0, 0.08465], rpy: [0, 0, 0], axis: [0, 0, 1], limit: [-2.8, 2.8] },
    { id: "joint2", label: "J2 大臂", type: "revolute", xyz: [0.020084, 0.031625, 0.05555], rpy: [-1.5708, 0, 0], axis: [0, 0, -1], limit: [-3.14, 0] },
    { id: "joint3", label: "J3 小臂", type: "revolute", xyz: [-0.264, 0, 0], rpy: [0, 0, 0], axis: [0, 0, 1], limit: [-3.14, 0] },
    { id: "joint4", label: "J4 腕俯仰", type: "revolute", xyz: [0.2426, -0.054, -0.001625], rpy: [0, 0, 0], axis: [0, 0, 1], limit: [-1.87, 1.57] },
    { id: "joint5", label: "J5 腕偏摆", type: "revolute", xyz: [0.078308, -0.0375, -0.03], rpy: [-1.5708, 0, 0], axis: [0, 0, 1], limit: [-1.57, 1.57] },
    { id: "joint6", label: "J6 腕旋转", type: "revolute", xyz: [0.028008, 0, 0.04], rpy: [0, 1.5708, 0], axis: [0, 0, 1], limit: [-3.14, 3.14] },
  ],
  // 末端（夹爪基座）相对 joint6 的固定变换；夹指为对向齿条，行程 0–28.5 mm。
  tool: { xyz: [0, 0, 0.15539], rpy: [0, -1.5708, 3.1415], fingerTravel: 0.0285 },
  // 外形尺寸（m）：只用于画简化外形，不参与运动学。占位：取自官方网格各连杆的包围盒，
  // 板厚、电机外径等细节是估计值，待用 STEP 实测替换。
  shape: {
    basePlate: [0.14, 0.20, 0.008], baseRadius: 0.046, baseHeight: 0.0846,
    motorRadiusLarge: 0.034, motorRadiusSmall: 0.028, plateThickness: 0.004,
    upperArm: { width: 0.056, zNear: 0.0, zFar: -0.063 },
    foreArm: { width: 0.050, zNear: 0.005, zFar: -0.067 },
    gripperRail: { center: [-0.088, 0, 0], size: [0.030, 0.184, 0.040] },
    finger: { length: 0.065, thickness: 0.012, height: 0.040, opening: 0.030 },
  },
  // 画面布置（m）。占位：仿真用的名义臂比 B601-DM 小，部分仿真姿态下末端会低于底座平面，
  // 所以把臂画在一个安装台上；真机安装方式确定后改成实际高度（落地安装填 0）。
  scene: { pedestalHeight: 0.20, cameraTarget: [0.17, 0, 0.06], cameraDistance: 2.0, cameraAzimuthDeg: -62, cameraElevationDeg: 16 },
  // 上位机关节读数（度）→ URDF 关节角（弧度）的映射：q_urdf = sign * deg2rad(q_panel) + offset。
  // 上位机约定：J1 偏航，0° 正对靶板；J2 大臂仰角，0° 水平、90° 竖直；J3 小臂相对大臂的夹角，负值为向下折。
  // 占位：offset/sign 是按 URDF 零位姿态数值求出的（见 tests/test_twin_modules.py 的核对），
  // 真机零位以实测为准，待下位机联调时替换。
  panelMapping: [
    { joint: "joint1", sign: -1, offset: 0 },
    { joint: "joint2", sign: 1, offset: -3.141592653589793 },
    { joint: "joint3", sign: -1, offset: -2.922574576194731 },
  ],
  // 上位机暂不驱动的关节固定在这个姿态（弧度）。占位：激光头朝向沿小臂延长线。
  restPose: { joint4: -0.2278, joint5: 0, joint6: 0 },
};
