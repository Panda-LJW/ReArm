// usage: node shots.mjs <outdir> <chrome> <baseUrl> <prefix> [query] [sizes e.g. 1920x1080,1280x720] [pages home,overview,codes]
import { createRequire } from "module";
import { readdirSync, mkdirSync } from "fs";
import { homedir } from "os";
const require = createRequire(import.meta.url);
const npx = homedir() + "/.npm/_npx";
const pc = readdirSync(npx).map(d => `${npx}/${d}/node_modules/playwright-core`).find(p => { try { require.resolve(p); return true } catch { return false } });
const { chromium } = require(pc);
const [out, chrome, base, prefix, query = "", sizes = "1920x1080,1280x720", pages = "home"] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chrome, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const logs = [];
for (const size of sizes.split(",")) {
  const [w, h] = size.split("x").map(Number);
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  const p = await ctx.newPage();
  p.on("console", m => { if (["error", "warning"].includes(m.type())) logs.push(`${size} ${m.type()}: ${m.text().slice(0, 300)}`) });
  p.on("pageerror", e => logs.push(`${size} pageerror: ${e.message}`));
  for (const page of pages.split(",")) {
    await p.goto(`${base}/${query ? "?" + query : ""}#${page}`); await p.waitForTimeout(page === pages.split(",")[0] ? 2500 : 900);
    await p.screenshot({ path: `${out}/${prefix}-${page}-${w}x${h}.png` });
    const m = await p.evaluate(() => {
      const de = document.documentElement, vis = e => e.offsetParent !== null && getComputedStyle(e).visibility !== "hidden";
      let minFont = 999, minEl = ""; const small = {};
      document.querySelectorAll("body *").forEach(e => { if (!vis(e)) return; const own = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()); if (!own) return; const r = e.getBoundingClientRect(); if (!r.width || !r.height) return; const s = parseFloat(getComputedStyle(e).fontSize); if (s < 18) { const k = (e.id ? "#" + e.id : e.className ? "." + String(e.className).split(" ")[0] : e.tagName) + "@" + s; small[k] = (small[k] || 0) + 1 } if (s < minFont) { minFont = s; minEl = e.className || e.id || e.tagName } });
      const clipped = [...document.querySelectorAll("body *")].filter(e => vis(e) && e.childElementCount === 0 && e.textContent.trim() && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== "visible").map(e => (e.id || e.className || e.tagName) + ":" + e.textContent.trim().slice(0, 24)).slice(0, 12);
      const cards = [...document.querySelectorAll(".card,.cam")].filter(vis).filter(e => e.scrollHeight > e.clientHeight + 2 && getComputedStyle(e).overflowY === "hidden").map(e => (e.querySelector("h3")?.textContent || e.className).slice(0, 14) + `:${e.clientHeight}/${e.scrollHeight}`);
      return { pageScroll: de.scrollHeight > innerHeight + 1, hOverflow: de.scrollWidth > innerWidth + 1, minFont, minEl: String(minEl).slice(0, 30), small, clipped, clippedCards: cards, twin: de.dataset.twin, pres: de.dataset.presentation, renderer: document.getElementById("twin")?.dataset.renderer, twinState: window.__rearmTwin?.twin.state() };
    });
    console.log(prefix, page, size, JSON.stringify(m));
  }
  await ctx.close();
}
console.log("console:", logs.slice(0, 12));
await browser.close();
