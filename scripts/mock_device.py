"""模拟下位机：按《docs/下位机接口文档.md》的遥测报文，通过 WebSocket 循环发送关节角。

只用于联调前验证前端的数据源层，不连接任何硬件，只监听本机回环地址。

    .venv/bin/python scripts/mock_device.py --port 8765
    浏览器打开 http://127.0.0.1:8000/?twin=device&device=ws://127.0.0.1:8765

按文档约定：报文跑在 WebSocket 上时不带 CRC 后缀；`sim: true` 表示这是模拟数据。
"""
import argparse
import asyncio
import json
import math
import time

from websockets.asyncio.server import serve

POSES = [(0.0, 40.0, -100.0), (28.0, 62.0, -118.0), (-24.0, 78.0, -132.0), (12.0, 30.0, -84.0)]
HOLD_S, MOVE_S = 1.5, 1.5


def pose_at(elapsed: float) -> tuple[list[float], bool]:
    """Joint angles (panel convention, degrees) and whether the arm is moving."""
    span = HOLD_S + MOVE_S
    step, within = int(elapsed // span), elapsed % span
    start, end = POSES[step % len(POSES)], POSES[(step + 1) % len(POSES)]
    k = 0.0 if within < HOLD_S else (within - HOLD_S) / MOVE_S
    k = k * k * (3 - 2 * k)
    return [a + (b - a) * k for a, b in zip(start, end)], within >= HOLD_S


def telemetry(seq: int, started: float) -> str:
    elapsed = time.monotonic() - started
    angles, moving = pose_at(elapsed)
    return json.dumps({
        "v": 1, "type": "telemetry", "seq": seq % 65536, "t_ms": int(elapsed * 1000),
        "joints": [{"id": i + 1, "pos_deg": round(q, 2), "vel_dps": 0.0, "torque_nm": 0.0,
                    "temp_c": round(30 + 2 * math.sin(elapsed / 20), 1), "err": 0} for i, q in enumerate(angles)],
        "moving": moving, "target_reached": not moving, "laser": not moving, "estop": False, "estop_source": "none",
        "limit": 0, "vbus_v": 24.0, "ibus_a": 0.8, "load": 0.35, "temp_c": 31.0, "fault": 0, "sim": True,
    }, separators=(",", ":"))


async def main(host: str, port: int, rate_hz: float, duration: float | None):
    started = time.monotonic()

    async def handler(socket):
        seq = 0
        try:
            while True:
                await socket.send(telemetry(seq, started))
                seq += 1
                await asyncio.sleep(1 / rate_hz)
        except Exception:
            return  # client went away

    async with serve(handler, host, port):
        print(f"mock device listening on ws://{host}:{port} at {rate_hz:g} Hz", flush=True)
        await (asyncio.sleep(duration) if duration else asyncio.Future())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--rate", type=float, default=20.0, help="遥测频率 Hz")
    parser.add_argument("--duration", type=float, default=None, help="运行多少秒后自动退出（测试用）")
    args = parser.parse_args()
    # 只绑定回环地址：这是本机联调工具，不对外提供服务。
    asyncio.run(main("127.0.0.1", args.port, args.rate, args.duration))
