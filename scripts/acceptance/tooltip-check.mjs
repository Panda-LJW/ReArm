// 所有可见不可用按钮共用同一口径，不给确认框或其他按钮设置例外。
export async function disabledTooltips(ctx) {
  const buttons = ctx.page.locator('button[aria-disabled="true"]:visible,[role="button"][aria-disabled="true"]:visible');
  const count = await buttons.count();
  for (let i = 0; i < count; i++) {
    const button = buttons.nth(i), text = (await button.innerText()).trim();
    ctx.assert(await button.evaluate(el => getComputedStyle(el).cursor) === 'help', `${text}: cursor 不是 help`);
    await ctx.page.mouse.move(0, 0);
    // 清掉上一轮鼠标/键盘焦点留下的提示，不能用 DOM 改动隐藏提示。
    await ctx.page.evaluate(() => document.activeElement?.blur());
    await ctx.page.mouse.move(0, 0);
    await button.evaluate(el => {
      const visibleTips = () => [...document.querySelectorAll('[role="tooltip"][data-tip]')].filter(tip => {
        const box = tip.getBoundingClientRect(), css = getComputedStyle(tip);
        return box.width > 0 && box.height > 0 && css.display !== 'none' && css.visibility !== 'hidden' && Number(css.opacity) > 0;
      });
      window.__node1Tip = { before: visibleTips().length, samples: [], done: false };
      el.addEventListener('pointerenter', () => {
        const start = performance.now(), audit = window.__node1Tip;
        const sample = () => {
          const tips = visibleTips();
          audit.samples.push({ ms: performance.now() - start, visible: tips.length > 0,
            text: tips.map(t => t.innerText.trim()).join(' ') });
          if (performance.now() - start < 1200) requestAnimationFrame(sample);
          else audit.done = true;
        };
        sample();
      }, { once: true, capture: true });
    });
    const r = await button.boundingBox();
    await ctx.page.mouse.move(r.x + r.width / 2, r.y + r.height / 2);
    await ctx.page.waitForFunction(() => window.__node1Tip.done);
    const audit = await ctx.page.evaluate(() => window.__node1Tip);
    const first = audit.samples.find(s => s.visible), last = audit.samples.at(-1);
    ctx.note(`${text}: cursor=help，提示首现=${first?.ms ?? '未出现'} ms，1.2秒采样=${JSON.stringify(last)}`);
    ctx.assert(audit.before === 0 && audit.samples.every(s => s.ms >= 800 || !s.visible), `${text}: 0.8 秒前提示框可见`);
    ctx.assert(last.visible && last.text.length > 0, `${text}: 1.2 秒时未显示非空原因`);
    await ctx.page.mouse.move(0, 0);
  }
  return count;
}
