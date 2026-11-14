import { frameView } from "../../shell/view.js";
import { initialState } from "../../state/store.js";
import { online } from "../../state/selectors.js";
import { element } from "../../widgets/dom.js";
import { millimeters } from "../../widgets/format.js";

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
  content.append(group("连接", [["source", "数据来源"], ["connection", "状态"], ["protocol", "协议版本"]]),
    group("参数", [["threshold", "偏差阈值"], ["opening", "夹爪开口"]]));
  root.replaceChildren(header, content);
  const view = frameView(next => {
    const state = next || initialState(), hello = state.hello;
    const values = {
      source: hello?.sim === true ? "本地演示" : hello?.sim === false ? "主机" : "—",
      connection: !state.link.online ? "未连接" : !hello ? "等待握手" : online(state) ? "已连接" : "协议不兼容",
      protocol: Number.isInteger(hello?.proto) && hello.proto > 0 ? `v${hello.proto}` : "—",
      threshold: millimeters(hello?.threshold_mm), opening: "全开",
    };
    for (const [key, value] of Object.entries(values)) {
      if (fields[key].textContent !== value) fields[key].textContent = value;
      fields[key].classList.toggle("settings-missing", value === "—");
    }
    fields.connection.dataset.online = String(online(state));
  }, () => { css.remove(); root.replaceChildren(); }, doc.defaultView);
  view.render(ctx.store?.getState() || initialState());
  return view;
}
