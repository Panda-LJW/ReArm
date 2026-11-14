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
