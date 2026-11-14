"""校验接口文档的前端字段覆盖、章节及可复制示例帧。"""
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xFFFF
    return crc


def test_device_protocol_doc():
    doc = (ROOT / "docs/下位机接口文档.md").read_text(encoding="utf-8")
    app = (ROOT / "rearm/ui/static/app.js").read_text(encoding="utf-8")
    fields = set(re.findall(r"\bS(?:\?\.|\.)([A-Za-z_$][\w$]*)", app))
    assert fields, "没有抽到 S 字段，检查正则或 app.js 结构"
    missing = sorted(field for field in fields if f"`{field}`" not in doc)
    assert not missing, f"文档缺少前端字段：{missing}"

    device = (ROOT / "rearm/ui/static/modules/datasource/device-source.js").read_text(encoding="utf-8")
    parser = device.split("export function parseTelemetry", 1)[1].split("export function createDeviceSource", 1)[0]
    required = {"v", "type", "telemetry", "joints", "pos_deg", "laser", "t_ms", "sim"}
    required.update(re.findall(r"\b(?:data|j|a|b)\.([A-Za-z_$][\w$]*)", parser))
    missing = sorted(key for key in required if f"`{key}`" not in doc)
    assert not missing, f"文档缺少 parseTelemetry 的键/类型：{missing}"

    assert crc16_ccitt_false(b"123456789") == 0x29B1
    frames = re.findall(r"^(\{[^\r\n]*\})\*([0-9A-F]{4})$", doc, re.MULTILINE)
    candidates = re.findall(r"^\{[^\r\n]*\}\*[^\r\n]*$", doc, re.MULTILINE)
    assert len(frames) == len(candidates), "存在 CRC 后缀格式错误的示例帧"
    assert len(frames) >= 8, f"示例帧不足 8 条：{len(frames)}"
    for number, (body, expected) in enumerate(frames, 1):
        raw = body.encode("utf-8")
        assert len(raw) + 6 <= 1024, f"示例 {number} 超过帧长度上限"
        assert crc16_ccitt_false(raw) == int(expected, 16), f"示例 {number} CRC 错误"
        message = json.loads(body)
        assert isinstance(message, dict) and {"v", "type"} <= message.keys(), number
        assert message["v"] == 1 and isinstance(message["type"], str), number

    headings = "\n".join(re.findall(r"^#{1,3} .+$", doc, re.MULTILINE))
    for keyword in ("通信方式", "帧格式", "遥测", "指令", "心跳", "急停", "错误码", "示例", "对照表", "待确认"):
        assert keyword in headings, f"缺少章节标题关键词：{keyword}"
