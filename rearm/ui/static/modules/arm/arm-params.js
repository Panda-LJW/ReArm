// 机械臂的唯一几何与映射参数来源。只有数据，没有逻辑；换臂或实测后只改这个文件。
//
// 来源：Seeed reBot Arm B601-DM 的公开 URDF（box2ai-robotics/rebot-joycon 快照 dd97975，
// URDF/reBot_B601_DM/ReBot_Arm_DM.urdf）。连杆原点、转轴为官方设计值；
// 关节限位与夹爪行程采用真机后端 lizuyi-6/ReArm @ 245491f（2026-11-15）。
// 名义夹头、夹指截面和相机安装分别来自该后端 pick.frames、gripper.json、handeye_camera.json。
// 尚未在实物上逐项测量。标了「占位」的条目是本项目自行假设的，接真机前必须核对。
// X 为接近方向，Y 为闭合方向，Z 为手指厚度方向。长度待尺量；Y 外宽沿用 STEP 25 mm。
const FINGER = {
  length: 0.065, width: 0.025, thickness: 0.040, opening: 0.030,
  // 后端 gripper.json 的深/口宽为两位小数；几何按边长和夹角构造，避免舍入破坏 90°。
  vGroove: { side: 0.015, angleDeg: 90, depth: 0.01061, mouth: 0.02121, flat: 0 },
};

export const ARM_PARAMS = {
  name: "reBot Arm B601-DM",
  source: "URDF @ rebot-joycon dd97975；限位/夹爪/手眼 @ ReArm 245491f（名义模型）",
  units: { length: "m", angle: "rad" },
  // URDF 关节链，自底座向末端。origin 是相对父连杆的固定变换，axis 是关节自身坐标系下的转轴。
  joints: [
    { id: "joint1", label: "J1 底座", type: "revolute", xyz: [-0.00008416, 0, 0.08465], rpy: [0, 0, 0], axis: [0, 0, 1], limit: [-2.8, 2.8] },
    { id: "joint2", label: "J2 大臂", type: "revolute", xyz: [0.020084, 0.031625, 0.05555], rpy: [-1.5708, 0, 0], axis: [0, 0, -1], limit: [-3.14, 0.3] },
    { id: "joint3", label: "J3 小臂", type: "revolute", xyz: [-0.264, 0, 0], rpy: [0, 0, 0], axis: [0, 0, 1], limit: [-3.14, 0.05] },
    { id: "joint4", label: "J4 腕俯仰", type: "revolute", xyz: [0.2426, -0.054, -0.001625], rpy: [0, 0, 0], axis: [0, 0, 1], limit: [-1.87, 1.95] },
    { id: "joint5", label: "J5 腕偏摆", type: "revolute", xyz: [0.078308, -0.0375, -0.03], rpy: [-1.5708, 0, 0], axis: [0, 0, 1], limit: [-1.57, 1.57] },
    { id: "joint6", label: "J6 腕旋转", type: "revolute", xyz: [0.028008, 0, 0.04], rpy: [0, 1.5708, 0], axis: [0, 0, 1], limit: [-3.14, 3.14] },
  ],
  // 末端（夹爪基座）相对 joint6 的固定变换；两指沿平行导轨对向滑动。
  end_link: { xyz: [0, 0, 0.15539], rpy: [0, -1.5708, 3.1415] },
  // 真机 config/gripper.json max_open_mm=110：单指行程 0–55 mm；安装原点、旋转均为 0。
  // 右指 URDF 用 +Y 轴、负行程；这里等价表示为 -Y 轴、正行程。
  gripper: {
    fingerTravel: [0, 0.055], openingMm: [0, 110],
    fingers: [
      { side: "left", xyz: [0, 0, 0], rpy: [0, 0, 0], axis: [0, 1, 0] },
      { side: "right", xyz: [0, 0, 0], rpy: [0, 0, 0], axis: [0, -1, 0] },
    ],
    finger: FINGER,
    // STEP 实体包围盒为 25×40×65.5 mm；全部参考点的 49×80×67 mm 不是实体尺寸。
    fingerLength: 0.0655,
    customFinger: {
      // p_end = Rz(yaw) Ry(pitch) Rx(roll) · (p_STEP / 1000) + xyz。
      // STEP +Z → end +X（伸出），+X → +Y（横向），+Y → +Z（高度）。
      mount: { xyz: [-0.065, 0.0125, 0], rpy: [1.5707963267948966, 0, 1.5707963267948966] },
      // 先安装左指，再绕 end_link X 轴翻转整个零件得到右指；网格中已烘焙此变换。
      flipRpy: [3.141592653589793, 0, 0],
      tipX: 0.0005,
      note: "照片估算：STEP Z=0 的四孔根面贴滑块前端 X=-65 mm；Z=65.5 mm 为指尖。左指内侧贴 Y=0，右指绕伸出轴翻转 180°；安装位置待实测。",
    },
  },
  // pick.frames() 的名义夹头 = base·DH1..6·TOOL_DH，与 end_link 完整位姿一致。
  // TABLE_TIP_Z_MM=3.6 是碰桌时此点的基座 Z，不是局部 TCP 偏移；kin6 的 tool_x=-105 不是夹头。
  T_end_tcp: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
  // config/handeye_camera.json T_tip_cam（mm→m）。渲染相机：X 前、Y 左、Z 上；
  // OpenCV：x 右、y 下、z 前。T_end_camera = T_tip_cam · R_cv_render，
  // R_cv_render 的列为 [cv +Z, cv -X, cv -Y]，保持右手系与 +X 视锥。
  T_end_camera: [
    0.939991, -0.001543, 0.341197, -0.068814228,
    0.002923, 0.999989, -0.003530, 0.036191124,
    -0.341188, 0.004316, 0.939985, 0.055202707,
    0, 0, 0, 1,
  ],
  camera: {
    // 照片估算外形 90×25×25 mm；size 按局部 X（深）、Y（宽）、Z（高）排列。
    size: [0.025, 0.090, 0.025],
    // 真机彩色流 640×480 内参（fx 605.07、fy 604.63，后端零件采集参数）换算的视场角；相机 +X 为光轴。
    horizontalFovDeg: 55.75, verticalFovDeg: 43.3,
  },
  // 外形尺寸（m）：只用于画简化外形，不参与运动学。占位：取自官方网格各连杆的包围盒，
  // 板厚、电机外径等细节是估计值，待用 STEP 实测替换。
  shape: {
    basePlate: [0.14, 0.20, 0.008], baseRadius: 0.046, baseHeight: 0.0846,
    motorRadiusLarge: 0.034, motorRadiusSmall: 0.028, plateThickness: 0.004,
    upperArm: { width: 0.056, zNear: 0.0, zFar: -0.063 },
    foreArm: { width: 0.050, zNear: 0.005, zFar: -0.067 },
    // 旧 57 mm 网格的端挡在 ±85.2 mm，全开 110 mm 时滑块/限位块伸至 89.5 mm，会穿模。
    // 导轨显示长度两侧各补 (110-57)/2=26.5 mm，给端挡留出余量；仅外形近似，待实测。
    gripperRail: { center: [-0.088, 0, 0], size: [0.030, 0.237, 0.040] },
    finger: FINGER,
  },
  // 画面布置（m）：不显示安装台，地面网格与机械臂底座同在 base_link 的 Z=0。
  scene: { pedestalHeight: 0, cameraTarget: [0.06, 0, 0.18], cameraDistance: 1.45, cameraAzimuthDeg: -62, cameraElevationDeg: 16 },
  // 上位机关节读数（度）→ URDF 关节角（弧度）的映射：q_urdf = sign * deg2rad(q_panel) + offset。
  // 上位机约定：J1 偏航，0° 正对靶板；J2 大臂仰角，0° 水平、90° 竖直；J3 小臂相对大臂的夹角，负值为向下折。
  // 占位：offset/sign 是按 URDF 零位姿态数值求出的（见 tests/test_twin_modules.py 的核对），
  // 真机零位以实测为准，待下位机联调时替换。
  legacyPanelMapping: [
    { joint: "joint1", sign: -1, offset: 0 },
    { joint: "joint2", sign: 1, offset: -3.141592653589793 },
    { joint: "joint3", sign: -1, offset: -2.922574576194731 },
  ],
  // 上位机暂不驱动的关节固定在这个姿态（弧度）。
  legacyRestPose: { joint4: -0.2278, joint5: 0, joint6: 0 },
};

export const legacyPanelMapping = ARM_PARAMS.legacyPanelMapping;
export const legacyRestPose = ARM_PARAMS.legacyRestPose;
