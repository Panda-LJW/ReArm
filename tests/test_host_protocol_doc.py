"""主机 v1 文档契约：合法示例、面板字段和实际 mock 消息，禁止连接设备。"""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from test_trainer_views import USED_FIELDS


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "rearm/ui/static/modules"
DOC = (ROOT / "docs/接口文档.md").read_text(encoding="utf-8")
MESSAGES = (
    "hello", "joint_state", "demo_trajectory", "node_result", "pass_result",
    "correction", "laser_state", "event", "heartbeat", "error",
)
COMMANDS = (
    "demo_start", "demo_stop", "practice_start", "practice_stop", "estop",
    "reset_estop", "mark_node", "laser_on", "laser_renew", "laser_off",
)


def section(heading, level=2):
    match = re.search(
        rf"^{re.escape('#' * level + ' ' + heading)}[^\n]*\n"
        rf"(.*?)(?=^#{{1,{level}}} |\Z)", DOC, re.MULTILINE | re.DOTALL,
    )
    assert match, f"缺少章节：{heading}"
    return match.group(1)


def reject_constant(value):
    raise AssertionError(f"JSON 不允许非有限数值：{value}")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f"JSON 存在重复键：{key}"
        result[key] = value
    return result


def examples(text=DOC):
    blocks = re.findall(r"^```json\s*\n(.*?)^```\s*$", text, re.MULTILINE | re.DOTALL)
    return [json.loads(block, parse_constant=reject_constant, object_pairs_hook=unique_object)
            for block in blocks]


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def table_fields(text):
    """只认字段表首列，避免字段仅在示例或别处偶然出现也算已说明。"""
    return {field for line in text.splitlines() if line.startswith("|")
            for field in re.findall(r"`([^`]+)`", line.split("|")[1])}


def table_rows(text):
    return [[cell.strip() for cell in line.strip("|").split("|")]
            for line in text.splitlines() if line.startswith("|")]


def test_host_doc_json_examples_are_valid_and_have_six_axis_arrays():
    blocks = examples()
    assert len(blocks) >= len(MESSAGES) + 2 * len(COMMANDS)
    # 防止语言标签或未闭合的代码围栏使坏示例逃过 JSON 提取。
    assert len(blocks) == len(re.findall(r"^```json\b", DOC, re.MULTILINE))
    assert len(re.findall(r"^```", DOC, re.MULTILINE)) % 2 == 0
    for index, block in enumerate(blocks, 1):
        assert isinstance(block, dict), f"示例 {index} 必须为对象"
        for obj in walk(block):
            if "type" in obj:
                assert {"v", "seq", "t"} <= obj.keys(), (index, obj)
                assert obj["v"] == 1 and obj["type"] in MESSAGES
            if "cmd" in obj:
                assert {"v", "seq", "t"} <= obj.keys(), (index, obj)
                assert obj["v"] == 1 and obj["cmd"] in COMMANDS
            if "seq" in obj:
                assert type(obj["seq"]) is int and 1 <= obj["seq"] <= 9007199254740991
            if "t" in obj:
                assert type(obj["t"]) is int and 10**12 <= obj["t"] < 10**13, (index, obj)
            for field in ("q", "dq", "current", "temp", "valid"):
                if field not in obj:
                    continue
                value = obj[field]
                if field == "valid" and obj.get("type") == "node_result":
                    assert type(value) is bool, "node_result.valid 是标量布尔值"
                    continue
                assert isinstance(value, list) and len(value) == 6, (index, field, value)
                assert all(type(v) is bool for v in value) if field == "valid" else all(
                    v is None or type(v) in (int, float) for v in value
                ), (index, field, value)
            for field in ("spot_base_mm", "ref_spot_base_mm", "dev_mm", "end_base_mm"):
                if obj.get(field) is not None:
                    assert len(obj[field]) == 3, (index, field)
            for field in ("spot_px", "ref_spot_px"):
                if obj.get(field) is not None:
                    assert len(obj[field]) == 2, (index, field)
            if obj.get("type") == "node_result" and obj["valid"]:
                delta = [a - b for a, b in zip(obj["spot_base_mm"], obj["ref_spot_base_mm"])]
                assert obj["dev_mm"] == pytest.approx(delta)
                assert obj["dev_norm_mm"] == pytest.approx(sum(v * v for v in delta) ** 0.5)


@pytest.mark.parametrize("message", MESSAGES)
def test_every_message_has_field_table_and_its_own_example(message):
    text = section(f"5.{MESSAGES.index(message) + 1} `{message}`", level=3)
    assert f"`{message}`" in DOC
    assert any(block.get("type") == message for block in examples(text)), message
    assert "| 名称 | 类型 | 单位 | 取值范围 | 是否必填 | 说明 |" in text


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_has_matching_request_response_and_conditions(command):
    text = section(f"6.{COMMANDS.index(command) + 2} `{command}`", level=3)
    assert f"`{command}`" in DOC and "前置条件" in text
    blocks = examples(text)
    requests = [obj for obj in blocks if obj.get("cmd") == command]
    responses = [obj for obj in blocks if "ok" in obj]
    assert requests and responses, command
    for request in requests:
        response = next(obj for obj in responses if obj["seq"] == request["seq"])
        assert {"v", "ok", "code", "msg", "seq"} <= response.keys()
        assert response["v"] == 1 and type(response["ok"]) is bool
        assert isinstance(response["code"], str) and isinstance(response["msg"], str)
    # 预留命令不能用一个虚假的成功应答冒充支持。
    assert responses[0]["ok"] is (command != "mark_node")
    if command == "mark_node":
        assert responses[0]["code"] == "unsupported"


def test_host_doc_covers_all_manifest_fields():
    missing = sorted(field for field in USED_FIELDS if f"`{field}`" not in DOC)
    assert not missing, f"文档缺少面板字段：{missing}"


@pytest.fixture(scope="module")
def runtime_protocol():
    executable = shutil.which("node")
    if executable is None:
        pytest.skip("node not installed")
    script = r'''
import assert from "node:assert/strict";
import { createMockHost } from "./datasource/mock-host.js";
import { createHostSource } from "./datasource/host-source.js";
import { ARM_PARAMS } from "./arm/arm-params.js";

let realConnections = 0;
globalThis.WebSocket = class { constructor() { realConnections++; throw Error("禁止真实连接"); } };
globalThis.fetch = () => { realConnections++; throw Error("禁止真实请求"); };
const messages = [], replies = [], pending = [], measured = new Set();
const host = createMockHost({now: () => 1794614400000, setTimer: () => 0, clearTimer: () => {}});
async function send(cmd, args) {
  const reply = await host.send(cmd, args);
  replies.push(reply);
  return reply;
}
host.subscribe(message => {
  messages.push(message);
  // 只为采集协议字段驱动开关；不依赖 DOM、实际时间或真实激光。
  if (message.type === "joint_state" && message.mode === "practice" && message.settled) {
    const key = `${message.pass}:${message.node}`;
    if (!measured.has(key)) {
      measured.add(key);
      pending.push(send("laser_on", {ttl_ms: 3000}));
    }
  }
  if (message.type === "node_result") pending.push(send("laser_off"));
});

assert.equal((await send("demo_start")).code, "offline");
host.start();
assert.equal((await send("practice_start")).code, "no_demo");
assert.equal((await send("mark_node")).code, "unsupported");
assert.equal((await send("unknown_for_protocol_test")).code, "unknown_command");
assert.equal((await send("laser_on", {ttl_ms: 0})).code, "ttl");
assert.equal((await send("laser_renew", {ttl_ms: 3000})).code, "laser_off");
await send("laser_on", {ttl_ms: 3000});
await send("laser_renew", {ttl_ms: 3000});
await send("laser_off");
await send("demo_start");
assert.equal((await send("practice_start")).code, "busy");
host.advance(6500);
assert.equal(messages.filter(m => m.type === "demo_trajectory").length, 0);
await send("demo_stop");
await send("practice_start");
for (let elapsed = 0; !messages.some(m => m.type === "correction"); elapsed += 50) {
  assert.ok(elapsed < 20000, "一遍模拟练习未在虚拟时间预算内完成");
  host.advance(50);
}
await send("practice_stop");
await Promise.all(pending);
await send("estop");
assert.equal((await send("laser_off")).code, "estop");
await send("reset_estop");
host.stop();

// network 来自传输适配器，不是 mock 的业务错误；只注入失败 fetch，不启动连接。
const fakeSource = createHostSource({url: "ws://example.invalid/never-opened",
  WebSocketImpl: globalThis.WebSocket, fetchImpl: async () => { throw Error("模拟网络失败"); }});
const networkReply = await fakeSource.send("demo_start");
assert.equal(networkReply.code, "network");
assert.equal(realConnections, 0);

assert.equal(messages.filter(m => m.type === "pass_result").length, 1);
const results = messages.filter(m => m.type === "node_result");
assert.equal(results.length, 4);
assert.ok(results.every(m => m.valid));
assert.ok(messages.some(m => m.type === "correction" && m.applied));
const keys = {};
for (const message of messages) {
  keys[message.type] ??= new Set();
  for (const key of Object.keys(message)) keys[message.type].add(key);
}
console.log(JSON.stringify({
  keys: Object.fromEntries(Object.entries(keys).map(([type, fields]) => [type, [...fields].sort()])),
  errors: [...new Set(replies.filter(r => !r.ok).map(r => r.code))].sort(),
  network: networkReply.code,
  commands: [...new Set(host.commands().map(r => r.cmd))],
  joints: ARM_PARAMS.joints.map(({id, label, limit}) => ({id, label, limit})),
  opening: ARM_PARAMS.gripper.openingMm,
}));
'''
    run = subprocess.run([executable, "--input-type=module", "-e", script], cwd=MODULES,
                         capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_mock_emitted_keys_are_documented_per_message(runtime_protocol):
    emitted = runtime_protocol["keys"]
    assert set(emitted) == (set(MESSAGES) - {"error"}) | {"link"}, emitted.keys()
    common = table_fields(section("4.1 公共消息字段", level=3))
    for message, fields in emitted.items():
        if message == "link":
            text = section("4.5 面板本地通知", level=3)
            assert all(f"`{field}`" in text for field in fields), fields
        else:
            text = section(f"5.{MESSAGES.index(message) + 1} `{message}`", level=3)
            missing = set(fields) - common - table_fields(text)
            assert not missing, f"{message} 字段表漏写实际顶层键：{sorted(missing)}"
        assert all(f"`{field}`" in DOC for field in fields)
    assert set(COMMANDS) <= set(runtime_protocol["commands"])


def test_every_mock_error_code_is_exercised_and_in_error_table(runtime_protocol):
    mock = (MODULES / "datasource/mock-host.js").read_text(encoding="utf-8")
    implemented = set(re.findall(r'reply\(false,\s*"([^"]+)"', mock))
    assert implemented, "未抽到 mock 错误码，需检查实现结构"
    assert set(runtime_protocol["errors"]) == implemented, "有错误分支尚未实际触发"
    error_table = section("11. 错误码表")
    documented = {row[1] for row in table_rows(error_table) if len(row) == 4}
    for code in runtime_protocol["errors"] + [runtime_protocol["network"], "ok"]:
        assert f"`{code}`" in documented, f"错误码表缺少 {code}"


def test_joint_limits_match_arm_params(runtime_protocol):
    rows = table_rows(section("4.3 关节顺序与限位", level=3))
    assert len(runtime_protocol["joints"]) == 6
    for index, joint in enumerate(runtime_protocol["joints"]):
        row = next(row for row in rows if len(row) == 5 and row[2] == f"`{joint['id']}`")
        assert row[0] == str(index) and row[1] == joint["label"]
        assert [float(row[3]), float(row[4])] == joint["limit"]
        for limit in joint["limit"]:
            assert str(limit) in DOC
    low, high = runtime_protocol["opening"]
    assert f"{low} 至 {high} mm" in section("4.3 关节顺序与限位", level=3)


def test_sections_and_p0_3_replacement_mapping_are_complete():
    headings = re.findall(r"^## (\d+)\. (.+)$", DOC, re.MULTILINE)
    assert [int(number) for number, _ in headings] == list(range(1, 15))
    expected = (
        "文档信息", "职责边界", "传输", "公共约定", "消息", "指令", "激光",
        "时序", "相机", "心跳", "错误码", "兼容", "对照表", "待另一台主机确认",
    )
    for (_, heading), keyword in zip(headings, expected):
        assert keyword in heading
    assert len(re.findall(r"^```text$", section("8. 示范与练习的时序"), re.MULTILINE)) == 2
    mapping = section("13. 附录 A")
    replacements = {
        "四个数据格": ("第几遍", "和示范差多少 mm", "比第一遍好了多少", "修正了几次"),
        "误差曲线": ("最大和平均偏差", "阈值线"),
        "数字孪生": ("当前姿势", "示范轨迹虚影", "这一遍的末端路径", "节点标记", "当前节点高亮"),
        "摄像头": ("夹爪上相机的实时画面", "手眼相机", "实测光点", "示范光点", "偏差箭头", "激光开 / 关"),
        "关节卡片": ("6 个关节", "加夹爪"),
        "最近事件": ("示范", "练习", "每一遍结束", "修正", "急停"),
        "诊断候选表": ("本遍修正记录", "大模型的说明"),
        "顶栏": ("示范", "练习", "开关按钮", "激光", "手动开关", "自动控制", "禁用", "醒目提示"),
    }
    goal = (ROOT / "docs/goal_轨迹训练前端.md").read_text(encoding="utf-8")
    p0 = goal.split("## P0-3 ", 1)[1].split("## P0-4 ", 1)[0]
    # 目标表若增加位置，必须补映射，不能让固定关键词清单漏掉新行。
    positions = re.findall(r"^\s*\| ([^|]+) \| [^|]+ \| [^|]+ \|\s*$", p0, re.MULTILINE)
    assert set(positions) - {"位置"} == {
        "四个数据格", "误差曲线", "数字孪生", "摄像头画面", "关节卡片", "最近事件", "诊断候选表", "顶栏按钮",
    }
    for region, keywords in replacements.items():
        lines = "\n".join(line for line in mapping.splitlines() if line.startswith("|") and region in line)
        assert lines, region
        for keyword in keywords:
            assert keyword in lines, f"附录 A 的 {region} 缺少 {keyword}"
    for keyword in ("通信方式与端口", "时钟是否对时", "关节零位与方向", "相机型号与取流方式",
                    "实际检测", "偏差二维还是三维", "偏差阈值", "节点怎么分段", "练习遍数",
                    "手眼外参由谁标定", "image_url 保存多久", "夹爪开口的定义"):
        assert keyword in section("14. 附录 B"), keyword


def test_old_protocol_has_legacy_notice_under_title():
    old = (ROOT / "docs/下位机接口文档.md").read_text(encoding="utf-8")
    assert old.startswith(
        "# 下位机接口文档\n\n"
        "> 本文档对应旧的 3 关节打靶版本。6 关节 B601-DM 的接口见 `docs/接口文档.md`。\n"
    )
