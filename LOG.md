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

## 2026-11-13 M8 最终交付 [M8-20261113]
- 目标：固定最终代码、验收证据、已知缺口和可审查的里程碑历史。
- 文件：README.md、PROGRESS.md、LOG.md、LOG-INDEX.md、reports/*；eval_sim.py 仅把缺测 nan 文案改为“未观测”。
- 实测：最终 800 次伤试验耗时 255.27 秒；pytest 39 passed（最终评估内 5.27 秒）；基线 20/20；误报 0；更差采纳 0。
- 诊断：J1 99/100，J2 98/100，底座 x/y 均 100/100，组合 98/100；纯旋转 1/100、延长各 0/100，整体验收未全通过。
- GP：几何 1.5113→GP 0.1444 mm；加配重重训 1.3303→0.1582 mm；回退预测差 0 mm。
- 证据：最终聚合 JSON/逐次 JSONL/pytest JUnit/原始输出/源码 SHA-256；初次和结论修复前的完整报告也保留。协议和 JS 语法验证通过，画面未验证。
- 遗留：物理不可观测/不可辨识导致 5 项整体未达标；原 .git 只读、端口和浏览器环境受限，未绕过。
- 回滚：bundle 包含每个里程碑提交；先 clone 到新的审查目录选择提交，不覆盖本目录用户资料。

## 2026-11-13 M9 面板第二、三批交互与真机准备 [M9-20261113]
- 目标：在 feat/panel-batch1 / f7fc02f 之上完成任务 1–14 的工作区实现，保留第一批功能，不提交、不推送、不切分支。
- 文件：rearm/ui/static/index.html、app.css、app.js；rearm/ui/server.py；rearm/evo/controller.py；rearm/task/shooter.py；rearm/app.py；tests/test_ui_architecture.py、test_panel_frontend_contract.py、test_panel_safety_stream.py；README.md；docs/故障码.md；本日志及索引。
- 前端：按所选版本/head/相关预检/错误缓存对话框，重建保留输入、勾选、焦点、选择区间及滚动；版本列表按列表/head 更新。补齐可达业务错误中文与护栏表同译，动态伤错误和缺字段按模板翻译，未知英文加中文前缀。
- 前端：hash 三页导航、后端 heal_start 计数、断线过期横幅/全部命令禁用/0.5–10 秒指数退避、新快照就绪后恢复、首次状态失败提示；标定/重训/解除急停确认；busy 文案；仿真窗标题拖动及视口限制。
- 无障碍与布局：原生按钮支持 Tab/方向键/Enter/空格，Esc 关闭并还焦点，对话框 Tab 循环，导航 aria-current、菜单 aria-expanded、图表动态摘要。--mute 调为 #8993a2，在 #111418 上对比度 5.94:1；保留桌面网格与 body.short，预留状态条高度；手机顶栏两行、事件列表不限定截断高度。实际画面未验证。
- 安全编排：独立 threading.Event 急停不等待长流程 RLock，短激光写锁避免出光写入越过关断；每发和出光前检查，中止不会被自愈 ValueError 处理吞掉；busy 和 active_command 推送全部客户端。急停期间 6 类操作返回 400，原流程未退出或新急停并发到达时拒绝解除；失败的激光关断不伪报关闭，并保留急停。软件状态字段不代表物理遥测。
- 摄像头与接口：MJPEG multipart 约 5 fps，复用 FastAPI 已有线程池执行读帧，断开时等待当前读帧退出，无独立采集生产者；JPEG 与 MJPEG 串行读共享相机。静态文件 no-cache、resolve 检查目录范围；未增加依赖。状态镜像防止较旧快照覆盖新的急停/激光/操作事件。
- 验证：.venv/bin/python -m pytest -q，57 passed in 6.75s；node --check rearm/ui/static/app.js、git diff --check 通过。Node 独立执行 ERR 模板/未知英文兜底和 hash 路由函数断言通过。新增测试覆盖静态响应头/路径穿越、中文报错集合/护栏同译、hash/ARIA/对比度、自愈中途状态、6 类急停拒绝与恢复、4 类多发中断、3 类关灯异常、解除与新急停竞争、MJPEG 首帧/响应头/断线及读帧中取消清理。
- 未验收：本地 8765 监听被系统拒绝；Playwright 写用户缓存被拒绝；浏览器访问宿主不可用，CUA 使用 Chrome 未获授权。未绕过这些限制；离线夹具仅放 /tmp/rearm-panel-review，未能打开，因此本轮真实浏览器排版、焦点、拖动、重连、390 px 显示和真实相机均未验证。build_app(sim=False) 仍为原有驱动骨架，软件急停没有实体电机制动接口。
- 端口遗留：发现已有 PID 39812 监听 127.0.0.1:8000，lsof 确认 cwd 为本仓库；kill -TERM 被系统以 operation not permitted 拒绝。需用户在原启动终端 Ctrl+C。此次尝试的 8765 服务已因绑定失败退出；没有新启动成功的服务。
- 范围：未改诊断/校准/护栏算法、config/ 阈值、reports/ 或 runtime/；所有仿真测试和浏览器夹具数据写临时目录；未修改 Git 配置或 HEAD。
- 回滚：起点工作区干净，完整原版由 f7fc02f 保留；需要回滚时仅恢复上述本轮文件并移除新增 app.css/app.js 与两个测试文件，保留之后的用户改动。此次没有执行回滚或 Git 写操作。

## 2026-11-13 M10 面板验收后三处小修 [M10-20261113]
- 目标：在当前第二、三批工作区改动上仅修复摄像头失败显示、表格负数格式和 README 验收说明，不提交、不推送、不切分支、不新增依赖。
- 文件：rearm/ui/static/app.js、rearm/ui/static/index.html、README.md、LOG.md、LOG-INDEX.md。
- 摄像头：保留原有连接状态判断，将网络加载与可见图片分开；成功解码的帧经离屏 canvas 保存为本地图片地址，可见 img 不接收失败的网络地址。首次成功前隐藏 img；加载失败保留上次画面；断线取消请求、清理刷新计时器与排队状态，并拒绝旧请求的迟到回调。重连后仿真恢复单帧刷新，非仿真重新连接 MJPEG，以 5 fps 读取已解码帧。
- 数值：版本差异表的当前/目标、预检逐发及中位数复用 signed 的舍入与负号规则，负号统一为 −，舍入后为零统一为 0.00；正值保留不带加号的原样式，变化列仍保留加号。
- 文档：更新 README 三处过时说明，记录验收方确认的 2026-11-13 无头 Chromium 实测：1280×720、1366×768、1440×900、1920×1080 桌面和 390×844 手机视口，键盘操作、焦点保留、hash 路由、确认框、调试窗拖动、急停/解除/流程中急停、MJPEG、断线重连均通过。真实摄像头 MJPEG、真机手机浏览器和真实硬件急停仍未验证；软件急停只关激光并拦截后续动作，不能替代硬件急停。
- 验证：.venv/bin/python -m pytest -q，57 passed in 7.55s；node --check rearm/ui/static/app.js、git diff --check 通过。临时 Node 回归脚本直接执行本轮摄像头函数与对话框渲染函数，覆盖首次失败隐藏、后续失败保帧、断线无请求、排队合并、迟到回调、JPEG/MJPEG 重连、MJPEG 连续帧更新与清理，以及负数、负零、舍入、缺值和两张表实际生成的单元格文本，全部通过；该测试使用图像与 DOM 替身，不等于浏览器画面验证。
- 遗留：本轮 Playwright 启动独立无头 Chrome 时进程以 SIGABRT 退出（清理日志另报 kill EPERM），未获得浏览器画面，未修改系统权限或继续绕过。上述验收方记录不作为这次小修的浏览器复测结果；需复测首次图片失败、成功一帧后断线及 JPEG/MJPEG 重连的实际显示。
- 证据与回滚：修改前 5 个文件已保存至 /private/tmp/rearm-panel-fix-2NyfIX/before/，临时回归脚本为同目录上层 regression.cjs；只恢复此次备份中的对应文件即可退回本轮开始状态，须保留之后的用户改动。未修改其余既有工作区变更。
