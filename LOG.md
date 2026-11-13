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

## 2026-11-13 M5 面板、命令与验收器 [M5-20261113]
- 目标：完成 FastAPI/WebSocket 原生单页面板、五个 CLI、固定种子全量评估与证据输出。
- 文件：ui/*、scripts/*、app.py、tests/test_ui_architecture.py、tests/test_config_contracts.py、配置校验与阈值。
- 决策：UI 订阅事件更新，动作通过 Protocol 入口；关闭远程 CDN 文档页；eval 的未报警样本保留在分母，失败返回 1；审计姿势独立于拟合和四发护栏。
- 验证：HTTP 和 WebSocket ASGI 测试通过；CLI 姿势池生成 240+84 个姿势，demo 恢复发数 14/3/3；采集 300 发报警 0 次，GP 留出 1.4635→0.1535 mm（该 CLI 运行）。
- 排障：ASGI 测试接收器在旧 spec 分支忙循环，修为准确声明 spec 2.4；正式服务代码未需绕过。
- 环境限制：127.0.0.1:8000 监听被 sandbox 拒绝；CUA 返回 browser access host unavailable。已保存实测状态和离线预览 HTML，但画面未验证，不宣称浏览器联调完成。
- 遗留：正式每类 100 次评估、README 和最终审查。
- 回滚：回退 M5 提交；保留 M1–M4 与用户 docs。

## 2026-11-13 M6 诊断统计修正与验收复跑 [M6-20261113]
- 目标：核查首轮完整验收中 J1 诊断 94/100 的真实失败，保留首轮证据。
- 文件：diagnoser.py、thresholds.yaml、config.py、tests/test_evo.py、tests/test_residual_controller.py、README.md、reports/initial_evaluation/*。
- 根因与决策：连续参数 BIC 不应对部分假设预先量化；统一使用传感器测量方差的已知方差高斯 BIC（SSE/sigma²+k log n），sigma=0.12 mm 与配置测量标准差相同。20 发预算内增加初始诊断信息，不更改任何验收界限；基线靶点扩大到整个 A3 靶面，无边缘排除。
- 验证：首轮 800 次完整结果保存在 initial_evaluation/；连续 BIC 单独复测 J1 91/100，扩充观测后 93/100，未冒充达标。共享测量方差在同一批留存观测上回算 95/100，最终端到端全量正在重跑，以其结果为准。
- 遗留：物理不可观测/不可辨识部分仍须如实披露；浏览器画面仍未验证。
- 回滚：M5 为首轮实现回滚点；M6 保留原实测证据和诊断实验记录。

## 2026-11-13 M7 诊断结论与候选模型分离 [M7-20261113]
- 目标：修复 BIC 选择的“允许变化组”被直接误报成物理伤类型的问题。
- 文件：types.py、diagnoser.py、controller.py、ui/static/index.html、eval_sim.py、tests/test_evo.py、README.md。
- 根因：例如 H5 放开 J1/J2，但整格精修后 J1 恢复为 0、J2=-30°，旧诊断仍显示 H5。现在 Diagnosis 分别保存连续 BIC 排名、精修提案和实际变化组；只删除回到参考值的组（数值 epsilon），不按伤幅度加白名单或放松验收。
- 验证：pytest 39 passed（4.50 秒），含真实仿真种子下 H5→J2 结论回归测试；前轮完整报告保存在 pre_conclusion_fix/；新评估同时输出“类型格数”和“BIC 模型名匹配”，不隐藏前者与后者的差别。
- 遗留：最终 800 次完整复跑进行中；物理不可观测/不可辨识和环境限制仍如实保留。
- 回滚：回退 M7 恢复原诊断数据结构与名称显示；历史版本文件为 JSON，原字段保留，新字段仅追加在诊断元数据中。
