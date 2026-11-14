import { fresh, status, openConfirmation, readyToRun, shot, flushCommands } from './browser.mjs';

export const EXPECTED_PHASES = ['自检中', '识别中', '抓取中', '放置中', '抓取中', '放置中', '检查中', '完成', '待命'];
export const normalizePhases = values => values.filter((v, i) => i === 0 || v !== values[i - 1]).filter(v => v !== '就绪');

// 在真实点击前安装；记录文本变化而不是轮询，旁路指标不参与控制页面。
export async function observeStatus(ctx, trigger) {
  await ctx.page.evaluate(triggerSelector => {
    window.__node1Status?.observer.disconnect();
    const el = document.querySelector('[data-status]');
    if (!el) throw new Error('缺少 [data-status]');
    let last = el.textContent.trim();
    const audit = { events: [], started: null, finished: null };
    const record = () => {
      const text = document.querySelector('[data-status]')?.textContent.trim();
      if (text === last) return;
      last = text;
      if (audit.started !== null) {
        audit.events.push({ text, ms: performance.now() - audit.started });
        if (text === '待命') audit.finished = performance.now();
      }
    };
    audit.observer = new MutationObserver(record);
    audit.observer.observe(document.body, { subtree: true, characterData: true, childList: true });
    document.querySelector(triggerSelector).addEventListener('click', () => { audit.started = performance.now(); },
      { once: true, capture: true });
    window.__node1Status = audit;
  }, trigger);
}

export async function checkConfirmation(ctx) {
  await fresh(ctx);
  const dialog = await openConfirmation(ctx), confirm = ctx.page.locator('[data-action="confirm"]');
  const check = ctx.page.locator('[data-confirm-check]');
  ctx.assert(!await check.isChecked(), '勾选框默认应未勾选');
  ctx.assert(await confirm.getAttribute('aria-disabled') === 'true', '未勾选时 aria-disabled 必须为 true');
  ctx.assert(!await confirm.evaluate(el => el.hasAttribute('disabled')), '不能用原生 disabled 代替 aria-disabled');
  await flushCommands(ctx);
  const before = ctx.commands.length, rect = await confirm.boundingBox();
  await ctx.page.mouse.click(rect.x + rect.width / 2, rect.y + rect.height / 2);
  await confirm.focus(); await confirm.press('Enter'); await confirm.press('Space');
  await ctx.page.waitForTimeout(150); await flushCommands(ctx);
  ctx.assert(await dialog.isVisible() && ctx.commands.length === before, '未勾选时点击/回车/空格产生了操作');
  await status(ctx, '待命');
  await shot(ctx, 'confirm', 'confirm');
  await check.check();
  ctx.assert(await confirm.getAttribute('aria-disabled') !== 'true', '勾选后未启用确认');
  ctx.assert(!await confirm.evaluate(el => el.hasAttribute('disabled')), '勾选后确认仍有 disabled');
  ctx.note('未勾选不可用，鼠标/Enter/Space 无效；勾选后可用');
  await ctx.page.keyboard.press('Escape');
}

export async function checkProduction(ctx) {
  ctx.production = null;
  await fresh(ctx);
  const beforeText = (await ctx.page.locator('[data-count="sets"]').innerText()).trim();
  ctx.assert(/^\d+$/.test(beforeText), `完成套数不是整数：${beforeText}`);
  const confirm = await readyToRun(ctx);
  await shot(ctx, 'production-confirm', 'confirm');
  await observeStatus(ctx, '[data-action="confirm"]');
  await confirm.click();
  const captures = new Map([['自检中', 'selfcheck'], ['识别中', 'recognize'], ['抓取中', 'pick'],
    ['放置中', 'place'], ['检查中', 'inspect'], ['完成', 'done'], ['待命', 'idle']]);
  const captured = new Set();
  // 截图循环仅负责留证；顺序和总时长以 MutationObserver 的浏览器时钟记录为准。
  const deadline = Date.now() + 91000;
  let audit;
  while (Date.now() < deadline) {
    audit = await ctx.page.evaluate(() => ({ events: window.__node1Status.events,
      elapsed: performance.now() - window.__node1Status.started,
      finished: window.__node1Status.finished === null ? null : window.__node1Status.finished - window.__node1Status.started,
      current: document.querySelector('[data-status]')?.textContent.trim() }));
    const key = captures.get(audit.current);
    if (key && !captured.has(key) && (key !== 'idle' || audit.events.length)) {
      await shot(ctx, `production-${key}`, key); captured.add(key);
    }
    if (audit.finished !== null || audit.elapsed > 90000) break;
    await ctx.page.waitForTimeout(40);
  }
  const values = normalizePhases(audit.events.map(e => e.text));
  ctx.note(`状态=${JSON.stringify(values)}；回待命耗时=${audit.finished ?? '未完成'} ms`);
  ctx.production = { before: Number(beforeText), audit };
  ctx.assert(JSON.stringify(values) === JSON.stringify(EXPECTED_PHASES), '状态序列必须精确等于规定的 9 项');
  ctx.assert(audit.finished !== null && audit.finished <= 90000, '从确认到待命超过 90 秒或未完成');
  ctx.assert(captured.size === captures.size, '缺少生产关键阶段截图');
}

export async function checkResult(ctx) {
  ctx.assert(ctx.production?.audit.finished !== null && !!ctx.production, '第 5 条没有完成一次生产，无法核对增量');
  const result = (await ctx.page.locator('[data-result]').innerText()).trim();
  const after = Number((await ctx.page.locator('[data-count="sets"]').innerText()).trim());
  ctx.note(`检查结果=${result}；完成套数 ${ctx.production.before} → ${after}`);
  ctx.assert(/^(到位|偏差 \d+\.\d mm)$/.test(result), '检查结果格式不符');
  ctx.assert(after === ctx.production.before + 1, '完成套数未恰好增加 1');
  await shot(ctx, 'result');
}

export async function checkEstop(ctx) {
  ctx.estopReached = false;
  await fresh(ctx);
  const estop = ctx.page.locator('[data-action="estop"]');
  const geometry = await estop.evaluate(el => {
    const r = el.getBoundingClientRect();
    const buttons = [...document.querySelectorAll('button,[role="button"]')].filter(b => {
      const box = b.getBoundingClientRect();
      return b !== el && box.width && box.height && getComputedStyle(b).visibility !== 'hidden' && box.top < r.bottom && box.bottom > r.top;
    }).map(b => b.getBoundingClientRect());
    const left = buttons.filter(b => b.right <= r.left);
    return { top: r.top, height: r.height, right: r.right,
      rightmost: buttons.every(b => b.right <= r.left),
      gap: left.length ? r.left - Math.max(...left.map(b => b.right)) : null,
      abovePages: [...document.querySelectorAll('[data-page]')].filter(p => p.getBoundingClientRect().height)
        .every(p => r.bottom <= p.getBoundingClientRect().top) };
  });
  ctx.note(`位置尺寸=${JSON.stringify(geometry)}`);
  const layoutOK = geometry.abovePages && geometry.rightmost && geometry.height >= 44 && geometry.gap !== null && geometry.gap >= 24;
  const confirm = await readyToRun(ctx); await confirm.click();
  await status(ctx, '抓取中', 30000);
  await flushCommands(ctx); const from = ctx.commands.length;
  await observeStatus(ctx, '[data-action="estop"]');
  await estop.click(); await status(ctx, '急停');
  ctx.estopReached = true;
  await ctx.page.waitForTimeout(5000);
  const audit = await ctx.page.evaluate(() => ({ events: window.__node1Status.events,
    state: document.querySelector('[data-status]')?.textContent.trim() }));
  await flushCommands(ctx);
  const hasCommand = ctx.commands.slice(from).some(entry => entry.cmd === 'estop');
  ctx.note(`急停后 5 秒状态=${audit.state}；变化=${JSON.stringify(audit.events)}；estop 指令=${hasCommand}`);
  await shot(ctx, 'estop');
  ctx.assert(layoutOK, '急停不满足顶栏最右/高度 ≥44px/左间距 ≥24px');
  ctx.assert(hasCommand && audit.events.length > 0 && audit.events.every(e => e.text === '急停') && audit.state === '急停',
    '急停未发送指令或 5 秒内继续推进状态');
}

export async function checkReset(ctx) {
  ctx.assert(ctx.estopReached, '第 7 条未实际进入急停，不能核验急停后重置');
  await status(ctx, '急停');
  // 此处与第 7 条共用页面，只点一次重置，不能 reload、确认或再点别的控件。
  await ctx.page.locator('[data-action="reset"]').click();
  await status(ctx, '待命');
  const count = (await ctx.page.locator('[data-count="sets"]').innerText()).trim();
  ctx.assert(count === '0', `重置后套数=${count}，期望 0`);
  await ctx.page.locator('[data-action="start"]').click();
  await ctx.page.getByRole('dialog').waitFor({ state: 'visible' });
  await shot(ctx, 'reset');
  ctx.note('急停后仅点一次重置即待命，套数=0；再点开始出现确认框');
  await ctx.page.keyboard.press('Escape');
}
