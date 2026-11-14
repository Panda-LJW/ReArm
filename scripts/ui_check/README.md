# 面板界面验收脚本

这些脚本用无头浏览器打开面板，截图并量出字号、溢出等指标。夜间无人值守改动时的验收就是用它们做的。
只访问本机 `127.0.0.1`，不连接任何硬件。

依赖：Node 18+、`playwright-core`（脚本会在 `~/.npm/_npx/*/node_modules` 里找）、一个 Chromium 可执行文件
（例如 `~/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell`）。

```bash
# 1. 起一个独立的仿真服务（端口 8013，数据放临时目录，不影响 8000 上的面板）
scripts/ui_check/serve.sh "$PWD" 8013 /tmp/rearm-ui-check &
# 2. 造一份演示数据：首次标定、补偿重训、几次注入伤与自愈
.venv/bin/python scripts/ui_check/seed.py http://127.0.0.1:8013
# 3. 截图并输出指标
CH=<chromium 可执行文件路径>
node scripts/ui_check/shots.mjs out "$CH" http://127.0.0.1:8013 normal "" 1920x1080,1280x720 home,overview
node scripts/ui_check/shots.mjs out "$CH" http://127.0.0.1:8013 show "mode=show" 1920x1080,1280x720 home,overview,codes
```

| 脚本 | 检查什么 |
|---|---|
| `shots.mjs` | 各页面截图；最小字号、小于 18px 的元素清单、页面是否滚动、文字是否被截断、卡片内容是否溢出 |
| `interact.mjs` | 版本下拉、版本详情、确认框是否在视口内；路演开关往返；逐个屏蔽可选模块后主面板是否照常 |
| `phases.mjs` | 正常、自愈中、已急停三种阶段的截图；急停按钮是否始终可点 |
| `twinshots.mjs` | 孪生单独演示页，按五组关节角截图，核对显示角度与输入一致，并检查离线提示 |
| `device.mjs` | 配合 `scripts/mock_device.py`，验证下位机数据源驱动孪生及断线后转离线 |

路演模式的通过标准：`minFont` ≥ 18、`pageScroll`/`hOverflow` 为 false、`clipped` 与 `clippedCards` 为空。
