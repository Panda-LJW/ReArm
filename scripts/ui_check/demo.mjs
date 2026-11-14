// usage: node demo.mjs <outdir> <chrome> <baseUrl> [query] [size]
// 点“▶ 演示”，跟着脚本走完，逐步截图并记录解说条文字；最后检查停在正常状态。
import { createRequire } from "module";
import { readdirSync, mkdirSync } from "fs";
import { homedir } from "os";
const require = createRequire(import.meta.url);
const npx = homedir() + "/.npm/_npx";
const pc = readdirSync(npx).map(d => `${npx}/${d}/node_modules/playwright-core`).find(p => { try { require.resolve(p); return true } catch { return false } });
const { chromium } = require(pc);
const [out, chrome, base, query = "mode=show&demo_pause=700", size = "1280x720"] = process.argv.slice(2);
const [w, h] = size.split("x").map(Number); mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chrome, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const p = await (await browser.newContext({ viewport: { width: w, height: h } })).newPage(); const errs = [];
p.on("pageerror", e => errs.push(e.message));
await p.goto(`${base}/?${query}#home`); await p.waitForTimeout(2200);
const read = () => p.evaluate(() => ({ now: document.querySelector(".guide-now")?.textContent, next: document.querySelector(".guide-next")?.textContent, step: document.querySelector(".guide-step")?.hidden ? null : document.querySelector(".guide-step")?.textContent, btn: document.querySelector(".guide-demo")?.textContent, phase: document.body.dataset.phase, chip: document.getElementById("chipstate").textContent, scroll: document.documentElement.scrollHeight > innerHeight + 1, clippedCards: [...document.querySelectorAll(".card")].filter(e => e.offsetParent && e.scrollHeight > e.clientHeight + 2 && getComputedStyle(e).overflowY === "hidden").map(e => (e.querySelector("h3")?.textContent || "").slice(0, 8)) }));
console.log("idle", JSON.stringify(await read())); await p.screenshot({ path: `${out}/demo-idle-${size}.png` });
await p.click(".guide-demo");
const seen = new Map(); let shots = 0; const t0 = Date.now();
while (Date.now() - t0 < 240000) {
  await p.waitForTimeout(250); const r = await read();
  const key = `${r.step}|${r.phase}`;
  if (r.step && !seen.has(key)) { seen.set(key, r); if (shots < 14) await p.screenshot({ path: `${out}/demo-${String(++shots).padStart(2, "0")}-${size}.png` }); console.log(key, "|", r.now, "| chip:", r.chip, r.scroll ? "SCROLL" : "", r.clippedCards.length ? "CLIPPED " + r.clippedCards : "") }
  if (!r.step && r.btn === "▶ 演示" && seen.size) break;
}
await p.waitForTimeout(800);
const end = await read(), state = await (await fetch(base + "/api/state")).json();
console.log("end", JSON.stringify(end), "| took", Math.round((Date.now() - t0) / 1000), "s | state", state.state, state.head.id, "recoveries", state.stats.recoveries, "recognitions", state.stats.recognitions, "| pageerrors", errs);
await p.screenshot({ path: `${out}/demo-end-${size}.png` });
await browser.close();
