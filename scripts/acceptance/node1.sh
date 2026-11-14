#!/bin/bash
# 节点①唯一入口；不安装依赖，不换端口，不连接真机。
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1
OUT="$ROOT/docs/路演/验收/节点1"
mkdir -p "$OUT/screenshots"
SERVER_PID=""
cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

.venv/bin/python -m pytest -q >"$OUT/pytest.log" 2>&1
export REARM_PYTEST_EXIT=$?
cat "$OUT/pytest.log"
export REARM_PYTEST_PASSED
REARM_PYTEST_PASSED=$(.venv/bin/python - "$OUT/pytest.log" <<'PY'
import pathlib, re, sys
text = pathlib.Path(sys.argv[1]).read_text()
counts = re.findall(r"\b(\d+) passed\b", text)
print(counts[-1] if counts else 0)
PY
)

DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rearm-node1.XXXXXX")" || exit 1
export REARM_ACCEPTANCE_DATA_DIR="$DATA_DIR"
# 与 ui_check/serve.sh 一样在组装入口注入本机端口，打开 info 日志以确认是本次进程监听成功。
.venv/bin/python - "$DATA_DIR" >"$OUT/server.log" 2>&1 <<'PY' &
import sys, uvicorn
original = uvicorn.run
uvicorn.run = lambda app, **kwargs: original(app, host='127.0.0.1', port=8031, log_level='info')
sys.argv = ['node1', '--sim', '--nongeometric', '--data-dir', sys.argv[1]]
from rearm.app import serve_ui
serve_ui()
PY
SERVER_PID=$!
# 只探测本次服务；退出、绑定错误、超时都报告失败，不使用现存服务代替。
.venv/bin/python - "$SERVER_PID" "$OUT/server.log" <<'PY'
import os, pathlib, sys, time, urllib.request
pid, log = int(sys.argv[1]), pathlib.Path(sys.argv[2])
for _ in range(200):
    text = log.read_text()
    if "ERROR:" in text or "Traceback" in text:
        print(text, file=sys.stderr)
        sys.exit(1)
    if "Uvicorn running on http://127.0.0.1:8031" not in text:
        time.sleep(0.1)
        continue
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        print("8031 临时服务提前退出：\n" + text, file=sys.stderr)
        sys.exit(1)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8031/", timeout=0.2) as response:
            if response.status == 200:
                # 给本次子进程完成 bind 的机会，避免误用端口上的旧服务。
                time.sleep(0.2)
                if "ERROR:" not in log.read_text():
                    os.kill(pid, 0)
                    sys.exit(0)
    except (OSError, TimeoutError):
        pass
    time.sleep(0.1)
print("8031 临时服务在 20 秒内未就绪", file=sys.stderr)
sys.exit(1)
PY
READY=$?
export REARM_SERVER_READY="$READY"
if [[ "$READY" != 0 ]]; then
  echo '8031 启动失败：停止浏览器验收，仅生成失败报告和只读仓库检查。' >&2
fi
node scripts/acceptance/node1.mjs
RESULT=$?
if [[ "$RESULT" == 0 ]]; then
  open "$OUT/报告.md" || exit 1
fi
exit "$RESULT"
