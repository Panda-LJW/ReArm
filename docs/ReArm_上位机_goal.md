# Goal：日新臂 ReArm 上位机 v0（仿真可跑通的第一版）

## 1. 目标

实现一台 3 自由度激光打靶机械臂的上位机。它维护一个"自我模型"，用俯拍摄像头量到的激光落点持续检验这个模型，模型过时就自己更新，并把每次更新存成可回退的版本。

**v0 的完成标准：不接任何硬件，在仿真器里完整跑通全部流程，并通过第 7 节的验收。** 真机驱动只需留好接口和骨架。

## 2. 硬性要求

- Python 3.11；依赖限 numpy、scipy、scikit-learn、opencv-contrib-python、pyserial、fastapi、uvicorn、pydantic、pyyaml、pytest。
- 全部本地运行，不联网，不调用任何大模型接口。
- **模块化是第一优先级**（后续会逐个模块拆改）：
  - 所有跨模块的数据结构只定义在 `rearm/types.py`，所有可替换部件只通过 `rearm/interfaces.py` 里的 Protocol 交互。
  - 模块之间不互相 import 实现，只依赖 types 和 interfaces；只有 `evo/controller.py` 和 `app.py` 负责组装。
  - 不用全局变量和单例；配置从 YAML 读入后通过构造函数注入；所有阈值都在配置里，代码中不写魔法数字。
  - 算法模块是纯函数或无副作用的类，不直接读写硬件、文件、界面。
  - 界面只订阅事件总线，不被算法模块调用。
- 每个模块有对应的 pytest 单元测试，测试只用仿真器，随机数固定种子。
- 做不到或没验证的地方在 README 的"已知缺口"里如实写明，不要用假数据或写死的结果让验收通过。

## 3. 物理与几何模型

坐标系：靶板坐标系 {B}，原点在 A3 靶板（420 × 297 mm）中心，x 沿长边向右，y 由机械臂一侧指向远端，z 向上，靶面 z = 0。机械臂底座名义位置 (x_b, y_b) = (0, -208.5) mm，J1 = 0 时指向 +y。

舵机读数 q1, q2, q3（度），实际关节角 θ_i = q_i + δ_i，偏航 φ = θ1 + ψ_b。

```
r_o = L1·cos(θ2) + (L2 + e)·cos(θ2 + θ3)        # 出光点到 J1 轴的水平距离
z_o = h  + L1·sin(θ2) + (L2 + e)·sin(θ2 + θ3)   # 出光点高度
光轴俯仰 α = θ2 + θ3 + β，另有离开竖直平面的小偏角 γ
落点 = 从出光点沿光轴的射线与 z = 0 的交点
```

只有光轴朝下（方向向量 z 分量 ≤ -0.3）且落点在靶板内的姿势才有效。

几何参数与名义值（存 `config/arm_nominal.yaml`）：

| 参数 | 含义 | 名义值 | 范围 |
|---|---|---|---|
| δ1, δ2 | J1、J2 零点偏移 | 0° | ±30° |
| δ3 | J3 零点偏移 | 0° | ±10° |
| h | J2 轴到靶面高度 | 85 mm | ±10 mm |
| L1 | 大臂 | 150 mm | ±5 mm |
| L2 | 小臂到出光点 | 130 mm | ±5 mm（基线后固定） |
| e | 末端延长 | 0 mm | 0–60 mm |
| β, γ | 激光安装偏差 | 0° | ±5° |
| x_b, y_b | 底座位置 | 见上 | ±30 mm |
| ψ_b | 底座朝向 | 0° | ±15° |

关节限位：J1 ±90°，J2 0–110°，J3 -150–0°。

## 4. 自我模型与更新逻辑

```
预测落点 = 几何模型(params, q) + 残差模型(q, 接近方向, 负载, 温度)
```

- **几何模型**：第 3 节的公式。
- **残差模型**：可替换（Protocol）。v0 提供两个实现：`ZeroResidual`（恒为 0）和 `GPResidual`（scikit-learn 高斯过程，输出修正量和不确定度）。修正量有上限（配置项，默认 5 mm），超出则截断。

每打一发得到残差 = 实测落点 − 预测落点。状态机：

1. **正常**：按当前版本打靶。
2. **发现异常**：连续 N 发残差中位数超阈值（默认 3 发、6 mm）。单发离群直接丢弃。
3. **认旧状态**：用 3 个固定探测姿势打靶，与版本库中每个已采纳版本的预测比较；最小均方根残差 < 3 mm 且不到第二名的一半，则直接切换到该版本。
4. **诊断**：否则对下列假设分别拟合（只放开对应参数，其余固定），用 BIC 选择：H1 δ1；H2 δ2；H3 e；H4 x_b, y_b, ψ_b；H5 以上任意两组；H6 全部参数。下一发的姿势从候选姿势池中选"排名前两位的假设预测落点相距最远"的那个。δ 的拟合值距 15° 整数倍不到 2° 时吸附到整格再精修。大角度偏移用 0°、±15°、±30° 多起点拟合。
5. **校准**：`scipy.optimize.least_squares`，Huber 损失，带参数边界，带向当前版本的正则项。
6. **护栏**：在 4 个未参与拟合的姿势上验证。通过条件：残差中位数 ≤ 3 mm、比旧版本下降 ≥ 70%、参数都在范围内。通过则存为新版本并启用，否则记为"已拒绝"并保留旧版本。
7. **重训残差模型**（手动或定时触发）：用累积日志训练，按时间留出最近一段数据做检验；留出误差比当前残差模型更低才上线，否则保留旧的。

固定顺序：先认旧状态，再几何诊断，最后才是残差模型。残差模型的训练数据不包含异常期间的数据。

## 5. 目录与模块

```
rearm/
  config/            arm_nominal.yaml  thresholds.yaml  camera.yaml  sim.yaml
  rearm/
    types.py         Params, Shot, Pose, Diagnosis, GuardReport, Version, Event
    interfaces.py    ArmIO, ResidualModel, VersionStore, EventBus (Protocol)
    config.py        读取并校验配置
    hw/              servo.py  laser.py  real_arm.py      # 真机 ArmIO，v0 只需骨架
    vision/          camera.py  board.py  laser_spot.py  targets.py  undistort.py
    model/           kinematics.py  ik.py  self_model.py  pose_pool.py
    residual/        zero.py  gp.py  dataset.py  trainer.py
    evo/             detector.py  recognizer.py  diagnoser.py  calibrator.py
                     guard.py  versions.py  controller.py
    task/            shooter.py
    sim/             sim_arm.py  damage.py  sim_camera.py
    logging/         shot_log.py  event_log.py  bus.py
    ui/              server.py  static/
  scripts/           demo.py  eval_sim.py  build_pose_pool.py  collect.py  train_residual.py
  tests/
  README.md
```

关键接口（签名可微调，但必须集中在 interfaces.py）：

```python
class ArmIO(Protocol):
    def move_to(self, q: np.ndarray, speed: float) -> None: ...
    def read_state(self) -> ArmState: ...          # 角度、负载、温度、电压
    def laser(self, on: bool) -> None: ...
    def observe_spot(self) -> np.ndarray | None: ...   # 靶面坐标 mm；无效返回 None

class ResidualModel(Protocol):
    def predict(self, feats: np.ndarray) -> tuple[np.ndarray, np.ndarray]: ...  # 修正量, 不确定度
    def fit(self, feats: np.ndarray, targets: np.ndarray) -> None: ...
    def save(self, path) -> None: ...
    def load(self, path) -> None: ...

class VersionStore(Protocol):
    def commit(self, params, residual_id, meta) -> str: ...
    def reject(self, params, meta, reasons) -> str: ...
    def checkout(self, version_id) -> Version: ...
    def match(self, probe: list[Shot]) -> tuple[str, float] | None: ...
    def head(self) -> Version: ...
```

各模块要点：

- **sim**：实现 ArmIO。内部有一套"真实参数"，并模拟几何公式之外的误差，使残差模型有东西可学：与接近方向有关的齿隙、与伸出距离和负载有关的下垂、随运行时间上升的温度漂移、落点测量噪声。全部可在 `sim.yaml` 配置和关闭。`damage.py` 提供伤注入：J1/J2 分度盘错位 n×15°、延长杆 +20/+40 mm、底座平移 20 mm 或旋转 10°、任意组合，以及"加配重""松动"这类只改变非几何误差的变化。
- **vision**：ArUco（DICT_4X4_50）四角定位求单应矩阵、相机去畸变、激光开关两帧相减加亚像素质心、圆贴纸靶点识别。用 `sim_camera.py` 生成的合成图像做单元测试。
- **model**：正运动学、落点、解析或数值雅可比、数值反解（带限位）、姿势池生成（过滤无效姿势，可算雅可比条件数）。
- **logging**：每一发写一行 JSONL（时间、q、接近方向、负载、温度、电压、预测、实测、残差、当前版本号、是否处于异常期）；事件日志记录报警、诊断、校准、切换、回退、拒绝、重训。
- **versions**：`versions/vNNNN.json` 加 HEAD 指针；几何参数和残差模型各有版本号，可分别回退；回退本身记一条事件。
- **ui**：FastAPI + WebSocket，单页原生 HTML/JS。v0 只要：当前状态、最近残差曲线、诊断结论与各假设得分、版本列表（可点回退）、"版本—留出误差"曲线（含"只用几何"对照线）、按钮（自检、重训、回退、注入伤（仅仿真））。

## 6. 命令

```
python scripts/build_pose_pool.py            # 生成候选姿势池
python scripts/demo.py --sim                 # 基线→受伤→自愈→复原→再受伤→秒愈，终端打印时间线
python scripts/collect.py --sim --shots 300  # 自动采集
python scripts/train_residual.py             # 重训并过护栏
python scripts/eval_sim.py                   # 跑第 7 节的全部验收并输出报告
python -m rearm.ui.server --sim              # 启动面板
pytest
```

## 7. 验收（全部在仿真中，由 eval_sim.py 输出实测数字）

| 项 | 标准 |
|---|---|
| 基线 | 全参数校准后，20 个随机靶点命中率 ≥ 95%（命中 = 落点距靶心 ≤ 10 mm） |
| 误报 | 无伤连续 100 发，报警 0 次 |
| 发现 | 每类伤各 100 次，≤ 3 发内报警 |
| 诊断 | 每类单一伤各 100 次，伤的类型和格数都对的比例 ≥ 95% |
| 新伤恢复 | 从报警到采纳新版本 ≤ 20 发，恢复后留出残差中位数 ≤ 3 mm |
| 旧伤恢复 | 同一种伤第二次出现，只用 3 发探测即切换到对应版本 |
| 伤愈识别 | 伤复原后自动切回初始版本 |
| 护栏 | 全部测试中，采纳了比旧版本更差的版本的次数 = 0 |
| 菜单外的伤 | 注入无法解释的变化时，系统拒绝候选版本并保留原版本 |
| 残差模型 | 打开仿真的非几何误差后，"几何 + GP"在按时间留出的数据上的中位误差低于"只用几何"；注入"加配重"后重训一轮，误差再次下降 |
| 回退 | 回退到任意已采纳版本后，预测与当时一致 |
| 测试 | pytest 全部通过 |

达不到的项不要调松标准，在报告和 README 中如实列出数字和原因。

## 8. 不在 v0 范围

- 真机联调（`hw/` 只留骨架和 TODO，接口与仿真一致）。
- 漂移的自动检测与自动触发重训（v0 手动或定时触发）。
- 按不确定度归一化的自适应阈值（v0 用固定阈值，但 GP 的不确定度要照常输出并记录）。
- 无标记视觉跟踪、大模型相关功能。

## 9. 交付

代码、测试、`eval_sim.py` 的一份实测报告，以及 README：如何运行、模块关系图（文字即可）、每个模块的职责与可替换点、已知缺口。
