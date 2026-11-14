import { ARM_PARAMS } from "../../arm/arm-params.js";
import { number, online, modeText, preserve, element } from "./format.js";

export function mount(root) {
  const joints = root.querySelector("#joints"), env = root.querySelector(".envrow");
  const dispose = preserve([joints, env]);
  const defs = [...ARM_PARAMS.joints.map(j => ({ label: j.label, limit: j.limit, unit: "°", scale: 180 / Math.PI })),
    { label: "夹爪", limit: ARM_PARAMS.gripper.openingMm, unit: " mm", scale: 1 }];
  joints.replaceChildren();
  const rows = defs.map(def => {
    const row = element("div", "joint"), name = element("span", "n", def.label), bar = element("div", "bar"), cursor = element("i"), value = element("span", "num");
    bar.title = `范围 ${number(def.limit[0] * def.scale)} ~ ${number(def.limit[1] * def.scale)}${def.unit}`;
    bar.append(cursor); row.append(name, bar, value); joints.append(row);
    return { row, cursor, value };
  });
  const values = ["最高温度", "最大电流", "模式"].map(label => {
    const span = element("span", "", label + " "), value = element("b", "num", "—"); span.append(value); return { span, value };
  });
  env.replaceChildren(...values.map(v => v.span));
  const max = values => Array.isArray(values) && values.some(Number.isFinite) ? Math.max(...values.filter(Number.isFinite)) : null;
  return { dispose, render(state) {
    const live = online(state), joint = state.joint;
    rows.forEach(({ row, cursor, value }, i) => {
      const def = defs[i], q = i < ARM_PARAMS.joints.length ? joint?.q?.[i] : joint?.gripper_mm;
      const valid = i < ARM_PARAMS.joints.length ? joint?.valid?.[i] !== false : joint?.gripper_valid !== false;
      const good = valid && Number.isFinite(q) && q >= def.limit[0] && q <= def.limit[1];
      row.classList.toggle("trainer-invalid", !good || !live);
      value.textContent = !live ? "离线" : !joint ? "—" : good ? number(q * def.scale) + def.unit : "无效";
      cursor.hidden = !live || !good;
      if (good) cursor.style.left = `${(q - def.limit[0]) / (def.limit[1] - def.limit[0]) * 100}%`;
    });
    values[0].value.textContent = live ? number(max(joint?.temp)) + " °C" : "离线";
    values[1].value.textContent = live ? number(max(joint?.current?.map(Math.abs)), 2) + " A" : "离线";
    values[2].value.textContent = modeText(state);
  } };
}
