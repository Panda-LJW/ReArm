import { fresh, nav, openConfirmation, shot } from './browser.mjs';
import { PAGES, buttonWords } from './surface-checks.mjs';
import { disabledTooltips } from './tooltip-check.mjs';

const FORBIDDEN = ['模拟', 'mock', 'Mock', '教师', 'teacher', 'Fable', '待开发', '敬请期待'];
export async function visitLibrary(ctx, tab = 'parts') {
  await nav(ctx, 'parts');
  await ctx.page.locator(`[data-tab="${tab}"]`).click();
}

export async function openDoc(ctx, target) {
  await fresh(ctx, 'parts'); await visitLibrary(ctx, target === 'part' ? 'parts' : 'recipes');
  await ctx.page.locator(target === 'part' ? '[data-part]' : '[data-recipe-doc]').first().click();
  await ctx.page.locator('[data-chart="deviation"]:visible').first().waitFor({ state: 'visible' });
  await shot(ctx, `${target}-doc`, `${target}-doc`);
}

// 依赖清单里的按钮文案和可访问字段名称；不添加页面未约定的测试入口。
export async function newFlow(ctx, target, capture = async () => {}) {
  await fresh(ctx, 'parts'); await visitLibrary(ctx, target === 'part' ? 'parts' : 'recipes');
  await ctx.page.getByRole('button', { name: target === 'part' ? '新增零件' : '新增配方', exact: true }).click();
  const flow = ctx.page.locator('[data-new-flow]:visible');
  await flow.waitFor({ state: 'visible' });
  const steps = await flow.locator('[data-step]').count();
  ctx.assert(steps === 3, `新增 ${target} 流程步骤数=${steps}，期望 3`);
  await capture(`${target} 新增步骤1`); await shot(ctx, `${target}-step1`);
  if (target === 'part') {
    await flow.getByRole('button', { name: '拍照识别', exact: true }).click();
    await flow.getByRole('textbox', { name: /名称/ }).waitFor({ state: 'visible' });
    const name = flow.getByRole('textbox', { name: /名称/ });
    const code = flow.getByRole('textbox', { name: /编号/ });
    ctx.assert((await name.inputValue()).trim() && (await code.inputValue()).trim(), '拍照后没有名称或编号');
  } else {
    const name = flow.getByRole('textbox', { name: /名称/ });
    await name.fill(`验收配方-${ctx.runId}`);
    const fixture = flow.getByRole('combobox', { name: /工装/ });
    const value = await fixture.locator('option').evaluateAll(options => options.find(o => !o.disabled && o.value)?.value);
    ctx.assert(!!value, '新增配方没有可选工装'); await fixture.selectOption(value);
    const parts = flow.getByRole('checkbox');
    ctx.assert(await parts.count() >= 2, '新增配方没有两个可选零件');
    await parts.nth(0).check(); await parts.nth(1).check();
  }
  // 若步骤1有确认动作，先完成它；不能替代后续的“开始训练”。
  const confirm = flow.getByRole('button', { name: /^(确认|确认零件|确认配方|下一步)$/ });
  if (await confirm.count() && await confirm.first().isVisible()) await confirm.first().click();
  const train = flow.getByRole('button', { name: '开始训练', exact: true });
  await train.waitFor({ state: 'visible' });
  await capture(`${target} 开始训练前`);
  await train.click();
  await ctx.page.waitForFunction(() => document.querySelector('[data-status]')?.textContent.trim() === '训练中');
  await capture(`${target} 新增步骤2`); await shot(ctx, `${target}-step2`);
  await ctx.page.waitForFunction(() => [...document.querySelectorAll('[data-new-flow]')]
    .some(el => el.getBoundingClientRect().width && /训练完成\s*·\s*已收录/.test(el.innerText)), null, { timeout: 30000 });
  await capture(`${target} 新增步骤3`); await shot(ctx, `${target}-step3`);
  ctx.note(`${target} 新增三步完成，训练自动结束并显示“训练完成 · 已收录”`);
}

export async function checkWording(ctx) {
  const failures = [], seen = [];
  const capture = async name => {
    const text = await ctx.page.locator('body').innerText();
    const hits = FORBIDDEN.filter(word => text.includes(word));
    seen.push(name);
    if (hits.length) failures.push(`${name}: ${hits.join('、')}`);
    // 第9条的“所有按钮”也覆盖弹窗、文档和新增三步；错误归回第9条。
    try { await buttonWords(ctx); await disabledTooltips(ctx); } catch (error) { ctx.buttonFailures.push(`${name}: ${error.message}`); }
  };
  const attempt = async (name, action) => {
    try { await action(); } catch (error) { failures.push(`${name}: ${error.message}`); }
  };
  for (const name of PAGES) await attempt(name, async () => { await fresh(ctx, name); await capture(name); });
  await attempt('确认框', async () => { await fresh(ctx); await openConfirmation(ctx); await capture('确认框'); });
  for (const target of ['part', 'recipe']) {
    await attempt(`${target} 文档`, async () => { await openDoc(ctx, target); await capture(`${target} 文档`); });
    await attempt(`${target} 新增流程`, () => newFlow(ctx, target, capture));
  }
  ctx.note(`已读取 innerText 的界面：${seen.join('、')}`);
  ctx.assert(failures.length === 0, failures.join('；'));
}

export async function checkLibrary(ctx) {
  await fresh(ctx, 'parts'); await visitLibrary(ctx);
  const parts = await ctx.page.locator('[data-part]:visible').count();
  await visitLibrary(ctx, 'recipes');
  const recipes = await ctx.page.locator('[data-recipe-doc]:visible').count();
  ctx.note(`零件=${parts}；配方=${recipes}`);
  ctx.assert(parts >= 4 && recipes >= 1, '零件少于4个或配方少于1个');
  await openDoc(ctx, 'part');
  const force = (await ctx.page.locator('[data-force]:visible').innerText()).trim();
  ctx.assert(/^\d+\.\d N$/.test(force), `夹持力格式错误：${force}`);
  ctx.note(`零件文档偏差曲线可见，夹持力=${force}`);
  await openDoc(ctx, 'recipe');
  await newFlow(ctx, 'part');
  // 不刷新，必须核对同次训练后库里的真实增量。
  await visitLibrary(ctx);
  const after = await ctx.page.locator('[data-part]:visible').count();
  ctx.note(`新增后零件数=${after}，原=${parts}`);
  ctx.assert(after === parts + 1, '三步完成后零件列表没有恰好新增1项');
  await shot(ctx, 'library-after-training');
}
