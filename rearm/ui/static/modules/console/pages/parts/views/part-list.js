import { mount as list } from "./library-list.js";
export const mount = (root, ctx) => list(root, { ...ctx, target: "part" });
