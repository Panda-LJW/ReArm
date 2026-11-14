import { frameView } from "../../shell/view.js";
import { initialState } from "../../state/store.js";
import { online, sourceName } from "../../state/selectors.js";
import { element } from "../../widgets/dom.js";
import { millimeters } from "../../widgets/format.js";
import { flash, stagger } from "../../widgets/motion.js";

export function mount(root, ctx = {}) {
  const doc = root.ownerDocument, css = element(doc, "link");
  css.rel = "stylesheet"; css.href = new URL("./settings.css", import.meta.url).href; doc.head.append(css);
  const fields = {};
  function group(title, rows) {
    const section = element(doc, "section", "settings-section c-card"), list = element(doc, "dl", "settings-values");
    const body = element(doc, "div", "settings-body c-card-body");
    body.append(list); section.append(element(doc, "h2", "c-card-head", title), body);
    for (const [id, label] of rows) {
      const pair = element(doc, "div", "settings-pair"), value = element(doc, "dd", "", "—");
      value.dataset.setting = id; fields[id] = value;
      pair.append(element(doc, "dt", "", label), value); list.append(pair);
    }
    return section;
  }
  const header = element(doc, "header", "settings-header");
  header.append(element(doc, "h1", "", "设置"), element(doc, "p", "pill", "只读"));
  const content = element(doc, "div", "settings-content");
  content.append(group("连接", [["source", "数据来源"], ["address", "接入地址"], ["connection", "后端连接"],
    ["arm_connection", "机械臂连接"], ["enabled", "机械臂使能"], ["busy", "忙状态"], ["pose_error", "位姿误差"],
    ["camera", "相机状态"], ["protocol", "协议版本"]]),
    group("参数", [["threshold", "偏差阈值"], ["opening", "夹爪开口"]]));
  root.replaceChildren(header, content);
  stagger(content.children);
  const view = frameView(next => {
    const state = next || initialState(), hello = state.hello;
    const device = online(state) ? state.device : null, camera = device?.camera;
    const extra = ["address", "arm_connection", "enabled", "busy", "pose_error", "camera"];
    for (const key of extra) fields[key].parentElement.hidden = !state.device && !hello?.address && !state.link.address;
    const known = (value, yes, no) => value === true ? yes : value === false ? no : "—";
    const values = {
      source: sourceName(state) || "—",
      address: hello?.address || state.link.address || "—",
      connection: !state.link.online ? "未连接" : !hello ? "等待握手" : online(state) ? "已连接" : "协议不兼容",
      arm_connection: known(device?.connected, "已连接", "未连接"),
      enabled: known(device?.enabled, "已使能", "未使能"),
      busy: known(device?.busy, `忙：${device?.busy_action || "执行中"}`, "空闲"),
      pose_error: Number.isFinite(device?.pose_error_deg) ? `${device.pose_error_deg}°` : "—",
      camera: !camera ? "—" : camera.error ? `异常：${camera.error}` : camera.enabled && camera.fresh ? "已接入" :
        camera.enabled ? "画面过期" : "未接入摄像头",
      protocol: Number.isInteger(hello?.proto) && hello.proto > 0 ? `v${hello.proto}` : "—",
      threshold: millimeters(hello?.threshold_mm), opening: hello?.sim === false ?
        `${millimeters(online(state) && state.joint?.gripper_valid ? state.joint.gripper_mm : null)}（来源：${state.joint?.gripper_source || "未标定"}）` : "全开",
    };
    for (const [key, value] of Object.entries(values)) {
      if (fields[key].textContent !== value) fields[key].textContent = value;
      fields[key].classList.toggle("settings-missing", value === "—");
    }
    fields.connection.dataset.online = String(online(state));
    flash(fields.connection, values.connection);
  }, () => { css.remove(); root.replaceChildren(); }, doc.defaultView);
  view.render(ctx.store?.getState() || initialState());
  return view;
}
