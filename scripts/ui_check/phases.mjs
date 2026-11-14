// usage: node phases.mjs <outdir> <chrome> <baseUrl> <prefix>  — captures ok / busy / stop / stale phases in both modes
import { createRequire } from "module";
import { readdirSync, mkdirSync } from "fs";
import { homedir } from "os";
const require = createRequire(import.meta.url);
const npx = homedir() + "/.npm/_npx";
const pc = readdirSync(npx).map(d => `${npx}/${d}/node_modules/playwright-core`).find(p => { try { require.resolve(p); return true } catch { return false } });
const { chromium } = require(pc);
const [out, chrome, base, prefix] = process.argv.slice(2); mkdirSync(out, { recursive: true });
const post = (n, b = {}) => fetch(`${base}/api/command/${n}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(r => r.status);
const browser = await chromium.launch({ executablePath: chrome, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
for (const [mode, w, h] of [["", 1920, 1080], ["mode=show", 1920, 1080], ["mode=show", 1280, 720]]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } }); const p = await ctx.newPage(); const errs = [];
  p.on("pageerror", e => errs.push(e.message));
  const tag = `${prefix}-${mode ? "show" : "normal"}-${w}x${h}`;
  const info = () => p.evaluate(() => ({ focus: document.documentElement.dataset.focus, phase: document.body.dataset.phase, chip: document.getElementById("chipstate").textContent, chipIcon: getComputedStyle(document.getElementById("chipstate"), "::before").content, estopOK: (() => { const e = document.getElementById("estop"), r = e.getBoundingClientRect(); return !e.disabled && document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === e })(), resetVisible: !!document.getElementById("resetstop").offsetParent, scroll: document.documentElement.scrollHeight > innerHeight + 1 }));
  await p.goto(`${base}/?${mode}#home`); await p.waitForTimeout(2200);
  await p.screenshot({ path: `${out}/${tag}-ok.png` }); console.log(tag, "ok", JSON.stringify(await info()));
  await post("inject", { kind: "j2", amount: 1 }); const run = post("selfcheck");
  for (let i = 0; i < 40; i++) { await p.waitForTimeout(60); if ((await p.evaluate(() => document.body.dataset.phase)) === "busy") break }
  await p.screenshot({ path: `${out}/${tag}-busy.png` }); console.log(tag, "busy", JSON.stringify(await info()));
  await run; await post("inject", { kind: "restore", amount: 0 }); await post("selfcheck"); await p.waitForTimeout(400);
  await post("estop"); await p.waitForTimeout(500);
  await p.screenshot({ path: `${out}/${tag}-stop.png` }); console.log(tag, "stop", JSON.stringify(await info()));
  await post("reset_estop"); await p.waitForTimeout(300);
  await ctx.close();
  console.log(tag, "pageerrors", errs);
}
await browser.close();
