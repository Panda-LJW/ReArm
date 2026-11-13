# 外形文件的来源与许可

`b601.json`、`b601.bin` 是 **Seeed reBot Arm B601-DM** 公开网格的压缩版本，只用于本面板的数字孪生显示。

- 原始设计：Seeed Studio，reBot-DevArm 硬件库，许可证 **CERN-OHL-W-2.0**
  （https://github.com/Seeed-Projects/reBot-DevArm ，快照 `198e5a3`）
- 网格取自：box2ai-robotics/rebot-joycon（MIT，模型部分保留原许可证），快照 `dd97975`，
  `URDF/reBot_B601_DM/meshes/colored_*.stl`
- 本仓库所做的修改：用 `scripts/build_twin_meshes.py` 做顶点聚类（格长 2.5 mm），
  三角面由 430,912 减到 64,794；各零件仍在原连杆坐标系下，未改尺寸。
- 与实物的已知差异：官方为尖头夹指，实物照片为白色矩形镂空夹指；配色按面板主题做了中性化处理。

CERN-OHL-W-2.0 要求分发修改版时保留许可证与来源声明，并说明所做修改；本文件即为该声明。
如果仓库要对外公开或随产品分发，请先确认是否接受这一许可证；不接受时删除本目录即可，
孪生会自动退回到用 `arm-config.js` 尺寸画的简化外形。
