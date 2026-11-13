// 数据源层的入口。所有数据源接口相同：{ kind, start(), stop(), subscribe(cb) → 取消函数 }，
// 回调收到的都是 frame.js 定义的 JointFrame。换数据源只改这里的选择，显示模块不用动。
import { createPanelSource } from "./panel-source.js";
import { createSimSource } from "./sim-source.js";
import { createDeviceSource } from "./device-source.js";

export const SOURCES = { panel: createPanelSource, sim: createSimSource, device: createDeviceSource };

export function createSource(kind = "panel", options = {}) {
  const factory = SOURCES[kind];
  if (!factory) throw new Error("未知数据源：" + kind);
  return factory(options);
}

// 地址栏参数 → 数据源：?twin=sim 用内置模拟；?twin=device&device=ws://主机:端口/路径 接下位机；缺省用面板数据。
export function sourceFromParams(params) {
  const kind = params.get("twin");
  if (kind === "sim") return createSource("sim");
  if (kind === "device") {
    const url = params.get("device") || "";
    if (!/^wss?:\/\//.test(url)) throw new Error("device 参数必须是 ws:// 或 wss:// 地址");
    return createSource("device", { url });
  }
  return createSource("panel");
}

export { makeFrame, MODES } from "./frame.js";
