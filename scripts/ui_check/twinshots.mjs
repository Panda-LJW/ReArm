// usage: node twinshots.mjs <outdir> <chrome> <baseUrl> <prefix> [query]
import { createRequire } from "module";
import { readdirSync, mkdirSync } from "fs";
import { homedir } from "os";
const require = createRequire(import.meta.url);
const npx = homedir() + "/.npm/_npx";
const pc = readdirSync(npx).map(d => `${npx}/${d}/node_modules/playwright-core`).find(p => { try { require.resolve(p); return true } catch { return false } });
const { chromium } = require(pc);
const [out, chrome, base, prefix, query = "twin=off"] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chrome, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await (await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })).newPage();
p.on("pageerror", e => console.log("pageerror", e.message));
// a bare page: mount the twin alone, no panel, to prove the module is self-contained
await p.goto(base + "/static/modules/twin/demo.html?" + query); await p.waitForTimeout(1500);
const poses = [[0, 40, -100], [0, 90, -90], [45, 20, -60], [-60, 110, -150], [0, 0, 0]];
for (const [i, q] of poses.entries()) {
  const st = await p.evaluate(async q => { window.demo.twin.update({ angles_deg: q, mode: "live", online: true, laser: true }); await new Promise(r => setTimeout(r, 1500)); return window.demo.twin.state() }, q);
  await p.screenshot({ path: `${out}/${prefix}-pose${i}.png` });
  console.log(JSON.stringify(q), "shown", st.shown.map(v => +v.toFixed(2)), st.renderer);
}
await p.evaluate(async () => { window.demo.twin.update({ online: false }); await new Promise(r => setTimeout(r, 400)) });
await p.screenshot({ path: `${out}/${prefix}-offline.png` });
console.log("offline state", JSON.stringify(await p.evaluate(() => [window.demo.twin.state().mode, document.querySelector(".twin-status").textContent, document.querySelector(".twin-note").textContent])));
await browser.close();
