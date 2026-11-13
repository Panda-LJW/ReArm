# 开发记录

## 2026-11-13 M1 几何与仿真基础 [M1-20261113]
- 目标：建立按接口注入的配置、物理模型和仿真基础。
- 文件：config/*、rearm/types.py、interfaces.py、config.py、model/*、sim/{sim_arm,damage}.py、tests/*。
- 决策：几何返回连续预测供拟合，valid 独立执行向下光线、板界和限位检查；真实参数只存在仿真器中。
- 验证：`.venv/bin/pytest -q`，5 passed（0.49 秒）。
- 遗留：实现后续模块和全部验收；δ1/ψ_b、L2/e 的结构不可辨识性必须如实报告。
- 回滚：回退本里程碑提交；不修改 docs 与用户已有 .codex_prompt.txt。

## 2026-11-13 M2 诊断与持久化 [M2-20261113]
- 目标：实现异常检测、H1–H6 BIC 竞争、多起点 Huber 拟合、整格吸附、主动选姿势、独立留出护栏和持久化。
- 文件：evo/*（controller 除外）、logging/*、task/shooter.py、residual/zero.py、tests/test_evo.py。
- 决策：固定 3 发连续异常防止单发离群误报；无光点不参与几何拟合；版本文件原子写入，拒绝版本不可 checkout。
- 验证：首次发现类方法 list 遮蔽类型注解，启用延迟注解修复；pytest 10 passed（0.53 秒）。
- 遗留：默认 beta=gamma=0 时 e 沿光轴伸长不改变落点，延长伤无法被观测；随后闭环实测。
- 回滚：回退 M2 提交；运行数据单独置于 runtime/。

## 2026-11-13 M3 自愈与残差学习 [M3-20261113]
- 目标：串联自检、旧状态识别、诊断、校准、护栏、版本采纳；补充 GP 和时间留出训练。
- 文件：app.py、evo/controller.py、residual/{gp,dataset,trainer}.py、tests/test_residual_controller.py。
- 决策：诊断期间和报警前首发异常均不用于残差训练；GP 数值 NPZ 可重载，不使用 pickle；不把留出数据再混入已验收模型训练；几何改变后残差归零、旧模型保留。
- 验证：pytest 15 passed（1.61 秒）；J1 新伤通过护栏，复原和重复伤各 3 发识别；GP 时间留出误差下降，保存/加载预测一致。
- 遗留：视觉、面板和全面验收仍在实现。
- 回滚：回退 M3 提交；旧几何/残差可分别 checkout。

## 2026-11-13 M4 视觉与真机边界 [M4-20261113]
- 目标：实现四角 ArUco 单应、相机去畸变、开关帧激光检测、圆靶识别、合成相机与真机骨架。
- 文件：vision/*、sim/sim_camera.py、hw/*、config/camera.yaml、tests/test_vision_hw.py。
- 决策：真实设备协议没有来源，骨架明确抛 NotImplementedError，不发送猜测串口指令；合成透视图可独立检验视觉算法。
- 验证：全套当前 23 passed，其中视觉验证透视点误差 <=0.6 mm、非零畸变点恢复和相机生命周期；真机未联调。
- 遗留：正式 100 次每类验收和浏览器画面检查。
- 回滚：回退 M4 提交。
