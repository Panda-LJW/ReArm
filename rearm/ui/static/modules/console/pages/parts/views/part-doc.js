import { element } from "../../../widgets/dom.js";
import { mount as documentView } from "./library-doc.js";
import { detail, number } from "./format.js";
import { shape } from "./shape.js";

function describe(root, item) {
  const doc = root.ownerDocument, appearance = element(doc, "div", "library-appearance c-viewport");
  root.append(element(doc, "h3", "c-card-head", "外形与轮廓"), appearance);
  if (item.photo_url) {
    const photo = element(doc, "img"); photo.src = item.photo_url; photo.alt = `${item.name}外形照片`;
    photo.addEventListener("error", () => photo.remove()); appearance.append(photo);
  }
  appearance.append(shape(doc, item));
  const properties = element(doc, "dl", "library-properties"), force = detail(doc, "夹持力", `${number(item.force_n)} N`);
  force.querySelector("dd").dataset.force = "";
  properties.append(detail(doc, "尺寸（长 × 宽 × 高）", `${(item.size_mm || []).map(number).join(" × ")} mm`),
    force, detail(doc, "开口", item.opening === "full" ? "全开" : "—"));
  const basis = element(doc, "details", "library-basis"), b = item.force_basis || {};
  basis.append(element(doc, "summary", "", "查看夹持力估算依据"));
  const values = element(doc, "dl", "library-properties");
  values.append(detail(doc, "估计重量", `${number(b.estimated_mass_kg * 1000)} g`), detail(doc, "材质", b.material || "—"),
    detail(doc, "摩擦系数", String(b.friction_coefficient ?? "—")), detail(doc, "安全系数", String(b.safety_factor ?? "—")),
    detail(doc, "重力加速度", `${b.gravity_m_s2 ?? "—"} m/s²`), detail(doc, "夹指数量", String(b.fingers ?? "—")));
  basis.append(values, element(doc, "p", "", "每指夹持力 ≈ 重量（kg）× 重力加速度 × 安全系数 ÷ 摩擦系数 ÷ 夹指数量"));
  force.append(basis); root.append(properties);
}
export const mount = (root, ctx) => documentView(root, { ...ctx, target: "part", describe });
