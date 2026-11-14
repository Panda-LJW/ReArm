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

## 2026-11-14 T1 机械臂参数单一来源与六轴入口 [T1-20261114]
- 目标：按 docs/model-swap/设计.md 第 2、3 节接入独立六轴 URDF FK、原始轨迹换算和孪生显示，保留旧三轴映射。
- 新增：rearm/ui/static/modules/arm/arm-params.js、fk.js、trajectory.js；tests/test_arm_kinematics.py。
- 修改：rearm/ui/static/modules/twin/arm-config.js、kinematics.js、twin.js、scene.js、fallback2d.js、demo.html；modules/datasource/frame.js；tests/test_twin_modules.py；LOG.md、LOG-INDEX.md。
- 参数：关节原点、转轴、限位和旧映射逐值沿用原 arm-config；ARM_CONFIG.joints 与 ARM_PARAMS.joints 共享对象。end_link 保留原 tool 固定变换，旧 forward 的 tool 与 end_link 指向同一矩阵。夹指单指行程 0–28.5 mm、总开口 0–57 mm，安装原点/旋转为零，沿末端局部 ±Y 对称平移；右指把 URDF 的 +Y 负行程等价写成 -Y 正行程。URDF 证据为现存本地调研快照 /private/tmp/b601-fk-20261114-hhjjxts6/rebot-joycon/URDF/reBot_B601_DM/urdf/ReBot_Arm_DM.urdf 的 finger_left/finger_right。
- 外参：T_end_tcp 为单位阵并注明待实测；自制夹指 +X 长度暂估 80 mm，相机位于局部 (10,0,40) mm、激光 (10,0,20) mm，二者 +X 为光轴/光束。Node 实算中间姿态 [0,-1.57,-1.57,0,0,0]：end_link +Z 在基座系为 [-0.000007346410191,0.000099999999832,0.999999994973]，抬高 40 mm 对应基座 Z 增加 39.999999799 mm。外形和 D435 标称视场角均标注估算/型号待确认。
- 数据：JointFrame 总是包含 q_rad、valid、gripper_mm，旧字段转换不变；旧契约测试只更新精确字段集合断言，原有 110 项未删。checkJoints 拒绝缺轴/非有限数/越界；forwardUrdf 不夹限位、不补零；endPoses 右乘固定外参；buildPath 按原始帧换算，坏帧记录 dropped 并断段，超时断段且不补点。
- 显示：六轴先校验再插值，坏帧冻结当前显示姿态并提示；有效帧通过 setPoseMatrices 直传矩阵，绕开旧 forward 的限位夹取。标签六轴显示 URDF 度数并按实际宽高避让；旧入口仍为三个标签。state 增加 axes/q_rad。官方网格左右部件按开口各移动一半，异步加载后保留当前开口；2D 回退也接收六轴矩阵和开口。manual demo 动态生成六个参数限位滑块和一个夹爪滑块，输入保留 rad，显示度，避免限位端点往返换算误差。
- 验证：开工基线 .venv/bin/python -m pytest -q 为 110 passed in 7.92s；最终同命令为 131 passed in 8.31s（新增 21 项）。七组报告位置逐坐标容差 0.0006 mm、欧氏误差小于 0.001 mm；另测越界不夹取、固定外参、轨迹断段、安装台隔离、参数共享、六轴平滑/坏帧冻结/三轴回切、矩阵直通和官方夹指对称位移、manual 六轴逐个改变及两端限位。9 个 JS 文件 node --check 及 git diff --check 通过。
- 验证边界：Node 用 DOM/画布宿主替身执行实际 twin、fallback2d、demo 脚本，WebGLRenderer 用替身但保留真实 vendored Three 的矩阵/几何和实际网格数据；不等于浏览器或硬件验收。尝试 127.0.0.1:8766 只读静态服务时绑定被拒绝（PermissionError: Operation not permitted）；独立无头 Chromium 因 bootstrap_check_in Permission denied (1100) 退出，未得到截图。未更改权限、未启动 8000 服务、未连接硬件。
- 设计差异：与第 2、3 节接口无冲突。保留单独的旧 setPose(urdfAngles)，新增内部 setPoseMatrices 消费未夹取矩阵；六轴相机/激光/轨迹叠加的实际绘制属于后续任务，不在本轮扩展。README 与 docs 未修改；执行期间出现的 docs/model-swap/决策日志.md、screenshots/ 非本轮产物，未触碰。
- 遗留：浏览器里逐个拖动六个关节和夹爪，复核实际转动、开合与标签避让；相机外参、夹指尺寸、真实硬件均待实测。
- 回滚：本轮开始时已备份至 /var/folders/wb/6hqw8dgs6m5bd73_t19nl8100000gn/T/rearm-t1-wme3n361/before/。按上述修改清单逐个恢复本轮文件、移除本轮新增的 arm/ 与测试文件即可回退；保留并发出现的文档和后续用户改动。全程保持 feat/model-swap，HEAD=f38ce81b0f54e056fe1ffe526717c88ed1fe7ed0，未提交、未推送、未切分支、未安装包。

## 2026-11-14 T2a 自制夹指 STEP 网格与孪生安装 [T2a-20261114]
- 目标：把 hardware/gripper/机械臂夹具.STEP 转为与 b601 同格式的轻量网格，默认装入孪生并保留官方夹指切换；不安装依赖、不提交、不推送、不切分支。
- 新增：scripts/build_gripper_mesh.py；rearm/ui/static/modules/twin/meshes/gripper.json、gripper.bin；tests/test_gripper_mesh.py；output/playwright/t2a-gripper-offline.png。
- 修改：rearm/ui/static/modules/arm/arm-params.js；rearm/ui/static/modules/twin/scene.js、twin.js、twin.css、demo.html；rearm/ui/static/modules/main.js（仅 createTwin 的 gripper 参数）；tests/test_arm_kinematics.py（外参期望与官方夹指测试显式选项）；LOG.md、LOG-INDEX.md。
- 实体尺寸：gmsh 4.15.2 / OpenCASCADE 读到一个实体，包围盒 mm：X [-12.5,12.5]、Y [-20,20]、Z [0,65.5]，即 25×40×65.5。任务中的约 49×80×67 来自全部 CARTESIAN_POINT 的范围 [-31.89339828,-20,0] 至 [17.5,60,67.39339828]，包含实体外参考几何，不用作缩放尺寸。STEP SHA-256 为 b9f5851a8b50e8d74c0fe8a99124e55812df4ea8e2f6cd8c65fa827af39f8de2。
- 朝向依据：实际打开斜前、斜后、俯视三张照片；矩形镂空框架从滑块向前伸出。STEP Z=0 面有四个安装孔，Z=65.5 为指尖，故 STEP +Z → end_link +X，STEP +X → end_link +Y（横向 25 mm），STEP +Y → end_link +Z（高 40 mm）。照片估算安装，尚未实测。
- 安装参数：统一放在 gripper.customFinger；mount.xyz=(-0.065,0.0125,0) m，mount.rpy=(π/2,0,π/2) rad，约定 Rz·Ry·Rx；左指先安装，右指对安装后整个零件施加 flipRpy=(π,0,0)，绕 end_link X 轴翻转。脚本读取此处数值并烘焙到顶点，加载时仅叠加 ±Y 行程，不重复安装变换。根面 X=-65 mm，和官方滑块前端的误差不到 0.5 mm；指尖 X=0.5 mm，fingerLength=65.5 mm。
- 外参：T_end_tcp 取两指尖中点 (0.5,0,0) mm；相机光心 (-69.5,0,40) mm，位于指尖后 70 mm；激光 (-69.5,0,20) mm，位于相机正下方 20 mm。二者均朝局部 +X。安装位置为照片估算，激光仍待装好实测；本任务未扩展相机和激光的绘制。
- 网格：仅表面三角化，最小尺寸 2 mm、最大 4 mm、曲率 20、单线程；两指共 5760 面、每指 1430 顶点，二进制 103440 字节。小端 float32 positions 与 uint32 indices 连续排列，单位 m，parts 使用 frame=tool、side=left/right、finger_white/finger_grey。成功直接转换原 STEP，simplified=false，未使用简化方案。
- 加载：默认 custom；?gripper=official 只加载官方夹指。自制左右两指完整解码后才替换 finger_black，官方滑块、齿条、限位块继续保留和运动。JSON/BIN 缺失、HTTP/网络失败、解析失败、缺一指、截断数据、非法索引均静默退回官方；官方主体失败仍保留既有简化外形。配色由 --twin-finger 和 --twin-finger-2 控制。异步完成前销毁场景时释放未挂载几何。
- 几何验证：零开口时左指 Y∈[0,25] mm、右指 Y∈[-25,0] mm，全部三角形各自处于对应闭半空间，因此不仅顶点、三角形内部也不会相穿，接触面位于 Y=0；右指严格为左指绕 X 翻转。保留 URDF 单指 0–28.5 mm、总开口 0–57 mm；最大开口夹指外缘 ±53.5 mm，滑块与夹指均在导轨限位范围 ±85 mm 内。网格闭合、每条边恰连两面、无退化面、有向体积与 OCC 实体体积相差不到 0.2%。
- 验证：开工 .venv/bin/python -m pytest -q 为 131 passed in 8.15s；最终同命令为 144 passed in 8.70s，原 131 项保留，新增 13 项。相关子集 45 passed；实际 scene.js + vendored Three 几何/矩阵/材质验证 0、20、57 mm 开合、加载前已有开口、CSS 重着色、官方选项和七种加载失败退路。四个 JS 文件与 demo 内联模块 node --check 通过，转换脚本语法和 git diff --check 通过。
- 可重复性：用独立输出目录重跑转换，JSON/BIN 均逐字节一致。JSON SHA-256=7eb5ad39321b543751d56069571a3a588b1507777567d327b749db81d9e1601b；BIN SHA-256=53521fb97a8d7704a133f980489199b6d9dd2c7da2a3d7db6803041828d9cd7b。
- 画面证据：从实际 scene.js 装配对象导出末端几何，离线光栅化 0、20、57 mm 的斜视及俯视，已打开 output/playwright/t2a-gripper-offline.png 对照照片核对矩形开孔、翻转方向、一白一灰、根部连接和导轨范围。该图是离线几何渲染，不是浏览器截图。导出数据 /private/tmp/rearm-t2a-render-scene.json，渲染脚本 /private/tmp/rearm-t2a-render.py。
- 遗留：Playwright 启动独立 Chrome 以 SIGABRT 退出，清理时报 kill EPERM，未获得实际 WebGL 浏览器画面，未改变权限或启动服务。请在 /static/modules/twin/demo.html?source=manual 将夹爪从 0 拖到 57 mm，再加 &gripper=official 对比；真实安装位置仍待实测。没有连接硬件、没有启动 8000 端口服务。
- 回滚：修改前文件备份位于 /var/folders/wb/6hqw8dgs6m5bd73_t19nl8100000gn/T/rearm-t2a-nfqr_e6z/before/；恢复上述本轮修改文件并移除本轮新增文件即可局部回退，保留后续用户改动。工作分支保持 feat/model-swap；app.js、app.css、index.html、guide/theme/focus/presentation、rearm 下 Python、config、docs 和项目 .venv 均未编辑。

## 2026-11-14 T4 主机数据源、模拟练习与激光守护 [T4-20261114]
- 目标：按设计第 5、6 节和任务接口 v1 实现纯逻辑；保持 feat/model-swap，不接真实地址、不改页面、不提交、不推送、不安装包。
- 新增：rearm/ui/static/modules/datasource/host-source.js、mock-host.js；modules/trainer/config.js、store.js、metrics.js、laser-guard.js；tests/test_trainer_logic.py。
- 修改：rearm/ui/static/modules/datasource/index.js（注册 host/mock、增加 trainerSourceFromParams）；tests/test_twin_modules.py（仅把数据源完整名单从 3 项扩展为 5 项，其他断言保留）；LOG.md、LOG-INDEX.md。
- host-source：原始 v1 消息发布、非对象/错误版本过滤、连接/断开/静默超时通知、错误和断线重连、停止后的旧回调隔离；WebSocket 地址转换为同主机同端口的 HTTP(S) /api/v1/command，POST 自增 seq，网络异常转为 network 应答。构造时不连接，无模拟回退。
- mock-host：同样的原始消息和 Promise 指令接口；hello 标明 sim；实时计时与 advance 共用事件循环。六轴平滑抓取 6 秒，样本逐帧取自已经发出的 joint_state，自动 4 节点；复用 ARM_PARAMS、laserRay、endPoses 计算限位内姿态、250 mm 光束点和 end_link 基座坐标。支持示范/练习互斥、缺示范拒绝、停止、急停/解除、完整指令记录、TTL 自动关灯、每秒心跳和软件激光状态。
- 模拟偏差：第 p 遍各节点目标 d=max(2.5,18×0.62^(p−1))+ε mm，ε 为固定种子 LCG 的 [-0.1,0.1) mm 噪声。由参考光点到 J1 轴的基座 XY 半径 r 反算 Δq1=2×asin(d/(2r))，对 J1 加偏置后再次运行 FK 得到实测点和三维 dev；并非只填入预定 dev_norm_mm。修正 items 是下一遍各节点实际 J1 目标角差，中文说明随数值生成。
- 8 遍证据：seed=1，mean_mm 为 [17.9907425747, 11.1475506758, 6.8856284093, 4.3220812869, 2.6798317016, 2.4354951016, 2.4899630522, 2.5060913849]；改善 86.0701059199%；32/32 个节点 valid=true，停稳后 400 ms 返回；同 seed 整个消息序列相同，不同 seed 数值不同。未接守护器时 4/4 节点在 2000 ms 超时，valid=false、spot_not_found、缺测坐标及统计保留 null。
- store/metrics：不可变归并、按遍及节点键去重、按时间/序号拒绝槽位内旧消息、迟到历史补齐、最多 100 条事件；断线保留 mode 并置 stale。指标按完成遍统计，已应用 correction 按遍计数；无数据、首遍缺测或零基线改善率为 null。laserMismatch 用最新消息时间 state.t 与 panel_laser.t 比较，heartbeat 推进计时，纯函数不读墙钟。
- laser-guard：在线练习停稳节点开灯并续期，同节点结果或超时关闭，重复节点不重开；手动开关只在在线且非练习/急停/故障时允许，示范可保留手动灯，进入练习先关闭。急停、故障、断线和四种 shutdown 均清理计时并尝试关灯；发送同步异常/Promise 拒绝均不外抛。shutdown 即使已关也发送安全兜底，连续间隔小于 200 ms 合并；生命周期 shutdown 后抑制遥测自动重开，重新装配需新 guard，显式合法 manual(true) 可恢复手动意图。
- 设计差异：与第 5、6 节和本任务接口无冲突。细化约定：成功节点停留 800 ms，未见光点则停留至 2000 ms 超时后离开；mark_node 是预留指令，mock 返回 unsupported；mock 不提供图像流，hello.camera 和 image_url 为 null，不伪造相机内容；界面装配及 panel_laser 消息接线属于后续页面任务，本轮未实现。
- 验证：开工 .venv/bin/python -m pytest -q 为 156 passed in 8.68s；最终同命令 179 passed in 9.64s，原 156 项全部保留，新增 23 项。测试使用 Node ES 模块和虚拟时钟，不依赖真实等待；所有激光指令送 mock，真实 WebSocket/fetch 设为失败哨兵，host 仅使用假 WebSocket/fetch。覆盖 8 遍闭环、无光点失败、各类守护规则、TTL、急停、重连和 3 秒静默、不可变/乱序/去重、空指标、无 DOM 和无硬编码主机地址。7 个相关 JS 文件 node --check、git diff --check 通过。
- 遗留与范围：真实硬件/网络及页面集成未验证，按任务要求未连接或修改；未启动服务或占用 8000 端口。执行中出现的 docs/model-swap/tasks/T3-接口文档.md、docs/model-swap/遥控面板方案.md 是外部并发新增，未触碰。app.js、app.css、index.html、main.js、arm/、twin/、guide/theme/focus/presentation、rearm 下 Python、config/、docs/、.venv 均未编辑。
- 回滚：修改前 index.js、test_twin_modules.py、LOG.md、LOG-INDEX.md 保存在 /private/tmp/rearm-t4-2mhxj_6h/before/。只恢复本轮对应文件、移除上列新增的 6 个 JS 与 test_trainer_logic.py 即可局部回退；日志只移除本 T4 条目，保留后续用户或并发改动。

## 2026-11-14 T5 首页认领接缝与轨迹训练区域 [T5-20261114]
- 目标：按设计第 1、4、6 节、P0-3/P0-4 和 T5 任务替换首页内容，保持 feat/model-swap；不提交、不推送、不切分支、不装包、不接真实地址。
- 修改：rearm/ui/static/app.js（仅认领判断）、modules/main.js（legacy 分流及 trainer 装配）；新增 modules/trainer/trainer.js、trainer.css、views/kpis.js、joints.js、feed.js、deviation-chart.js、corrections.js、camera.js、controls.js、canvas.js、format.js；新增 tests/test_trainer_views.py；追加 LOG.md 和 LOG-INDEX.md。
- app.js：第 3 行 claimed；第 144 行断线相机芯片保护；第 188、197 行在相机已认领时停止旧请求；第 213–260 行按六个区域跳过原渲染；第 284 行误差图直接重画保护；第 478 行误差图 aria 文案保护。showCameraFrame 的检查防止认领前已发出的图像异步回填。syncControls、急停、导航、旧卡片等逻辑未改；没有引入 trainer 或 modules 字样，未认领时原语句顺序保持。
- 装配：非 legacy 不启动旧孪生数据源、不加载 guide；孪生不可用时 trainer 接收 null。trainer 初始化失败恢复各区域原 DOM、按钮显隐和图表事件，main 清 claim 并广播 rearm:theme。无新增 HTML 挂载位，index.html 和 app.css 逐字未改。
- 数据与孪生：订阅 T4 原始消息，经 reduce 和 summarize 更新七个 view；RAF 合并。原始关节帧按 pass 积累，每次换遍清空；buildPath 计算示范/本遍 TCP 路径，无效或断线帧断段。节点独立 FK，光点 mm 转 m；makeFrame 的时间从 Unix 毫秒转秒，按 hello.sim/链路映射 sim/live/offline。
- 区域：四个 KPI 显示遍数、平均/最大偏差及阈值、改善率、修正次数；关节按 ARM_PARAMS 显示六轴及夹爪、无效行、最高温度/最大电流/模式；事件最新在上；偏差图平均实线/最大虚线/阈值，字号经探针；修正说明与条目用 textContent，历史滚动；手眼相机 MJPEG 或移动网格示意，光点/箭头/偏差、实际激光状态及不一致告警；控制区隐藏旧按钮，示范/练习互斥，手动激光次要按钮和琥珀提示条。旧模拟标签通过附加 trainer class 暂时隐藏，新增来源 pill 展示模拟或主机名。
- 安全接线：pagehide、hidden、离开主页都 shutdown；捕获急停点击补发 estop、shutdown，不拦截旧处理；rearm:state 的 estop 真→假发送 reset_estop。未 hello/离线/故障/急停禁用训练操作，练习中手动激光禁用；离开主页或隐藏期间也禁用训练操作。生命周期 shutdown 后不自动恢复出光，需要新的显式操作重新装配 guard。激光预期只在开关意图变化时记录，续期不会不断重置 1 秒告警窗口。
- 验证：开工全量 179 passed in 9.84s；最终 .venv/bin/python -m pytest -q 为 199 passed、1 failed in 10.87s。新增 21 项全过（1.42s），Node 语法检查及 git diff --check 通过。DOM 集成使用缓存中已存在的 jsdom，没有安装依赖；无该宿主的环境会跳过 4 项 DOM 集成，其余契约/纯逻辑测试仍执行。
- 运行证据：实际 mock + trainer + guard 虚拟时钟跑完 6 遍，平均偏差 17.99→11.15→6.89→4.32→2.68→2.44 mm；验证 RAF 合并、孪生六轴/路径/节点、事件/修正/图表、手动提示、全部生命周期关灯、急停/解除、DOM 回退、无孪生、假 WebSocket 离线不回退模拟。另执行实际 app.js 的 DOM 测试，验证旧三轴渲染和认领后不覆盖六区域；实际 main.js 的隔离宿主验证 legacy、缺失孪生和 trainer 加载失败。恶意 llm_text 作为文字显示，不生成 img 节点。
- 唯一测试冲突：现有 tests/test_trainer_logic.py:452 将 trainer 根目录 glob('*.js') 加两个 datasource 文件的数量写死为 6，且要求这些文件全部无 DOM；新增任务指定的 trainer.js 后为 7，因此失败。已通过异步问题申请仅把扫描范围限定到 T4 四个逻辑文件，尚未收到授权；按“旧测试不变”保持该文件原样，没有跳过或削弱断言。验收“全量全过”因此尚未达成。
- 画面边界：独立 Chromium 启动退出（Target page, context or browser has been closed）；尝试绑定 127.0.0.1:8766 得到 PermissionError: Operation not permitted。未申请提权、未改变权限、未启动任何服务；1920×1080 / 1280×720 日常与路演的实际浏览器排版、实际 MJPEG、真实硬件均未验证。CSS 已做七行紧凑布局、矮屏路演两列，但不能据 DOM 测试声称没有截断。
- 设计差异：功能接口与设计一致；新增 views/canvas.js、format.js 共用字号解析、格式化和回退工具。初次打开不自动执行示范/练习，默认模拟主机在线，按“示范→结束→练习”启动。测试扫描范围与新入口文件的冲突及浏览器限制如上，待处理。
- 未触碰：app.css、index.html、tokens.css、guide/theme/focus/presentation、arm/twin、T4 逻辑及 datasource、rearm 下 Python、config、docs、.venv、全部旧测试、仓库根海报素材包.zip。
- 回滚：修改前文件在 /private/tmp/rearm-t5-e1w8cxcw/before/；只恢复 app.js、main.js，移除上列本轮新增 trainer 入口/样式/views 和 test_trainer_views.py，删除本日志条目及对应索引即可局部回退，保留 T4 文件和其他用户改动。临时 DOM 验证脚本在同一 /private/tmp 目录；仓库未新增临时产物。

## 2026-11-14 T5 第一次验收返修 [T5R1-20261114]
- 目标：修正验收列出的 8 项数字表达、单位、标签重叠、路演关节布局与模拟相机投影问题；保留 Claude 已修正的逻辑测试扫描范围和手动结束示范行为。
- 修改文件：rearm/ui/static/modules/datasource/mock-host.js；modules/trainer/views/format.js、kpis.js、corrections.js、camera.js、deviation-chart.js；modules/trainer/trainer.css；modules/twin/twin.js（仅浮动标签避让）；tests/test_trainer_logic.py、test_trainer_views.py、test_twin_overlay.py、test_arm_kinematics.py；LOG.md、LOG-INDEX.md。新增 modules/trainer/format.js 纯格式化函数，无新依赖。
- 数字：共享格式化先舍入绝对值，再确定正负号，输出 U+2212 且零不带符号；修正条目及摘要将 deg 显示为 °，mock 的 llm_text 共用数字格式，接口 items.unit 保持 deg。每项显示 target 加 note 中的节点编号；空 note 只显示 target。
- 改善率：绝对百分数与独立 % 单位；改善副行用 ↓，变差用 ▲ 变差及 --bad；只有一遍已完成结果时显示 — / 第 1 遍是基准。持平和舍入为零均不出现负零；从变差转为改善或离线时清除红色数值状态。
- 孪生：getBoundingClientRect 读取状态芯片和标签尺寸，左上角预留芯片右边界/下边界再加 8 px；按偏差、关节、节点优先级寻找邻近空位，找不到空位时隐藏低优先级标签。覆盖旧三轴入口及六轴入口，不改几何、运动、数据或样式文件。
- 路演：移除两列布局的 max-height:800px 限制，1920×1080 与 1280×720 共用两列；显式覆盖 presentation 后加载的关节 margin 与读数字号，避免原规则恢复大行距；环境信息改为两列并收紧上下间距。字号仍取 --fs-sm，不缩小到路演最小值以下。
- 相机：分辨率来自同一 hello.camera 对象，默认 640×480；焦距使用 ARM_PARAMS 中的 87°×58° 视场角。逆变换到相机局部坐标，+X 为深度、+Y 向左、+Z 向上，针孔投影使参考点位于约 (320,274.64)。实测世界坐标统一投影到对应示范节点的相机坐标系，以便和已保存的参考像素比较；不是把两个不同姿态的手眼相机像素直接相减，也不声称实物标定。接口世界坐标/FK/偏差/修正量未改变。
- 相机标签：改为 HTML 浮层，使用 --fs-sm，处理 SVG 等比居中留边；按四个芯片实际边界加 8 px 选择光点另一侧空位。极端外部坐标遇芯片时隐藏被遮挡的圆点，不伪移坐标；无可用文字位置时隐藏标签。模拟中心附近的正常点保持显示。偏差图同步以 --fs-sm 为字号下限，避免日常模式原 --fs-chart=10px。
- 测试：原 200 项保留，新增 8 项（包含相机 3 组参数化）。DOM 宿主补齐 getBoundingClientRect/classList.contains；原 SVG 文本断言改为验证 HTML 浮层及 SVG 无文字。新增改善率首遍/改善/变差/持平/近零/离线、单位/负零/节点名称、四角避让/不同画幅、针孔参考和实测投影/分辨率比例/llm_text、CSS 与孪生避让契约。相关 96 项通过。
- 最终验证：.venv/bin/python -m pytest -q 为 208 passed in 11.93s；8 个改动/新增 JS 文件 node --check 通过；git diff --check 通过。开工时禁改路径 SHA-256 清单与结束时完全一致，两个 Claude 修正片段逐字保留。没有提交、推送或切分支。
- 画面验证限制：127.0.0.1:8766 监听被运行环境拒绝，PermissionError: Operation not permitted；CUA 浏览器 host 不可用，原生 Google Chrome 访问被工具拒绝；独立无头 Chromium 启动退出，未获得新截图。仅查看了用户已有的返修前 1280×720、1920×1080 路演截图定位 CSS 层叠原因。四组最终浏览器字号、无裁切/无溢出、1920 路演至少 3 条事件仍需按原浏览器检查重跑，不能把 DOM/文本测试当成画面验收。浏览器错误证据：/private/tmp/rearm-t5r1-g86w8fav/browser-error.txt；测试输出：/private/tmp/rearm-t5r1-pytest-final.txt。
- 回滚：本轮修改前文件保存在 /private/tmp/rearm-t5r1-g86w8fav/before/；仅恢复本条列出的文件，移除新增 modules/trainer/format.js，删除本日志条目及索引即可局部回滚。两个补充宿主测试文件从开工时干净的 HEAD 取原文备份。保留用户已有 docs/model-swap/决策日志.md 改动、screenshots/ 和海报素材包.zip；未改 README/SPEC。

## 2026-11-15 路演节点① T0 验收脚本 [NODE1-T0-20261115]
- 目标：只实现 docs/路演/tasks/节点1-任务书.md 的 T0，按 A 节与清单 9.1/9.3/9.4 验收，不开始 T1。
- 新增脚本：scripts/acceptance/node1.sh、node1.mjs、browser.mjs、production-checks.mjs、surface-checks.mjs、tooltip-check.mjs、library-checks.mjs、static-checks.mjs、report.mjs。
- 新增测试与记录：tests/test_node1_acceptance.py（10 项反例测试）、docs/路演/tasks/卡点.md。修改 LOG.md、LOG-INDEX.md（仅追加）。
- 本轮生成证据：docs/路演/验收/节点1/报告.md、results.json、pytest.log、server.log、infrastructure.log；screenshots/ 已创建但未取得画面。报告逐条列出17项、10张应有关键截图的缺口、vendor 命中与 git log main..HEAD --oneline。
- 脚本决策：每条独立函数，异常不中断后面的只读检查；状态由 MutationObserver 记录，去相邻重复再去“就绪”后精确匹配9词，确认到待命最多90秒；抓取时急停观察5秒；重置仅点一次；不可用按钮统一检查 aria-disabled、help 指针及0.8/1.2秒提示时机；措辞覆盖四页、确认框、两个文档和两类新增流程；布局沿用 shots.mjs 的量法；跨页面保留模拟主机的全部命令记录。
- 环境边界：只用已安装的 playwright-core 和缓存的 chrome-headless-shell，不安装包；服务固定 127.0.0.1:8031，--sim --nongeometric，独立临时数据目录，trap 关闭本次服务。没有连接真实硬件或另一主机，所有应用代码与旧页面保持不变。
- 地址扫描：扫描37个JS，非vendor命中3处：modules/datasource/device-source.js:2 的 ws://…、modules/datasource/index.js:17 的 ws://主机:端口、modules/trainer/views/camera.js:34 的 http://www.w3.org/2000/svg。vendor另有3处，按规格单列不计失败。没有为命名空间或注释增加豁免，亦未改受保护的训练代码；任务预期第16条转绿与现有代码存在冲突，已在卡点.md说明。
- 验证：新增测试10 passed in 0.22s；指定完整 pytest 334 passed in 21.24s；scripts/acceptance/node1.sh 内 pytest 334 passed in 21.53s，最终退出码1。第1、17条通过；第2–15条因浏览器无法启动未执行并记失败；第16条地址扫描失败。bash -n、全部8个mjs的 node --check 与 git diff --check 通过。没有通过截图验收，不声称页面已验证。
- 阻拦证据：8031服务实际启动并正常关闭（server pid 88293）。Chromium pid 88306 启动时报 `browserType.launch: Target page, context or browser has been closed`；核心原文 `Check failed: kr == KERN_SUCCESS. bootstrap_check_in org.chromium.Chromium.MachPortRendezvousServer.88306: Permission denied (1100)`；清理另报 `Error: kill EPERM`，随后进程 SIGTRAP 退出。完整日志见 infrastructure.log，未重试、未更换浏览器/端口或绕过沙箱。
- 提交状态：未提交、未暂存，因T0应转绿的第16条仍失败，且用户明确要求浏览器启动受阻时保留未提交改动。没有尝试 git add/commit，没有创建替代仓库或bundle。工作分支 feat/model-swap；HEAD=f0dc98c610cd437cbbfac954737fb5a7f2e0489d；main=57785e8f95837f0d2384b4f5968cba225821434c，未改变。海报素材包.zip 未跟踪。
- 遗留：无头浏览器检查和截图未完成；第16条规则与现存受保护代码的冲突待决定，未自行放宽。原有 docs/路演/施工清单.md、tasks/节点1-任务书.md、Go_PPT.md 仍为开工时的未跟踪文件，未编辑；T1–T8未执行。
- 回滚：移除本轮新增的9个验收脚本、测试文件、卡点文件与本轮5个报告证据文件，删除本日志块和对应索引行即可局部回退；保留开工前已有的路演文件、素材包及后续用户改动。应用与配置不需要回滚。


## PPT-COVER-20261115：路演封面方向

- 日期：2026-11-15（Asia/Taipei）
- 目标：依据用户海报制作横版路演封面供选方向，并整理四个必须呈现的优势。
- 改动文件：新增 `deck/cover-directions-v1/` 下三张 PNG、原图和品牌副本、提示词、内容来源与检查记录；本条日志及索引。
- 关键决策：先提供 A 产品特写、B 双臂呼应、C 横向字标三个方案，用户选定后再延展轮换底图。用户本轮四个优势优先于旧路演文档的不同表述；标准化交付保留为有望实现，不虚构成果数字。
- 验证：三张实际生成图已逐张查看，无标题与硬件交叠；文件尺寸均为 1672×941，只作视觉选稿。SHA-256 已写入 `deck/cover-directions-v1/review/sha256.json`。
- 遗留：等待用户选择方向；最终分辨率、原始字标及产品结构复核、轮换底图、整套 PPT、视频与实际投屏仍待后续。
- 回滚：本轮为独立新增目录，原海报、品牌文件及控制台代码未改；无需回退项目其他工作，忽略本轮目录即可。


## NODE1-T1-20261115：控制台外壳、导航与通用控件

- 日期：2026-11-15（Asia/Taipei）。目标：只做路演节点①任务 T1；本轮用户要求覆盖任务书的运行/提交步骤，只运行完整 pytest 和 node --check，浏览器验收与提交由外部执行。
- 新增入口：`rearm/ui/static/console.html`，只加载 tokens.css 与新 main.js，并复用原品牌 SVG。
- 新增外壳：`rearm/ui/static/modules/console/main.js`、`console.css`；`shell/nav.js`、`router.js`、`topbar.js`、`estop.js`、`dialog.js`、`tooltip.js`、`view.js`；`state/words.js`；`pages/production/index.js`、`pages/parts/index.js`、`pages/records/index.js`、`pages/settings/index.js`。共14个文件，其中13个 JS；每个文件不超过200行。
- 修改服务：`rearm/ui/server.py` 仅修改 `/` 路由，默认返回 console.html，`legacy=1` 返回原 index.html，保留 no-cache；未改指令、WebSocket、急停或硬件行为。
- 测试文件：新增 `tests/test_console_shell.py`（13项）；修改 `tests/test_ui_architecture.py`（ASGI测试助手正确分离path/query，旧首页测试改走legacy）、`tests/test_panel_frontend_contract.py`、`tests/test_presentation_mode.py`（仅改旧首页请求入口）。原断言未弱化、原测试未删除。
- 记录文件：追加 `docs/路演/tasks/卡点.md` 的T1选择器自查；本日志及 `LOG-INDEX.md` 仅追加。已有路演验收报告、截图和 scripts/acceptance/ 未改；同时出现的 deck/ 与封面日志属于其他工作，完整保留。
- 关键决策：四个页面本轮只有真实用途说明，各页独立 optional 加载，加载失败只替换该页内容；hash 统一驱动可见页面并保留查询串；视图 render 合并到 requestAnimationFrame，dispose 取消待渲染帧。状态词放在唯一词表，未实现T2 store或模拟主机。
- 控件：急停在顶栏最右，48px高，距左侧按钮24px，实底使用 --estop；未设快捷键。当前没有数据源，重置与急停使用aria-disabled和原因提示，不虚构执行成功。急停接入点只调用注入的send，不提前改变状态。通用dialog使用原生模态框、Tab焦点圈、Esc取消和焦点归还；文案通过textContent写入。统一tooltip延迟850ms显示，移开/失焦/启用/删除/关框时清理，鼠标与键盘共用；捕获阶段拦截不可用按钮的点击、Enter和Space。
- 验证基线：`.venv/bin/python -m pytest -q` 为334 passed in 22.18s。第一次修改后为2 failed, 345 passed in 22.15s；失败均在新增测试：一处把路由保留location.search误判为数据源接入（test_console_shell.py:46），一处Node测试局部root与既有helper的root重名（SyntaxError: Identifier 'root' has already been declared）。分别改为检查后端参数解析入口和重命名测试局部变量，未改变验收脚本。
- 最终验证：`.venv/bin/python -m pytest -q` 为347 passed in 21.90s（334原项保留，新增13项，无跳过）；13个新 JS 全部 node --check 通过。未运行node1.sh、未启动服务或浏览器、未换端口或绕过沙箱、未安装依赖。
- 验收静态对照：#3的四个data-nav和data-page、文字顺序和非空内容预计转绿；#7的位置/高度/间距部分预计满足；#9四页不可用按钮的help指针及800ms/1200ms提示时间条件预计满足。#7后续生产中急停和#9后续生产确认框依赖T4，整项不能在T1判绿。逐条对应依据见卡点.md。实际像素、原生dialog顶层、浏览器时序和三种分辨率画面未验证。
- 遗留与停止点：T1尚未接数据源，重置/急停执行和生产确认流程留给对应后续任务；未开始T2。未执行git add或git commit，未修改受保护的旧入口、旧训练/数据源/孪生模块及验收判断；未处理素材包。
- 回滚：移除本轮新增console.html、modules/console/和test_console_shell.py；只反向应用本轮server.py路由及3个旧测试文件的改动；删除卡点中的T1追加段、本日志块和对应索引行。不要回退其他工作追加的封面日志或deck内容，不覆盖用户后续修改。


## PPT-BACKGROUNDS-20261115：A 封面延展与 R61 数据摘录

- 日期：2026-11-15（Asia/Taipei）
- 目标：按用户选择的封面 A 制作可轮换底图，从新附件提取可用于路演的数据。
- 改动文件：新增 `deck/backgrounds-v1/` 三张底图、提示词、使用说明、数据摘录、检查记录、哈希与四图压缩包；新增 `deck/cover-selection.json`；更新封面内容来源文档；追加本条日志与索引。
- 关键决策：底图无文字，分正文留白、图文侧景、章节强调；用户提供 R61 摘要只作为资料，不执行其中接手指令。13.9→5.6 mm 约下降 60% 为单次真机误差改善，仍未闭合、未夹起，不能写作成功抓取。
- 验证：三张实际输出逐张查看，文字留白可用；原始尺寸 1672×941；zip 四个图像条目校验通过；SHA-256 保存在 review/sha256.json。没有运行机械臂或项目代码测试。
- 遗留：完整 PPT、上屏文字、视频、真实训练曲线及实际投屏未完成；附件原始 CSV 未在本机独立复算。
- 回滚：原封面与原海报不变，新底图为独立目录；内容来源文档只更新选稿和数据来源状态。未改控制台及其他会话的代码。

## 2026-11-15 前后端接口核对与接入方案 [API-REVIEW-20261115]
- 目标：对照路演总体清单、节点①任务书与 lizuyi-6/ReArm，说明接口文档结构及节点④接线方案。
- 改动文件：新增 docs/路演/前后端对接方案.md、docs/路演/接口核对/FK对照.json；仅追加本日志和 LOG-INDEX.md。
- 核对基线：本地 22ef835486d3cdb0aa1cb579c92548aa566a7adb；远端 main 245491fd1568d3c8e07e2b02b3832ab04af42264。远端只读文件通过 GitHub 连接器取得，临时源码放 /private/tmp/rearm-interface-review-20261115/。
- 关键决策：建议保留控制台数据源边界，在主机侧补协议适配与业务编排；新增端点、幂等、恢复及有效性扩展均列为待双方确认，没有修改正式协议、任务书或运行代码，没有启动节点④。
- 已发现差异：HTTP 轮询 /api/state 与 /api/cmd 对照 WS/v1 消息；pick 为抓起放回，缺装配放置和最终检查；夹爪57/110mm、力/力矩、7/6轴、遥测有效性与实机限位不一致；急停、解除与自动回位不能直接照搬模拟行为。
- 验证：使用本地既有 .venv 的 numpy 与 node 运行纯 FK 对照，3组 end_link 最大坐标差 <4e-13mm，TCP相距105.5mm；后端已记录工作位复现前端J4越界。文档2段JSON可解析、本地引用文件均存在，证据数值断言通过。没有运行应用测试或远端套件，没有连接机械臂、相机或实际主机，也没有渲染界面。
- 遗留：双方确认部署、坐标/标定、零件ID、装配测量、任务生命周期后，再由接口施工任务补正式文档和契约；T2等并行改动未碰。
- 回滚：只删除本轮两个新增文件和本日志块、索引行；不回退其他会话改动。

## NODE1-T2-20261115：控制台协议、模拟主机与状态归并

- 日期：2026-11-15（Asia/Taipei）。目标：只实现路演节点① T2，按用户指令只运行完整 pytest 和 node --check，浏览器验收与提交由外部执行。
- 修改文件：docs/接口文档.md（仅追加附录 C）、rearm/ui/static/modules/console/main.js、shell/topbar.js、tests/test_console_shell.py、docs/路演/tasks/卡点.md；本日志与 LOG-INDEX.md 只追加。
- 新增文件：rearm/ui/static/modules/datasource/mock-console.js；datasource/mock-console/{timeline,production,training,library}.js；datasource/fixtures/{parts,recipes,workspace,poses}.js；console/state/{store,selectors}.js；tests/test_console_data.py。13 个新增/改动 JS 均不超过 200 行，无新依赖。
- 数据：四个已收录零件的夹持力为 11.6/12.3/12.1/11.8 N，每件有可复算的质量、材质、摩擦系数、安全系数及双指估算；8–12 轮下降偏差、试抓、图像数、用时、收录时间、版本齐全；一个圆盘定位工装和两步配方。模型/照片/录像素材未提供，几何及轮廓占位，photo_url 为 null，没有录像入口。
- 姿态：预先指定关节角，再以既有 FK 计算夹持中心布置物体；观察位向下且光轴落在工作区范围内，所有关键姿态和全流程遥测通过 checkJoints。没有改运动学、限位、旧模拟主机或孪生。姿态数据是演示用，不是实机标定或碰撞验证。
- 主机：同一事件队列支持实时 20 Hz 和 advance 虚拟时间；两步配方全程 38 秒，自检九项、识别、抓放、检查、完成与收回齐全，run_done 的检查完成用时为 32.5 秒。首套固定到位 0.4 mm，后续种子随机约九成通过。急停锁住当前姿态/开口并取消生产、拍照、训练；解除不续跑；reset_demo 清空本次统计和记录并回折叠，同时保留库和指令审计数组。
- 训练与文档：拍照 1.5 秒，训练立即发 round=0 的开始通知，随后每 1.2 秒一轮，8 轮后自动更新文档/库并完成；支持零件、配方新增与按 id 重训，后者版本加 1；生产/训练/拍照互斥，角度和轨迹不进入文档或生产记录。新件先使用捕获位几何占位，独立素材仍待提供。
- store 与装配：纯 reduce(state,message) 按时间、序号及对象 ID 归并，重复结果不增计数，重置前迟到结果不复活；完成套数、通过率、近期偏差及两类记录只由消息产生。main 单独 optional 加载新主机，将源 commands 原数组挂到 window.__rearmMock，页面只拿 store/send；顶栏状态随消息更新，T1 急停接上 send。T4 的重置按钮、确认流程和业务页面未提前实现。
- 测试边界调整：旧 T1 静态测试只对 main.js 开放任务书明确要求的指定数据源 import 和唯一审计挂载语句，其他禁令与旧断言保留；旧协议章节和 test_host_protocol_doc.py 未改。新附录单独有实际消息字段覆盖测试。
- 验证：开工 347 passed in 21.90s；新增 22 项，最终 .venv/bin/python -m pytest -q 为 369 passed in 28.07s，无跳过、无删除；13 个 JS 的 node --check 通过。覆盖 38 秒精确状态顺序、20 Hz/插值/夹爪时序、8 个时点急停、重置、训练新增和重训、同步回调中止、种子复现、纯 reducer、停止/重启、指令数组身份及 JSDOM 顶栏接线。
- 失败证据与修正：首次 2 failed/367 passed，暴露相机光轴方向和新协议字段标记问题；第一次修正后 1 failed/368 passed，新增工作区落点检查发现相机 +Z 偏移未纳入观察位选择；仅补诊断的复跑仍 1 failed/368 passed。依据 FK 输出做第二次姿态调整后全绿。测试次数、原数值及逐条选择器对照见卡点.md；没有第三次盲改或放宽验收。
- 验收预期：T2 没有必须转绿的页面条目；#1 单测满足，#15 原数组审计钩子已具备、正常轨迹不发送激光指令，预计可转绿；#3/#16/#17 预计保持。#5/#6/#7/#8/#13 的数据条件已测，但页面钩子仍属于后续任务，不能称整项通过。没有运行 node1.sh、服务或浏览器，没有修改 scripts/acceptance/ 判断、既有验收报告/截图，没有 git add/commit。
- 遗留：实际浏览器画面、鼠标时序与验收报告待外部执行；T3–T8 未开始。已有 deck/、路演前后端对接方案、接口核对文件及其他会话追加日志均保留，README/SPEC/旧页面/旧训练/旧数据源/安全逻辑未动。
- 回滚：只移除本条列出的 12 个新增文件，反向应用本轮 main/topbar/test_console_shell 改动，删除接口附录 C、卡点 T2 段和本日志/索引条目；不要覆盖其他会话的日志、文档或素材。


## PPT-ROADSHOW-20261115：完整 11 页路演稿

- 日期：2026-11-15（Asia/Taipei）
- 目标：沿用用户确认的封面 A 和三张底图，完整讲清四项优势，并结合 R61 交接摘要。
- 改动文件：新增 `deck/roadshow-v1/` 内容与来源、演示稿构建记录、最终讲稿、在线文稿连接信息、逐页渲染及验收记录；追加日志与索引。
- 关键决策：11 页顺序为成本问题、产品方案、四项优势、单次真机结果、应用流程、后续验证与结尾；第 3 页使用项目原始硬件照片；第 6 页用原生可编辑图表呈现 13.9→5.6 mm，保留未闭合、未夹起和 5 mm 门限；标准化交付保留目标表述。
- 保存：在线文稿 page_557b0041cccc819198204f4e3f302f2d，artifact_external_d40ccdec-bb55-482a-bd42-107c8b325fd8，stateVersion 6；可由预览导出 .pptx。
- 验证：11 页逐页渲染目检及拼版检查；全部 1280×720；四项优势与 R61 限制覆盖；无越界、无文字框交叠、无占位；已从在线状态核对 11 份备注与 1 张原生图表。
- 遗留：Windows PowerPoint 与现场投屏未验证；R61 原始遥测未在本机独立复算。当前目录无正式视频，使用实物照片与流程组成完整稿，不留视频占位。
- 回滚：原素材和前两轮输出保留；本轮独立目录与在线演示稿，不覆盖控制台或其他会话改动。


## PPT-VIDEO-SLOT-20261115：实体演示视频留位

- 日期：2026-11-15（Asia/Taipei）
- 目标：用户要求在路演稿预留实体演示视频的位置。
- 改动文件：在线演示稿及 `deck/roadshow-v1/` 的插页记录、页序、连接信息、验收记录与视频页预览；追加日志和索引。
- 关键决策：在产品介绍后插入第 4 页“实机演示”，预留 960×540、16:9 横版视频框；视频未嵌入，共 12 页。
- 验证：已看新页及全稿拼版；原 11 页非页码元素逐对象对照保持一致（忽略回读时补全的图片 byteLength），后续页码正确顺延；保存 stateVersion 9。
- 遗留：待实体演示视频提供后嵌入并测试播放；本轮未测试实际视频播放。
- 回滚：删除新增第 4 页并按 source/video-page-shifts.json 恢复原页码；改前快照和元信息保留在 review/before-video/。

## 2026-11-15 设备层任务书与五类卡点方案 [DEVICE-TASKBOOK-20261115]
- 目标：核对已有设备层任务书，补齐硬件参数、测量、协议、急停恢复和完整装配的解决办法。
- 改动文件：新增 docs/路演/tasks/节点4-设备层与后端接入任务书.md；同步 docs/路演/前后端对接方案.md 的入口、v2 建议及测量/终态口径；只追加本日志与索引。
- 依据：远端 245491fd1568d3c8e07e2b02b3832ab04af42264 的 M12/M13、服务与夹爪配置；本地总体施工清单、节点①任务书及 T2 接口附录 C。M13 已覆盖驱动、单位、限位和失能，但没有五类控制台对接的完整编排要求。
- 关键决策：真机独立 v2，旧训练与模拟 v1 保留；主机发布版本化硬件 profile；装配采用孔柱径向偏差、落座、存在性与顺序检查；置信度需校准，力与力矩分开；停止、解除、使能、归位各自独立；主机新增装配和检查编排。D0 至 D6 均写明负责方、交付物与验收条件。
- 验证：两份 Markdown 格式检查通过，13 个本地链接目标存在，2 段 JSON 样例解析通过，D0 至 D6 工单齐全。只修改文档，未运行应用测试、未连接机械臂或相机、未执行真机动作。
- 遗留：TCP/相机标定、孔柱与落座公差、测量误差上界及现场防坠恢复流程须实测确认；任务书为实施要求，尚未实现。未修改正式接口、SPEC、控制台代码或并行任务，也未启动节点④施工。
- 回滚：删除本次新增任务书；只撤销前后端对接方案中本次 v2 与入口同步，不删除此前源码核对及 FK 证据；移除本日志块与对应索引行，不回退其他会话追加内容。

## NODE1-T4-20261115：生产页、确认与重置接线

- 日期：2026-11-15（Asia/Taipei）。目标：仅完成路演节点① T4，验证限定为完整 pytest 和 node --check，浏览器验收与提交由外部执行。
- 修改文件：rearm/ui/static/modules/console/main.js、pages/production/index.js、shell/topbar.js、state/store.js；tests/test_console_shell.py；docs/路演/tasks/卡点.md；LOG.md、LOG-INDEX.md 仅追加。
- 新增文件：console/pages/production/production.css、views/{recipe-pick,key-number,steps,observe-view,twin-stage}.js；console/widgets/{dom,sparkline,stepper}.js；console/shell/reset.js；console/state/workspace.js；tests/test_console_production.py。所有新控制台 JS 均少于 200 行，无新增依赖。
- 关键决策：按已定路线保留原生 ES 模块；左侧约七成宽孪生，右侧依次为配方/开始、套数/通过率/偏差、步骤、自检及观察画面。组件树为 production→recipe-pick/key-number/steps/observe-view，main 单独 optional 装配 twin-stage，shell 负责确认、提示及重置；不用全局改版或新框架。
- 状态与数据：复用 T2 消息与词表，工作区从既有 datasource fixture 进入纯 store；抓取完成后随夹爪，放置完成后移到定位柱，急停保留位置，新生产与演示重置恢复工位。视图只读 store、只经 send 发命令；没有改主机协议、时间线、急停、限位或安全实现。首套检查结果回待命后保留；角度只显示于抓取 started 阶段，不写入记录。
- 交互：二次确认默认未勾选，复用统一 aria-disabled/提示/焦点机制；发送前再核对状态。演示一次点击依次解除和重置，前条拒绝则不继续；非演示急停必须确认，仅解除且不续跑。训练、生产、断线及无配方时禁用开始；失败应答显示原因，不改写结果。孪生失败只影响其挂载位。
- 视觉取舍：沿用品牌变量，层级用明度与分隔线；无彩色装饰、渐变或发光。空值灰色；观察标签按文字实际尺寸避让并用连线对应目标，字体不随 SVG 缩小；窄宽度下上下排列，内容溢出限定在右栏。真实渲染未验证，不能称布局已验收。
- 测试适配：T1 导入边界仅补任务明确要求的 main→twin 公开入口与 state→workspace fixture；保留视图网络、跨页及旧模块禁令。原页面失败测试新增孪生失败隔离断言，未删减原页面/导航/状态/急停断言。验收脚本未改。
- 验证：基线 391 passed in 30.24s；首轮 400 passed in 32.02s；最终 401 passed in 33.33s，新增 10 项，零失败/零跳过。25 个控制台 JS 的 node --check 通过；完整流程虚拟时间 38 秒，两套累计、急停后冻结、一键清零重跑、非演示确认及拒绝应答均覆盖。未运行 node1.sh、服务、浏览器或其他验收入口，未暂存/提交。
- 验收预期：对照 production-checks.mjs、browser.mjs、surface-checks.mjs、node1.mjs 的实际选择器，第 4、5、6、7、8、11、15 条预计转绿；逐条依据见卡点.md。真实 DOM 几何、鼠标时序、WebGL 及三种分辨率仍待外部运行，未改原验收报告、截图。
- 遗留：本任务无单测失败；外部验收和提交尚未执行。没有开始 T5，也未修改 README、SPEC、旧页面、旧训练、孪生源码、任何 scripts/acceptance 文件。保留并行产生的 deck、设备层任务书及其日志。
- 回滚：本轮开始时 HEAD 为 1873acfa6af2233412691cf55f2ae6b3a14d501b；只反向应用上述 T4 变更、移除本轮新增文件和 T4 文档段。改前受影响跟踪文件从该 HEAD 留存到 /private/tmp/rearm-node1-t4-before；日志另存追加前副本。不要整文件回退其他会话同时追加的日志或文档。


## PPT-ATTENTION-20261115：路演阅读负担优化

- 日期：2026-11-15（Asia/Taipei）
- 目标：按用户说明的观众需求，减少同屏阅读负担，让重点、顺序和数据更容易跟随。
- 改动文件：在线演示稿、`deck/attention-v2/` 备份/修改记录/渲染/检查；更新 `deck/roadshow-v1/presentation.json`；追加日志与索引。
- 关键决策：保留已选视觉和 12 页顺序，缩短长标题与重复说明，固定四个优势的编号；数据页仅保留一组对比。保留单次测试、未夹起、连续实测待积累和标准化交付目标。第 4 页视频框保持 16:9，未嵌入视频。
- 验证：11 个修改页逐张查看，拼版检查；无越界、无可见文字框交叠；图片对象与视频框一致；原生数据回读仍为 13.9 / 5.6 mm；12 页备注保留。原生文本非空白字符减少 32.7%。保存 stateVersion 13。
- 遗留：未做现场 PowerPoint、实际观众或视频播放测试；本次是信息与版式优化，不声称对特定观众的效果已被验证。
- 回滚：`deck/attention-v2/source/apply-session.mjs` 的 restoreFocus 可按本轮备份恢复文字、位置与样式；不影响用户此前删除的脚注。


## PPT-RESTORE-20261115：恢复阅读优化前版本

- 日期：2026-11-15（Asia/Taipei）
- 目标：按用户要求切回上个版本供查看。
- 改动文件：在线演示稿；`deck/restore-v1-20261115/`；两版 presentation.json；追加日志与索引。
- 关键决策：以阅读优化前 stateVersion 9 的元素备份恢复 109 个对象，保留 12 页、第 4 页视频位置及用户此前修改。优化版另行保留。
- 验证：保存 stateVersion 14；全部页面文字、位置、字号、字重、图片与目标备份核对无差异，11 个修改页重新渲染并查看整套拼版。
- 遗留：视频尚未嵌入，未测试现场 PowerPoint 播放。
- 回滚：优化版快照保存在 restore-v1-20261115/backup，仍可使用 attention-v2 的 applyFocus 重新切换；不修改项目其他工作。


## NODE1-T5-20261115：零件库、文档与共用三步训练

- 日期：2026-11-15（Asia/Taipei）。目标：仅完成路演节点① T5；运行完整 pytest 和 node --check，正式验收及提交由外部执行。
- 修改文件：rearm/ui/static/modules/console/pages/parts/index.js；docs/路演/tasks/卡点.md；LOG.md、LOG-INDEX.md 仅追加。
- 新增文件：console/pages/parts/parts.css；views/{part-list,recipe-list,library-list,part-doc,recipe-doc,library-doc,new-flow,identify-step,recipe-fields,training-record,shape,format}.js；console/widgets/line-chart.js；tests/test_console_parts.py。所有新控制台 JS 少于 200 行，没有新增依赖。
- 目标与结构：供操作员查看零件/配方及训练结果，主操作为新增；沿用既有品牌、原生 ES 模块和 T2 数据层。组件为 parts→双分页列表/文档/new-flow；两种文档共用读取与训练记录组件，两种新增共用左侧三步流程，重训从第二步进入。没有全局改版、替换框架、改变协议、跨页导入或移动模块边界。
- 展示：列表提供外形 SVG、名称、编号、版本和收录时间；文档覆盖清单 3.2/3.3，夹持力一位小数，依据使用原 force_basis 字段；配方展示工装、顺序和可打开的零件文档。训练记录包含逐轮偏差、阈值、试抓记录、图像数、用时和成功率；照片缺失时使用轮廓，无录像字段时不创建录像行，提供录像时可播放且默认静音。
- 曲线：从旧 deviation-chart 的线性刻度与 1/2/5 取整规则独立重写，无旧模块 import；SVG 只画线和点，文字使用 HTML 与 --fs-sm，避免随 SVG 缩小。偏差用 --data、阈值用 --warn，同时以实线/虚线及文字区分。
- 流程：拍照识别等待本次 part_candidate，名称编号保持用户输入；配方由 store 的工位和零件选择，支持顺序调整；train_start 后由真实进度消息增长曲线，train_done 才进入“训练完成 · 已收录”。新增零件/配方分别使列表 4→5、1→2；重训传原 draft.id，文档版本 1→2且列表不增加。
- 互斥与错误：复用 trainReason/startReason 和统一 aria-disabled/data-reason，点击前重新读取 store；训练中顶栏显示训练中，生产开始不可用，生产期间训练不可用。主机拒绝、识别中断、急停和重置均不伪造成功；旧候选隔离，暂停 RAF 后仍能按同次完成记录恢复第三步。未更改任何急停、限位、安全实现。
- 视觉与状态自查：用表格和单一详情区避免重复卡片；沿用颜色变量避免装饰色；输入控件和展开依据保持节点以避免高频刷新丢失；滚动限定在页面内部以容纳长文档；曲线文字不放进缩放 SVG。空列表、读取错误/重试、训练拒绝、禁用原因、键盘 tab 切换与焦点样式都有对应处理。实际浏览器渲染未验证。
- 验证：开工 401 passed in 33.74s；最终 413 passed in 37.28s，新增 12 项，零失败/零跳过，原测试未删改。14 个新增/改动 JS 的 node --check 全过。测试使用既有 pytest→node/JSDOM、真实 store/模拟主机和虚拟时间，不启动浏览器或服务。
- 验收对照：逐条核对 library-checks.mjs 的数量、钩子、文档曲线、夹持力格式、名称编号、三步、30 秒完成及同页增量判断，第 13 条预计转绿；其他界面的按钮、措辞、布局规则一并静态核对，但不提前宣称第 9、12、14 条通过。详细选择器映射已追加卡点.md。
- 遗留：没有运行 node1.sh 或其他验收入口，没有实际画面、鼠标时序、三种分辨率及新截图证据；未更新正式报告。训练录像与正式 3D 素材未提供，后端联调仍待后续节点。未开始 T6，没有 git add/commit，没有修改 scripts/acceptance/、旧首页/训练模块、孪生、数据源、README 或 SPEC，保留开工时其他未跟踪文件。
- 回滚：开工 HEAD 为 206feddb16eff00b9477f42c90dad05edf7f7e3d；改前 parts/index.js 和三份文档副本存于 /private/tmp/rearm-node1-t5-before。只恢复本轮 index.js、移除本轮新增 parts 文件/line-chart.js/测试，按段撤销本轮日志及卡点追加；不要整文件覆盖其他会话新增内容。

## NODE1-T6-20261115：记录与只读设置

- 日期：2026-11-15（Asia/Taipei）。目标：仅完成节点① T6，补齐记录、设置两页；正式浏览器验收和提交由外部执行。
- 改动文件：rearm/ui/static/modules/console/pages/records/index.js、records.css；pages/settings/index.js、settings.css；widgets/format.js（上述相对目录均位于 modules/console）；tests/test_console_records_settings.py；docs/路演/tasks/卡点.md；LOG.md、LOG-INDEX.md 仅追加。
- 结构与决策：沿用原生 ES 模块、现有导航和 optional 独立加载。记录页由标题与两张语义表格组成，设置页由只读连接信息与参数组成；复用 frameView、DOM 工具、store 和 selectors，无跨页依赖、网络访问、额外指令或新增依赖。共用格式化工具仅供本次两页使用，不重构其他页面。
- 记录：生产表含时间、配方、结果、偏差、用时；训练表含时间、对象、轮数、最终偏差、用时。仅展示 store 已完成记录，按最新在前显示；零件/配方名称从库或文档解析，未取到名称时保留编号。空表为灰色“还没有生产记录”或“还没有训练记录”；缺测保留“—”。生产、训练完成和重置直接跟随原状态更新，关节消息不重建记录行。
- 设置：读取 hello.sim 显示“本地演示”或“主机”，连接区分未连接、等待握手、协议不兼容、已连接；协议版本和偏差阈值取自 hello，不写死阈值。夹爪开口显示规格规定的“全开”，是只读策略值，不充当实时夹爪读数。没有主机地址输入框或可编辑控件。
- 视觉与状态自查：沿用品牌变量，两个 CSS 均限定各自 data-page；最小新增字级为 --fs-base（13px）。表格内部滚动、长名称换行，避免页面被长记录撑开；使用 textContent 避免名称被解释为 HTML；空值灰色；表格滚动区可键盘聚焦并有焦点框；收到高频遥测时保留阅读位置。实际浏览器画面未验证。
- 验证：开工 .venv/bin/python -m pytest -q 为 413 passed in 36.19s；最终同命令 417 passed in 35.18s，新增 4 项，零失败、零跳过，原测试未删改。两个页面 index.js 和 widgets/format.js 的 node --check 全过。新增测试覆盖完整生产、两类训练、急停中断、重置、迟到名称、缺测、文本安全、只读连接状态及 dispose。
- 验收对照：surface-checks.mjs 的四项 data-nav 顺序及文字不变，browser.mjs 的 data-page 可见且内容非空由原导航测试继续覆盖，第 3 条预计保持绿。第 9、12、14 条仅自查本次两页的按钮/措辞/样式兼容性，不宣称全站已通过；详细对照追加至卡点.md。
- 遗留：未运行 node1.sh、浏览器、服务或其他验收入口；没有三种视口、实际截断/滚动或截图的新证据，正式报告未更新。外部须继续跑验收脚本确认第 3 条及两页实际画面。未修改 scripts/acceptance/、协议、数据源、急停/限位、旧首页、孪生、README 或 SPEC；没有 git add/commit，未开始 T7。
- 回滚：开工 HEAD 为 409bbb8f8eb7beaa11e53437ca21b270d6da4e76。改前两页 index.js 和三份文档副本位于 /private/tmp/rearm-node1-t6-before.BgceSO；只恢复两页 index.js，移除本轮两份 CSS、widgets/format.js 和测试文件，按段撤销本轮文档追加，保留其他会话内容及原有未跟踪文件。


## NODE1-T7-20261115：统一打磨与七项截图反馈修正

- 日期：2026-11-15（Asia/Taipei）。目标：仅完成 T7 与本轮七项补充；正式浏览器验收、截图和提交由外部执行，未开始 T8。
- 决策：延续原生 ES 模块、品牌 tokens、单列步骤与既有数据源；不增加依赖、不换框架、不改协议，不接设备。生产父容器直接分发状态，由叶子视图统一 RAF 合帧；stepper 在所属视图帧内写 DOM，顶栏与步骤同步，保留每帧合并。reduce 拒绝 action/index/part_id 或时序不属于当前 run_state 的 step_state。
- 提示：保留850ms悬停延迟、aria-disabled/help与统一激活拦截；只对键盘 focus-visible 显示焦点提示，鼠标按下/焦点回还不显示；显示4秒自动移除提示与描述关联。定时器、移开、失效和 dispose 清理完整。
- 观察与布局：观察画面占右列全宽；标签按真实尺寸分配上下区域，图形限定中间区，连线对应目标，识别框固定屏幕线宽。空结果显示灰色“尚未检查”。配方标签同行、统计紧凑排列；记录两表并列/内部滚动，设置分上下栅格，文档图形和曲线利用余高。所有字号≥12px token；单列步骤保留。未查看修改后实际渲染。
- 训练：五份历史文档的用时为32:40、40:12、36:50、46:01、47:50，收录时间分别错开，图像按2张/秒累计。现场每1.2秒推进一个画面轮次，每轮训练时钟为5分钟，8轮9.6秒演示完成，训练记录为40:00/4800张。入库直接归档已发进度，避免用墙钟重新计算。文档/记录共用用时格式，小时以上显示h:mm:ss。
- 抓放：第一层接触姿态确定盘面高度；第二层另选限位内朝下姿态，用FK检查5mm公差；工作区按已放零件顶面累加高度。夹持时走既有Three道具层，放下后保持位置，第二件叠在第一件上。没有逆解或孪生源码改动。
- 验收脚本：修改前已在卡点.md说明原因；只收紧library-checks.mjs，文档截图等polyline可见，第13条检查两类文档折线点数≥2，步骤2等至少两轮折线。未调整其他脚本、超时、数量或判断门槛。
- 验证：基线417 passed in 36.33s；第一轮422 passed in 37.76s；最终保留单列步骤并匹配观察纵横比后422 passed in 35.71s。均为 .venv/bin/python -m pytest -q，零失败、零跳过，新增5项。56个控制台/fixtures/mock-console/验收JS与MJS的node --check通过。新增测试覆盖同帧高亮与迟到事件、鼠标/键盘提示及4秒寿命、训练时钟与归档及小时格式、所有预置抓取接触姿态和两次抓放≤5mm、夹持随动与叠放、观察标签边界/互斥/避开图形。原测试只更新0:09、192张及重合位置等已改变语义，精确数值断言保留并加强。
- 验收预期：第9、12、14条预计转绿，第13条收紧后预计仍通过，其余原条目预计保持；17项实际选择器逐条对照记录在docs/路演/tasks/卡点.md。以上不是正式验收结果。
- 遗留：真实浏览器三种尺寸、鼠标焦点行为、WebGL运动画面未验证；按用户要求没有启动浏览器/服务、运行node1.sh、更新验收报告或截图。未git add/commit；旧首页/训练模块、孪生、急停/限位及server.py均无diff；素材包未跟踪，main仍为57785e8f95837f0d2384b4f5968cba225821434c。保留其他会话的PPT和接口材料。
- 回滚：改前文件在/private/tmp/rearm-t7-before/rollback.tar；只提取下列本轮改动的已有文件，移除新增observation-layout.js和test_console_polish.py。LOG/LOG-INDEX/卡点只撤本轮段落，不整文件覆盖并行内容。

改动文件（完整清单）：

- `LOG-INDEX.md`
- `LOG.md`
- `docs/路演/tasks/卡点.md`
- `rearm/ui/static/modules/console/pages/parts/parts.css`
- `rearm/ui/static/modules/console/pages/parts/views/format.js`
- `rearm/ui/static/modules/console/pages/parts/views/library-doc.js`
- `rearm/ui/static/modules/console/pages/parts/views/training-record.js`
- `rearm/ui/static/modules/console/pages/production/index.js`
- `rearm/ui/static/modules/console/pages/production/production.css`
- `rearm/ui/static/modules/console/pages/production/views/observation-layout.js`
- `rearm/ui/static/modules/console/pages/production/views/observe-view.js`
- `rearm/ui/static/modules/console/pages/records/records.css`
- `rearm/ui/static/modules/console/pages/settings/settings.css`
- `rearm/ui/static/modules/console/shell/tooltip.js`
- `rearm/ui/static/modules/console/state/store.js`
- `rearm/ui/static/modules/console/state/workspace.js`
- `rearm/ui/static/modules/console/widgets/format.js`
- `rearm/ui/static/modules/console/widgets/stepper.js`
- `rearm/ui/static/modules/datasource/fixtures/parts.js`
- `rearm/ui/static/modules/datasource/fixtures/poses.js`
- `rearm/ui/static/modules/datasource/fixtures/recipes.js`
- `rearm/ui/static/modules/datasource/fixtures/workspace.js`
- `rearm/ui/static/modules/datasource/mock-console/library.js`
- `rearm/ui/static/modules/datasource/mock-console/production.js`
- `rearm/ui/static/modules/datasource/mock-console/training.js`
- `scripts/acceptance/library-checks.mjs`
- `tests/test_console_data.py`
- `tests/test_console_parts.py`
- `tests/test_console_polish.py`
- `tests/test_console_production.py`
- `tests/test_console_records_settings.py`

## 2026-11-15 现有前端 v1 接口规范与实际交互样例 [FRONTEND-API-SPEC-20261115]
- 目标：交付按现有前端代码核对的接口规范，供后端直接阅读和对照，不混入设备层 v2 方案。
- 改动文件：新增 docs/现有前端接口规范.md；新增 docs/接口样例/控制台-v1/ 下消息样例.json、完整交互.json、核对基线.json；新增 docs/接口样例/现有前端接口包.zip；本日志和索引只追加。
- 基线：HEAD 8e13b36c382378c76bf32d1976fd2f2eb6b302e2，加当前未提交修改；61 个相关文件内容快照和 SHA-256 记录在核对基线.json。离线采样脚本与源码副本放 /private/tmp/rearm-frontend-api-20261115/，未执行真实网络或硬件操作。
- 内容：9 个指令、15 种推送、6 类模拟错误，字段类型/单位/空值、文档与训练结构、生产时序、状态归并和模拟重置；区分已接入 mock 与未加载的现有 host-source 传输实现，明确相机/工作台、缺测、失败、去重及重连的现有限制。
- 关键核对：当前训练每轮画面 1200ms，但每轮上报 300000ms，8轮播完9600ms，上报2400000ms与4800张；规范按代码记录，不沿用旧附录未说明的时间口径。未把模拟参数写成实机测量，未宣称填 backend 地址即可连接。
- 验证：生成并完整回放生产、新增零件、新增配方、重训、错误/急停/重置五场景，最终状态逐项相同；HTTP 适配器地址及请求通过假传输检查；16 个本地引用目标存在、6 段文内 JSON 可解析、消息/指令/错误覆盖通过；4项压缩包逐字节及完整性检查通过。源码与采样基线无变化。初次采样快照缺少纯 FK 依赖，补入临时快照后通过。
- 范围：仅交付规范和样例，没有修改前端代码、正式接口文档、设备配置、README 或 SPEC；没有运行完整应用测试或浏览器，也没有连接真实主机、机械臂和相机。
- 遗留：真实传输入口、真实工位与图像、失败/缺测和恢复语义仍按节点④实施；本轮只说明现状。
- 回滚：删除本轮新增规范、控制台-v1 样例目录和接口包，移除本日志与对应索引行；不覆盖或回退其他会话内容。

## 2026-11-15 路演节点① T7 第二轮局部返工 [NODE1-T7-R2-20261115]
- 目标：仅处理用户追加的五点，保留已验收 T7 主体；本轮最终保留第 1、2、4、5 点，第 3 点按 A.1 两轮失败停止规则回滚。
- 改动文件：rearm/ui/static/modules/datasource/fixtures/poses.js、datasource/mock-console/library.js；modules/console/state/store.js、state/selectors.js、widgets/sparkline.js、pages/production/production.css、pages/settings/settings.css；tests/test_console_data.py、test_console_polish.py、test_console_records_settings.py；docs/路演/tasks/卡点.md；LOG.md、LOG-INDEX.md。
- 决策：folded 使用 [0,0,0,0,0,0]，不改变轨迹时间或安全实现；库摘要从文档带出 training 的 round/deviation_mm/elapsed_ms，store 首次归并留存 archivedTrains，reset_demo 只清本次 trains/runs；设置按内容高度排列；折线改为独立 40px 高度，单值显示圆点与数值。
- 验证：开工 422 passed in 39.33s；两轮观察布局分别 4 failed/419 passed、2 failed/421 passed，失败现象与尝试均写入卡点；回滚失败观察改法后 423 passed in 35.69s。最终 5 个改动 JS 的 node --check 退出码均为 0。关键姿态与完整运动限位、精确插值、5 条初始历史与重置/重连/现场排序、单点和多点图内坐标均有测试。
- 遗留：第 3 点观察画面仍为上一版四角标签和长引线，未完成；实际像素、WebGL、三分辨率均未验证，原验收报告未刷新。原 17 项选择器和判断逐条静态自查见卡点，不宣称浏览器全绿。没有运行 node1.sh、服务、浏览器，没有修改 scripts/acceptance/、git add/commit 或开始下个任务。
- 回滚：本轮开工 HEAD=2c83c8e55d77296f3858081ae4d04a545d7dd8ce；两个原 CSS 保存在 /private/tmp/rearm-t7-r2-backup/。失败观察实现另存该目录 observation-failed/，已从工作树撤回。若回滚保留的四项，仅逆向应用本轮上述源码/测试差异，并移除此日志、索引及卡点本节；保留并行会话的接口文档、样例和 FRONTEND-API-SPEC 日志。

## 2026-11-15 孪生安装台归零，待确认道具与演示姿态同步 [TWIN-PEDESTAL-20261115]
- 目标：移除机械臂脚下安装台，底座、网格与道具共用地面；本轮只完成安装台归零，道具落地尚未完成。
- 改动文件：rearm/ui/static/modules/arm/arm-params.js、tests/test_twin_overlay.py、LOG.md、LOG-INDEX.md。
- 关键决策：pedestalHeight 从 0.20 改为 0，更新配置注释；scene.js 原有 lift > 0 分支会跳过安装台，GridHelper 定位到 Z=0，fallback2d.js 的 fillRect 高度为 0，均无需改实现。保留 cameraTarget 及其余视觉参数，不改运动学、页面或样式。
- 测试调整：旧三轴激光落点断言从 -0.20 改为 0；原测试姿态的出光点 Z=-0.132098 m 已低于新地面，补查其射线隐藏，另取位于地面上方且向下的旧三轴姿态核验落点。
- 验证：指定 pytest 三文件，修改前 48 passed in 1.82s，修改后 48 passed in 1.83s；rg -n -i pedestal tests 仅命中这三文件，无额外命中文件。实际 Three 几何审计确认安装台节点 1→0，网格 Z=-0.20→0，加载官方网格后的底座最低点约 0；相机位置、joint1/tool 投影完全不变。2D 调用记录确认填充高度 0、底座起点与地面线同高。审计结果：/private/tmp/rearm-pedestal-20261115/geometry-audit.json。
- 遗留：WORKSPACE 道具底面在 Z=-0.167619～-0.182619 m，本次归零后仍在地下；接触姿态由 FK 生成且已有抓取对齐回归，不能只平移道具而破坏抓放。已请求用户确认是否同步调整 fixtures/poses.js 与 fixtures/workspace.js 的演示数据，未收到确认，不继续扩大修改。实际画面未验证：启动 127.0.0.1:8017 本地只读静态服务被沙箱以 PermissionError: Operation not permitted 拒绝，未请求权限或绕过限制。
- 回滚：原 arm-params.js、test_twin_overlay.py 已保存至 /private/tmp/rearm-pedestal-20261115/，仅恢复这两个本轮文件即可撤回代码修改；随后移除此日志及对应索引。保留开工时的无关未跟踪文档和素材。未执行 git commit。
- 并行改动：最终只读检查发现 production/views/twin-stage.js 已被另一处修改移除 setProps 调用，另有观察区与生产页测试改动；本轮未触碰或回退这些文件。上述负高度结论针对 WORKSPACE 数据和直接挂载道具的孪生，生产页是否继续显示道具应以用户最终范围为准。

## 2026-11-15 观察画面摄像头接入口 [OBSERVE-CAMERA-20261115]
- 目标：在生产页观察 SVG 下接入 URL 或 MediaStream，保留原识别框、引线与标签。
- 改动文件：rearm/ui/static/modules/console/pages/production/views/observe-view.js、rearm/ui/static/modules/console/pages/production/production.css、tests/test_console_camera.py；LOG.md、LOG-INDEX.md 仅追加本节。
- 接口：observe-view.mount(root) 返回的 view.setCameraSource(source) 接受 null、URL 字符串、{url,type} 或 MediaStream；启动时读取 ?camera=<编码后的 URL>，之后 render 不覆盖调用方设置。URL pathname 的 jpg/jpeg/mjpg/mjpeg 扩展名使用 img；显式 type 支持 img/image/mjpeg/jpeg、image/* 和 multipart/x-mixed-replace，其余走 video。video 静音自动播放、playsInline，MediaStream 绑定 srcObject；HLS 使用浏览器原生能力，未新增播放器依赖。
- 行为：无来源显示“未接入摄像头”；等待首个 img load/video loadeddata 时显示“摄像头连接中”，保留示意图；成功仅隐藏 objects 组；error 解绑媒体、恢复示意图并显示“摄像头连接失败”。切源、断开和 dispose 清除事件、URL、视频播放与 srcObject，不停止调用方拥有的 tracks；旧来源回调不可改变当前状态。
- 排版：媒体在 SVG 和标签下方，沿用现有 imageTransform 的图像区域，object-fit: contain；角标使用 --mute、--video、--fs-sm、--sp-1，排版给角标预留高度，未新增硬编码颜色或更改原标签算法。
- 验证：新增 5 项 Node/JSDOM 测试覆盖无来源、MJPEG、视频、显式类型、URL 默认源、查询参数不干扰扩展名、MediaStream、成功/失败/断开、旧事件、dispose 和媒体/识别框坐标一致。最终 .venv/bin/pytest -q tests/test_console_camera.py tests/test_console_data.py tests/test_console_polish.py tests/test_console_production.py tests/test_console_shell.py：56 passed in 13.20s；node --check observe-view.js 和 git diff --check 通过。补跑首轮发现角标 --fs-xs 违反现有最小字号断言，已改用 --fs-sm，未放宽测试。
- 遗留：实际浏览器画面、真实摄像头、真实视频/HLS 播放均未验证；Playwright CLI 未缓存，离线调用 ENOTCACHED；启动 127.0.0.1:8765 只读静态服务被环境以 PermissionError: Operation not permitted 拒绝，未申请权限或绕过限制。手动验收：打开 /?camera=%2Fapi%2Fcamera.mjpg，确认画面与识别标注；改用不可达来源确认失败回退；调用 setCameraSource(null) 确认恢复未接入标记。
- 回滚：修改前 observe-view.js、production.css 和日志副本保存在 /private/tmp/rearm-camera-feed-before-20261115/；仅撤回本轮两个源码文件差异、删除新增测试和本日志/索引段，保留其他会话后续变更。未修改 twin-stage.js、twin/、arm-params.js、scene.js、workspace 数据层或已有测试；工作树内这些文件和日志的并行变更均保留。未执行 git commit。

## CONSOLE-VISUAL-SHELL-20261115：工业仪表外壳与通用组件

- 日期：2026-11-15（Asia/Taipei）。目标：实现《控制台视觉改版规范》第二、三节；先完整阅读规范及旧版 app.css、theme.css、tokens.css，再核对顶栏、导航、急停、重置、对话框、tooltip 选择器断言。
- 改动文件：rearm/ui/static/modules/console/console.css、rearm/ui/static/modules/console/shell/topbar.js、tests/test_console_shell.py；本日志和 LOG-INDEX.md 仅追加。未编辑 pages/、twin/、arm/、tokens.css、app.css、index.html，保留开工时已有改动；未 git commit。
- 外壳：文字品牌与副标题、7px 连接点、已有 hello.sim 数据来源、低调状态 pill、下划线导航、32px 普通按钮及最小 40px 实底急停。连接展示复用 online selector，区分未连接、等待握手、协议不兼容；缺字段不补数据。重置/急停事件、顺序、状态更新与焦点逻辑不变。
- 容器：页面透明网格，padding 为 12px 16px；桌面在内容区内部滚动，≤1080 允许页面滚动，≤720 顶栏两行。页面卡片底色由后续页面任务套用，未代改各页布局。
- 通用类与使用：c-card 包 c-card-head / c-card-body，标题右侧 c-aside；c-kpis 直接放 c-kpi，内用 c-kpi-label/value/note（兼容 k/v/d，空值由视图写“—”）；c-viewport 带四角取景线，c-chip 加 tl/tr/bl/br 定位和 ok/busy/bad 状态；table.c-table 的数字列 num/r、当前行 cur 或 aria-current=true、选中行 aria-selected=true；c-tag 加 ok/bad/cur；c-btn 加 primary；c-tabs 的子 button/a 用 on 或既有 aria 选中；c-empty 空态、pill 简短状态。每组规则就近提供用法注释。
- 浮层：dialog/tooltip 使用 token 圆角及规范阴影，遮罩使用规定 rgba，无模糊；既有原生 dialog、键盘焦点圈、禁用提示定时和指令拦截逻辑未变。
- 测试调整：图片 Logo 断言按新规范改为文字品牌/副标题；原来一律禁止像素、角标渐变和阴影的旧断言改为禁止新增 hex/rgb/hsl、仅允许规范三个 rgba 并核对所有 CSS 变量来自 tokens。保留所有交互断言，新增连接/握手/协议/来源缺失及旧文字清理的回归。
- 验证：改动前指定命令为 143 passed, 285 deselected in 21.39s；改动后 `.venv/bin/pytest -q tests/ -k 'console or twin or panel'` 为 144 passed, 285 deselected in 21.17s。topbar.js 的 node --check 及 git diff --check 通过。
- 遗留：三视口实际渲染未验证。Playwright wrapper 离线查 npm 元数据返回 ENOTCACHED；已确认本地 CLI 可用。随后启动只服务本地静态文件的 127.0.0.1:8026 HTTP 服务时，沙箱对 socket.bind 返回 PermissionError: [Errno 1] Operation not permitted；未请求提权、未换端口或绕过限制，未宣称截图验收通过。需后续浏览器核对 1440×900、1280×720、390×844 的排版及原生 dialog/tooltip。
- 回滚：开工备份位于 /var/folders/wb/6hqw8dgs6m5bd73_t19nl8100000gn/T/rearm-console-shell-zc6x76rl/。可只恢复本条列出的三个代码/测试文件；日志只删除本条与对应索引行，不整份覆盖，避免覆盖并发记录。


## CONSOLE-VISUAL-RECORDS-SETTINGS-20261115：记录与设置仪表卡片

- 日期：2026-11-15（Asia/Taipei）。目标：按《控制台视觉改版规范》第四节记录/设置和第五节页面动效，对齐旧版面板；已完整读取规范、旧 index.html、app.css、theme.css，并先检索 tests/ 的本页选择器与断言。
- 改动文件：rearm/ui/static/modules/console/pages/records/index.js、records.css；rearm/ui/static/modules/console/pages/settings/index.js、settings.css；LOG.md 与 LOG-INDEX.md 仅追加。未编辑 console.css、shell/、main.js、console.html、tokens.css、twin/、arm/、其他页面或测试；未 git commit。
- 记录页：保留页标题，两张并排 c-card 表格卡使用 c-card-head 空心方块标题和 c-aside 条数；c-table 数字列等宽右对齐、结果 c-tag、粘性表头、区域内部滚动。顶部 c-kpis 四格显示完成套数、到位率、平均偏差、训练记录。只从原 selectors 返回的记录计算展示值：到位率仅以 boolean 结果为分母，平均值仅纳入有限且非负的生产偏差；空分母显示“—”，训练条数包含归档记录。不修改 store、selector、指令、订阅或既有记录刷新判断。
- 设置页：连接、参数两张 c-card，dl 键值行采用小标签与等宽值；状态沿用 data-online，以 7px 圆点加原状态文字呈现，已连接只把圆点变绿；页标题旁的“只读”使用 pill。所有原 data-*、aria-*、role、字段文案及表头保留，无新增可编辑控件。
- 布局：桌面记录页为标题、KPI、双卡三行网格；设置页为标题和双卡；≤1080px 单列，记录表滚动区限制为 60dvh，≤720px 收紧表格横向留白。引用已有 c- 组件，新增 CSS 均限定本页 data-page，页面类和 keyframes 使用 records-/settings- 前缀，颜色/字体/间距/圆角仅引用 tokens。
- 动效：卡片 320ms 淡入上移 6px、第二张延迟 40ms；表格行/键值行 120ms hover 过渡；KPI 仅在显示值变化时替换数值节点，触发 sub→data 的 320ms 高亮，不增加计时器；连接圆点 200ms 颜色过渡。时长/曲线使用带默认值的 var()，prefers-reduced-motion 下禁用两页全部动画、过渡和滚动动效。本页无步骤、画面区或对话框，没有添加不属于本页的动效。
- 验证：开工 `.venv/bin/pytest -q tests/ -k console` 为 81 passed, 348 deselected in 20.69s。修改后首次全组遇到并发生产页缺少 stage-chips.js，23 failed/58 passed；未触碰其他页面，待文件出现后再次执行相同筛选，最终 81 passed, 348 deselected in 17.50s（输出 /private/tmp/rearm-records-settings-console-pytest.txt）。本页独立测试 4 passed in 1.93s。额外复用 JSDOM 宿主验证空数据、缺测/负值剔除、已知结果分母、归档数量、节点不变性、只读和零指令；两份 JS 的 node --check、限定范围 git diff --check、颜色 token/动效 fallback 静态核对通过。
- 遗留：实际渲染未验证。Playwright 默认浏览器版本 1254 不在本机，改用已存在的 chromium_headless_shell-1234 后，启动被沙箱拒绝（bootstrap_check_in MachPortRendezvousServer: Permission denied (1100)）。未请求提权或继续绕过；没有三视口截图或实际动效/溢出验收结论。后续在 1440×900、1280×720、390×844 切换记录/设置核对长表内部滚动、文字完整和减少动效模式。
- 回滚：四个页面文件的原始副本保存在 /var/folders/wb/6hqw8dgs6m5bd73_t19nl8100000gn/T/rearm-records-settings-before-k_z_8nyf/，内含 records/、settings/。仅逐文件恢复这两个目录；日志仅撤销本条及对应索引，不覆盖其他会话内容。


## CONSOLE-VISUAL-PARTS-20261115：零件库工业仪表样式与页面动效

- 日期：2026-11-15（Asia/Taipei）。目标：按《控制台视觉改版规范》第四节零件库及第五节页面动效对齐旧版面板；已完整阅读规范、index.html、app.css、theme.css，改前核对 tests/ 的零件库选择器。
- 修改文件：rearm/ui/static/modules/console/pages/parts/{index.js,parts.css}；其 views/{format,identify-step,library-doc,library-list,new-flow,part-doc,recipe-doc,training-record}.js。本日志与 LOG-INDEX.md 仅追加；未修改 console.css、shell/、main.js、console.html、tokens.css、twin/、arm/、其他页面、测试或 README/SPEC；保留并发任务已有修改，未 git commit。
- 布局：顶部文字 tab 与滑动底线、右侧新增；左列表 c-card/c-table，名称按钮的透明伪元素覆盖整行，仍触发原按钮事件；28px 线框缩略图、mono 编号/版本/时间、选中行左侧 2px 线；右侧文档卡含轮廓角标、文档属性、训练 KPI 细线格、曲线与试抓标签，未选择显示空态；识别预览尺寸沿用已有文案并套 c-chip；三步新增沿用 stepper，改为旧版 steps 横排细框。桌面内容区内部滚动；≤1080 单列、≤720 列表紧凑重排。
- 边界决策：不改原 mode、hidden、事件、命令、状态机或数据流；用本页 CSS 在文档模式下显示原列表及新增按钮，实现左右并排，所有原 data-*、aria-*、role、文案和选择器保留。新增的 data-library-* 与 class 仅表达选中状态；训练 KPI 动效在持久容器上交替 class，只在展示值变化时触发，避免原有重复渲染截断或反复播放动画。
- 动效：卡片 320ms 淡入上移 6px，右卡延迟 40ms；tab 底线 200ms；按钮/行 hover 120ms、按压位移；选中线 120ms、详情内容 120ms 淡入；数值 320ms 高亮；当前步骤线向下展开 200ms、完成勾淡入；取景角标从中心到四角。全 CSS，时长曲线 var 带默认值，prefers-reduced-motion 下关闭。页面没有可沿用的 busy 画面状态，未伪造扫描或状态点。
- 验证：改前 console 基线 81 passed / 348 deselected；最终 `.venv/bin/pytest -q tests/ -k console` 为 86 passed / 348 deselected（17.72s，新增外壳测试由并发任务提供），其中本页 12 项通过。14 个本页 JavaScript 文件 node --check 通过；展示探针验证选中行切换、tab、相同 KPI 值不重启动效及值变化重启；颜色/字体/间距等变量均来自 tokens，动效变量带 fallback；git diff --check 通过。
- 遗留：1440×900、1280×720、390×844 实际画面和真实点击区域未验证。Playwright wrapper 离线缓存不足；本地 HTTP 在命令环境不可达；浏览器 host 不可用且 CUA 返回未获准使用 Google Chrome，未申请权限或继续尝试绕过。以上测试不等同截图验收。
- 回滚：修改前 parts/ 完整副本位于 /tmp/rearm-parts-visual-20261115/before。只恢复上述 10 个页面文件，恢复前先确认没有后续零件库改动；不要回退共享目录或整份日志。

## 2026-11-15 生产页对齐旧版工业仪表布局 [CONSOLE-VISUAL-PRODUCTION-20261115]

- 目标：按 docs/控制台视觉改版规范.md 第四节生产及第五节动效，对齐旧版 index.html、app.css、theme.css 的 row1 画面加右侧栏结构。开工先完整阅读上述文件，并检索 tests/ 的生产、摄像头、孪生及打磨选择器。
- 改动文件：production/index.js、production/production.css、production/views/key-number.js、observe-view.js、recipe-pick.js、steps.js；新增 production/production-motion.css、production/views/stage-chips.js。LOG.md、LOG-INDEX.md 仅追加。未改测试、console.css、shell/、main.js、console.html、tokens.css、twin/、arm/ 或其他页面。
- 布局：左侧约 60% 为 c-card / c-viewport 孪生宿主，四角 c-chip 展示当前状态、所选配方、数据来源、当前步骤，保留拖动/缩放/双击复位提示。右侧依次是 c-kpis 四格、配方卡、步骤卡和观察卡；配方选择及开始按钮同行，步骤序号等宽、状态点和当前行左侧细线，观察卡底部保留检查结果。桌面通过内容区及步骤卡内部滚动约束一屏；≤1080 单列、≤720 KPI 两列。
- 数据与接口：只增加视图绑定及 CSS 状态属性；KPI 使用原完成套数、一次通过率、最后记录偏差和 duration_ms，第四格明确为“最近一套用时”，无数据为“—”，不从时钟推算本套用时。原偏差趋势继续使用原 sparkline。生产指令、确认/禁用逻辑、事件、状态归并均未改；摄像头 setCameraSource、?camera=、MediaStream/URL 生命周期、媒体与识别框坐标算法完整保留。twin-stage.js 与 observation-layout.js 和开工备份字节一致，没有恢复 setProps 或道具渲染。
- 动效：生产页自身的 CSS 文件负责五块依次淡入上移、按钮/行 hover、按压、数值变化高亮、步骤左线长出、完成勾淡入、进行中状态点 pulse、角标收拢、busy 顶部扫描及 chip 文本淡出淡入。数值/文本仅在展示内容变化时切换 data-flash，不增加定时器。所有时长/曲线引用 --t-* / --ease-* 并有默认值；prefers-reduced-motion 全关闭。结构 CSS 与 keyframes 分开，沿用现有结构样式作用域测试；两份 CSS 的颜色与设计变量均经 tokens 集合核对，没有硬编码新颜色。
- 验证：开工 `.venv/bin/pytest -q tests/ -k console` 为 81 passed, 348 deselected；最终相同命令为 86 passed, 348 deselected in 17.67s，增加的测试来自并发外壳任务，本轮未改测试。额外临时 Node/JSDOM 检查四卡四格、chip/配方/当前步骤、两次生产数值变化、0.4 mm 与 0:32、急停/重置/训练状态及样式清理均通过；8 个生产 JS 文件的 node --check、CSS token 静态核对和 git diff --check 通过。最终测试输出保存在 /private/tmp/rearm-production-visual-z553pyu4/pytest-console-final.txt。
- 实际画面未验证：已有 8001 服务可读取页面，但 Playwright CLI 写入系统缓存被 EPERM 拒绝；项目既有 playwright-core 启动 Chromium 又被 macOS bootstrap_check_in Permission denied 拒绝；内置浏览器返回 browser access host unavailable。未提权、未修改系统或权限、未连接硬件，未生成截图。1440×900、1280×720、390×844 的像素排版、真实视频播放及浏览器动效仍需手动核对。
- 回滚：开工原文件及本轮 after 快照位于 /private/tmp/rearm-production-visual-z553pyu4/；production-visual.patch 只包含本轮 8 个生产文件的差异，可在确认没有后续冲突时反向应用。不要覆盖整份并发日志，仅移除此节及对应索引行。未 git commit。
- 唯一 HASH：e6e92123fb793807。


## 2026-11-15 观察标签内缩与孪生默认构图 [PRODUCTION-FRAMING-20261115]

- 目标：观察标签避开取景角标，摄像头状态不与标签重叠；只通过 cameraTarget / cameraDistance 调整孪生构图，不改业务逻辑、不提交 commit。
- 改动文件：production/views/observation-layout.js、production/views/observe-view.js、production/production.css、arm/arm-params.js；tests/test_console_production.py、test_console_polish.py、test_console_camera.py、test_twin_overlay.py；LOG.md 和 LOG-INDEX.md 仅追加。
- 标签：外边距从 4px 改为 24px，保留 4px 标签间距；CSS 的两列最大宽度同步扣除 24px 两侧边距和中缝。摄像头状态使用 c-chip 基础样式，文字/边框降为 mute/line，置底居中；沿用原有实测状态高度预留机制，不改媒体或事件逻辑。观察卡最小行高 14rem→17rem，补偿新增边距与 chip 高度，避免矮屏挤没图像区。
- 相机：cameraTarget [0.20, 0, 0.20]→[0.06, 0, 0.18] m；cameraDistance 2.05→1.45 m。方位角 -62°、仰角 16°和其余参数完全保留。折叠姿态模型本身低矮，同一固定镜头下高度约为观察姿态的六成，无法两者同时达到 55%–65%；已通过异步问题说明两种取舍，用户未回复时按已说明的推荐项实施，观察约 65%、折叠约 40%，不扩大为动态镜头。
- 投影核对：复用现有 SCENE_HOST，加载真实 b601 / 自制夹指网格与传感器，保留真实 Three 几何、FK、相机投影，仅替换 GPU 宿主。800×700、1000×900、700×580 的观察/折叠占高分别 64.98%/39.62%，中心横向约 54%/45%，纵向约 44%/56%；350×400 为 56.45%/34.42%，两态全部顶点均在画幅内。结果保存在 /var/folders/wb/6hqw8dgs6m5bd73_t19nl8100000gn/T/rearm-framing-before-mooacvdu/projection-audit.json，投影计算不等同截图验收。
- 测试调整：观察测试同步新内边距、两列宽度和状态区高度；多行标签样本高度增加 40px 保持原图像可用高度；原孪生复位距离断言从 2.05 改为 1.45，夹爪视角 0.45 不变。首轮局部测试 2 项失败，原因是新增几何断言在 frameView 的下一帧布局前检查；在布局检查前推进既有虚拟时钟 16ms，未改变生产代码的事件逻辑或放宽避让断言。
- 验证：`.venv/bin/pytest -q tests/ -k 'console or twin or arm'` 为 148 passed, 286 deselected in 21.82s。三份修改 JS 的 node --check 与 git diff --check 通过。
- 遗留：实际渲染未验证。CUA 返回 browser access host unavailable；Playwright wrapper 离线缓存缺失 ENOTCACHED；复用仓库已有 playwright-core 与已安装 Chromium 启动时被 macOS bootstrap_check_in Permission denied (1100) 拒绝。未提权、未修改权限；错误保存在 /var/folders/wb/6hqw8dgs6m5bd73_t19nl8100000gn/T/rearm-framing-before-mooacvdu/browser-check-error.txt。用户刷新生产页后核对折叠/观察姿态，以及未接入/连接失败两种状态下标签与角标的位置。
- 回滚：开工文件副本及 after 快照位于 /var/folders/wb/6hqw8dgs6m5bd73_t19nl8100000gn/T/rearm-framing-before-mooacvdu/，本轮八个源文件/测试的独立差异为 framing.patch；核对后可反向应用，仅删除本日志节和对应索引，保留原有未提交修改。未改 README 或需求文件。
- 唯一 HASH：9b39b61f6ce40ccd。
