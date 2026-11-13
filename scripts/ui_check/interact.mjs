// usage: node interact.mjs <outdir> <chrome> <baseUrl> <query> <size>
// Checks overlays in a given mode: version dropdown, version modal, more menu, confirm dialog, toggle button, module removal.
import { createRequire } from "module";
import { readdirSync, mkdirSync } from "fs";
import { homedir } from "os";
const require = createRequire(import.meta.url);
const npx = homedir() + "/.npm/_npx";
const pc = readdirSync(npx).map(d => `${npx}/${d}/node_modules/playwright-core`).find(p => { try { require.resolve(p); return true } catch { return false } });
const { chromium } = require(pc);
const [out, chrome, base, query, size] = process.argv.slice(2);
const [w, h] = size.split("x").map(Number); mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chrome, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const ctx = await browser.newContext({ viewport: { width: w, height: h } });
const p = await ctx.newPage(); const errs = [];
p.on("pageerror", e => errs.push(e.message));
const tag = `${query.replace(/\W+/g, "_") || "normal"}-${size}`;
const fits = sel => p.evaluate(sel => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return { inView: r.left >= 0 && r.top >= 0 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1, w: Math.round(r.width), h: Math.round(r.height), scrollX: e.scrollWidth > e.clientWidth + 1 } }, sel);
await p.goto(`${base}/?${query}#home`); await p.waitForTimeout(2000);
await p.click("#vbtn"); await p.waitForTimeout(200); await p.screenshot({ path: `${out}/${tag}-versions.png` }); console.log("dropdown", JSON.stringify(await fits("#vlist")));
await p.click(".vrow:nth-child(2)"); await p.waitForTimeout(300); await p.screenshot({ path: `${out}/${tag}-modal.png` }); console.log("modal", JSON.stringify(await fits("#modal")));
await p.keyboard.press("Escape");
await p.click("#more"); await p.waitForTimeout(150); console.log("more", JSON.stringify(await fits("#morelist")));
await p.click('[data-cmd="baseline"]'); await p.waitForTimeout(200); await p.screenshot({ path: `${out}/${tag}-confirm.png` }); console.log("confirm", JSON.stringify(await fits("#modal")));
await p.keyboard.press("Escape");
// toggle button round trip
const t0 = await p.evaluate(() => [document.documentElement.dataset.mode || "normal", location.search, document.getElementById("modetoggle")?.textContent]);
await p.click("#modetoggle"); await p.waitForTimeout(500);
const t1 = await p.evaluate(() => [document.documentElement.dataset.mode || "normal", location.search, document.getElementById("modetoggle")?.textContent, location.hash]);
await p.click("#modetoggle"); await p.waitForTimeout(300);
console.log("toggle", JSON.stringify(t0), "→", JSON.stringify(t1), "→", JSON.stringify(await p.evaluate(() => [document.documentElement.dataset.mode || "normal", location.search])));
// estop still reachable and commands still work in this mode
console.log("estop enabled", await p.evaluate(() => !document.getElementById("estop").disabled), "selfcheck enabled", await p.evaluate(() => !document.querySelector('[data-cmd="selfcheck"]').disabled));
await ctx.close();
// module removal: block every optional module file, the panel must still work
for (const [name, pattern] of [["all-modules", "**/static/modules/**"], ["twin-only", "**/static/modules/twin/**"], ["three-only", "**/static/vendor/**"], ["presentation-only", "**/static/modules/presentation/**"], ["datasource-only", "**/static/modules/datasource/**"]]) {
  const c2 = await browser.newContext({ viewport: { width: w, height: h } }); const q = await c2.newPage(); const e2 = [];
  q.on("pageerror", e => e2.push(e.message));
  await q.route(pattern, r => r.abort());
  await q.goto(`${base}/?${query}#home`); await q.waitForTimeout(2200);
  const r = await q.evaluate(() => ({ twin: document.documentElement.dataset.twin, pres: document.documentElement.dataset.presentation, renderer: document.getElementById("twin")?.dataset.renderer, cardHidden: document.getElementById("twincard").hidden, hasTwin: document.body.classList.contains("has-twin"), kpi: document.getElementById("k-shots").textContent, state: document.getElementById("chipstate").textContent, conn: document.getElementById("conn").textContent, scroll: document.documentElement.scrollHeight > innerHeight + 1, joints: document.querySelectorAll("#joints .joint").length, toggle: !!document.getElementById("modetoggle") }));
  await q.screenshot({ path: `${out}/${tag}-no-${name}.png` });
  console.log("blocked", name, JSON.stringify(r), "pageerrors", e2.length);
  await c2.close();
}
console.log("pageerrors", errs);
await browser.close();
