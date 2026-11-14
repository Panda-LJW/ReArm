import { fresh, nav, openConfirmation, shot } from './browser.mjs';
import { disabledTooltips } from './tooltip-check.mjs';

export const PAGES = ['production', 'parts', 'records', 'settings'];

export async function checkNavigation(ctx) {
  await fresh(ctx);
  const items = await ctx.page.locator('[data-nav]').evaluateAll(nodes => nodes.map(el => ({
    page: el.dataset.nav, text: el.innerText.trim(), visible: !!el.getBoundingClientRect().width,
  })));
  ctx.note(`导航=${JSON.stringify(items)}`);
  ctx.assert(JSON.stringify(items.map(i => i.page)) === JSON.stringify(PAGES), '导航必须正好 4 项且顺序正确');
  ctx.assert(JSON.stringify(items.map(i => i.text)) === JSON.stringify(['生产', '零件库', '记录', '设置']) && items.every(i => i.visible),
    '导航文字或可见性不符');
  for (const name of PAGES) { await nav(ctx, name); await shot(ctx, `nav-${name}`); }
  ctx.note('四页逐个点击，根元素可见且文字非空');
}

export async function buttonWords(ctx) {
  const buttons = await ctx.page.locator('button:visible,[role="button"]:visible').evaluateAll(nodes =>
    nodes.map(el => ({ text: el.innerText.trim(), nativeDisabled: el.hasAttribute('disabled') })));
  const bad = buttons.filter(b => /[^\s·，。:：]+中(?:[.…。！!]*)(?=$|\s|[·，。])/u.test(b.text) || b.nativeDisabled);
  ctx.assert(!bad.length, `按钮含状态词或原生 disabled：${JSON.stringify(bad)}`);
  return buttons.length;
}

export async function checkButtons(ctx) {
  const errors = []; let count = 0, disabled = 0;
  for (const name of PAGES) {
    try {
      await fresh(ctx, name); count += await buttonWords(ctx);
      disabled += await disabledTooltips(ctx);
    } catch (error) { errors.push(`${name}: ${error.message}`); }
  }
  await fresh(ctx); await openConfirmation(ctx);
  count += await buttonWords(ctx);
  ctx.assert(await ctx.page.locator('[data-action="confirm"]').getAttribute('aria-disabled') === 'true',
    '未勾选时缺少 aria-disabled 确认按钮');
  disabled += await disabledTooltips(ctx);
  await shot(ctx, 'disabled-tooltip');
  ctx.note(`检查 ${count} 个按钮文案及 ${disabled} 个不可用按钮悬停`);
  ctx.assert(errors.length === 0, errors.join('；'));
}

export async function checkTwinLabels(ctx) {
  await fresh(ctx); await ctx.page.mouse.move(0, 0);
  const labels = ctx.page.locator('[data-twin-label]');
  await labels.first().waitFor({ state: 'attached' });
  const initial = await labels.evaluateAll(nodes => nodes.map(el => ({
    visible: el.getBoundingClientRect().width > 0 && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none',
    x: el.getAttribute('data-anchor-x'), y: el.getAttribute('data-anchor-y'),
  })));
  ctx.assert(initial.length > 0 && initial.every(e => !e.visible), '孪生标签默认可见或不存在');
  const index = initial.findIndex(e => e.x !== null && e.y !== null && Number.isFinite(Number(e.x)) && Number.isFinite(Number(e.y)));
  ctx.assert(index >= 0, '没有合法的视口关节锚点');
  const at = initial[index];
  await ctx.page.mouse.move(Number(at.x), Number(at.y));
  await labels.nth(index).waitFor({ state: 'visible' });
  await shot(ctx, 'twin-hover');
  ctx.note(`${initial.length} 个标签默认隐藏；锚点 (${at.x}, ${at.y}) 悬停可见`);
}

export async function checkEmptyData(ctx) {
  await fresh(ctx);
  const result = await ctx.page.evaluate(() => {
    const state = document.querySelector('[data-status]')?.textContent.trim();
    const token = getComputedStyle(document.documentElement).getPropertyValue('--bad').trim();
    const probe = document.createElement('span'); probe.style.color = 'var(--bad)';
    document.body.append(probe); const bad = getComputedStyle(probe).color; probe.remove();
    const hits = [];
    for (const el of document.querySelectorAll('body *')) {
      const css = getComputedStyle(el), box = el.getBoundingClientRect();
      const svg = el instanceof SVGElement;
      const hasBox = svg ? box.width > 0 || box.height > 0 : box.width > 0 && box.height > 0;
      if (!hasBox || !el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) ||
          css.display === 'none' || css.visibility !== 'visible') continue;
      const own = [...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
      if ((own && css.color === bad) || (el instanceof SVGElement && (css.fill === bad || css.stroke === bad)))
        hits.push({ tag: el.tagName, text: el.textContent.trim(), color: css.color, fill: css.fill, stroke: css.stroke });
    }
    return { state, token, bad, hits };
  });
  ctx.note(JSON.stringify(result)); await shot(ctx, 'empty-data');
  ctx.assert(result.state === '待命' && !!result.token, '未处于待命或缺少 --bad');
  ctx.assert(result.hits.length === 0, '待命时存在 --bad 文字或 SVG');
}

// 保留 shots.mjs 的量法；增加纵向截断检查，不截短失败列表。
export function layoutMetrics() {
  const de = document.documentElement;
  const vis = e => (e.offsetParent !== null || e instanceof SVGElement || getComputedStyle(e).position === 'fixed') &&
    getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none';
  let minFont = Infinity, minEl = '', textCount = 0;
  const describe = el => (el.id || String(el.className?.baseVal ?? el.className) || el.tagName) + ':' + el.textContent.trim().slice(0, 40);
  for (const e of document.querySelectorAll('body *')) {
    if (!vis(e) || ![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    const r = e.getBoundingClientRect(); if (!r.width || !r.height) continue;
    textCount++;
    const size = parseFloat(getComputedStyle(e).fontSize);
    if (size < minFont) { minFont = size; minEl = describe(e); }
  }
  const clipped = [...document.querySelectorAll('body *')].filter(e => {
    if (!vis(e) || e.childElementCount || !e.textContent.trim() || e instanceof SVGElement) return false;
    const css = getComputedStyle(e);
    return (e.scrollWidth > e.clientWidth + 1 && css.overflowX !== 'visible') ||
      (e.scrollHeight > e.clientHeight + 1 && ['hidden', 'clip'].includes(css.overflowY));
  }).map(describe);
  const clippedCards = [...document.querySelectorAll('.card,.cam')].filter(vis)
    .filter(e => e.scrollHeight > e.clientHeight + 2 && getComputedStyle(e).overflowY === 'hidden').map(describe);
  return { pageScroll: de.scrollHeight > innerHeight + 1, hOverflow: de.scrollWidth > innerWidth + 1,
    minFont, minEl, textCount, clipped, clippedCards };
}

export async function checkLayout(ctx) {
  const failures = [];
  for (const [width, height] of [[1440, 900], [1512, 982], [1920, 1080]]) {
    await ctx.page.setViewportSize({ width, height });
    for (const name of PAGES) {
      try {
        await fresh(ctx, name);
        await ctx.page.evaluate(() => document.fonts.ready);
        await ctx.page.waitForTimeout(300);
        const metrics = await ctx.page.evaluate(layoutMetrics);
        ctx.note(`${width}×${height} ${name}: ${JSON.stringify(metrics)}`);
        await shot(ctx, `layout-${name}-${width}x${height}`);
        if (metrics.pageScroll || metrics.hOverflow || !metrics.textCount || metrics.minFont < 12 || metrics.clipped.length || metrics.clippedCards.length)
          failures.push(`${name} ${width}×${height}`);
      } catch (error) { ctx.note(`${width}×${height} ${name}: ${error.message}`); failures.push(`${name} ${width}×${height}`); }
    }
  }
  await ctx.page.setViewportSize({ width: 1440, height: 900 });
  ctx.assert(failures.length === 0, `布局失败：${failures.join('、')}`);
}
