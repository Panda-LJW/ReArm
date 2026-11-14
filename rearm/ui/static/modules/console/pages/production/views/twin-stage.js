import { frameView } from "../../../shell/view.js";

export async function mount(root, ctx) {
  const twin = await ctx.createTwin(root, { status: false, labels: "hover" });
  let workspace;
  return frameView(state => {
    const joint = state.joint;
    twin.update({ q_rad: joint?.q, valid: joint?.valid, gripper_mm: joint?.gripper_mm,
      online: state.link.online, mode: state.hello?.sim === true ? "sim" : "live", timestamp: joint?.t / 1000 });
    if (workspace !== state.workspace) {
      workspace = state.workspace; twin.setProps(workspace.props);
    }
  }, () => twin.dispose(), root.ownerDocument.defaultView);
}
