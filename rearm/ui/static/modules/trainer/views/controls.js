import { online, element } from "./format.js";

export function buttonStates(state) {
  const unavailable = state.ui?.active === false || !online(state) || state.mode === "estop" || state.mode === "fault" || !!state.joint?.fault || state.ui?.panelEstop === true;
  const demo = state.mode === "demo", practice = state.mode === "practice", pending = !!state.ui?.pending;
  const laserOn = state.laser?.on === true, laserAuto = !unavailable && practice;
  const laserManual = !unavailable && !practice && laserOn;
  return {
    demo: { disabled: unavailable || practice || pending, pressed: demo, text: demo ? "示范中 · 结束" : "示范" },
    practice: { disabled: unavailable || demo || pending, pressed: practice, text: practice ? "练习中 · 停止" : "练习" },
    laser: { disabled: unavailable || practice || pending, pressed: laserOn,
      text: laserAuto ? "激光 自动" : laserManual ? "激光 开" : "激光",
      className: "trainer-laser" + (laserAuto ? " trainer-laser-auto" : laserManual ? " trainer-laser-on" : ""),
      dotClassName: laserAuto && laserOn ? "trainer-laser-dot" : "" },
  };
}
export function mount(root) {
  const header = root.querySelector("header"), old = header.querySelector('[data-cmd="selfcheck"]'), menu = header.querySelector(".menu");
  const legacyBadge = header.querySelector("#mode");
  legacyBadge.classList.add("trainer-legacy-badge");
  const hidden = [old.hidden, menu.hidden]; old.hidden = menu.hidden = true;
  const group = element("div", "trainer-controls"); group.setAttribute("role", "group"); group.setAttribute("aria-label", "轨迹训练");
  const buttons = Object.fromEntries(["demo", "practice", "laser"].map(name => {
    const button = element("button", name === "laser" ? "trainer-laser" : "trainer-action"); button.type = "button";
    button.dataset.trainerAction = name;
    button.onclick = () => group.dispatchEvent(new CustomEvent("trainer:command", { bubbles: true, detail: { action: name } }));
    group.append(button); return [name, button];
  }));
  old.before(group);
  const badge = element("span", "pill trainer-source"); header.querySelector(".conn").append(badge);
  const banner = element("div", "banner trainer-laser-banner", "激光已手动打开，注意避让"); banner.setAttribute("role", "alert"); banner.hidden = true;
  root.querySelector(".statusbars").append(banner);
  const toast = root.querySelector("#toast"), toastMessage = root.querySelector("#toastmsg");
  return { dispose() { old.hidden = hidden[0]; menu.hidden = hidden[1]; legacyBadge.classList.remove("trainer-legacy-badge"); group.remove(); badge.remove(); banner.remove(); },
    notify(reason) { toastMessage.textContent = reason; toast.classList.add("open"); },
    render(state) {
      const states = buttonStates(state);
      for (const [name, button] of Object.entries(buttons)) {
        const value = states[name]; button.disabled = value.disabled; button.textContent = value.text;
        button.setAttribute("aria-pressed", String(value.pressed));
        button.classList.toggle("primary", name !== "laser" && value.pressed);
        if (name === "laser") {
          button.className = value.className;
          button.setAttribute("aria-label", value.dotClassName ? `${value.text}，正在出光` : value.text);
          if (value.dotClassName) {
            const dot = element("span", value.dotClassName, "● "); dot.setAttribute("aria-hidden", "true"); button.prepend(dot);
          }
        }
      }
      const source = state.hello?.sim ? "模拟" : state.ui?.hostname || "";
      badge.textContent = online(state) ? source : source ? `${source} · 离线` : "离线";
      banner.hidden = !(state.ui?.laserManual && state.laser?.on);
    },
  };
}
