// 只由 node1.sh 启动；17 条逐个执行，失败不短路，也不改变产品状态来伪造通过。
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';
import { checkPytest, checkAddresses, checkHygiene } from './static-checks.mjs';
import { setupBrowser, flushCommands, shot } from './browser.mjs';
import { checkConfirmation, checkProduction, checkResult, checkEstop, checkReset } from './production-checks.mjs';
import { checkNavigation, checkButtons, checkTwinLabels, checkEmptyData, checkLayout } from './surface-checks.mjs';
import { checkWording, checkLibrary } from './library-checks.mjs';
import { writeReport } from './report.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
process.chdir(root);
const ctx = {
  root, out: join(root, 'docs/路演/验收/节点1'), runId: new Date().toISOString().replace(/[:.]/g, '-'),
  results: [], errors: [], commands: [], evidence: new Map(), buttonFailures: [], commandHookSeen: false,
  assert(ok, message) { if (!ok) throw new Error(message); },
  note(value) { this.current.notes.push(String(value)); },
};
mkdirSync(join(ctx.out, 'screenshots'), { recursive: true });

async function checkErrors(ctx) {
  // 必须到整个浏览器流程结束才定案；此处只确认监听已挂好。
  ctx.assert(!!ctx.page, '浏览器未启动，页面错误不能判通过');
  ctx.note('pageerror/console.error 监听覆盖整个运行；结果在所有操作后归并');
}

async function checkNoLaser(ctx) {
  await flushCommands(ctx);
  ctx.assert(ctx.commandHookSeen, '未观测到 window.__rearmMock.commands 数组，不能凭空数组判通过');
  const laser = ctx.commands.filter(entry => String(entry.cmd || '').startsWith('laser_'));
  ctx.note(`跨页面累计指令=${ctx.commands.length}，laser_ 指令=${JSON.stringify(laser)}`);
  ctx.assert(laser.length === 0, '流程发出了 laser_ 指令');
}

const checks = [
  [1, '单元测试', checkPytest, false],
  [2, '页面报错', checkErrors, true],
  [3, '导航', checkNavigation, true],
  [4, '二次确认', checkConfirmation, true],
  [5, '生产流程', checkProduction, true],
  [6, '检查结果', checkResult, true],
  [7, '急停', checkEstop, true],
  [8, '一键重置', checkReset, true],
  [9, '状态和按钮分开', checkButtons, true],
  [10, '孪生标签', checkTwinLabels, true],
  [11, '空数据', checkEmptyData, true],
  [12, '措辞', checkWording, true],
  [13, '零件库', checkLibrary, true],
  [14, '布局', checkLayout, true],
  [15, '不发激光指令', checkNoLaser, true],
  [16, '不写死地址', checkAddresses, false],
  [17, '仓库卫生', checkHygiene, false],
];

let setupAttempted = false;
try {
  for (const [id, name, check, needsBrowser] of checks) {
    const row = { id, name, ok: false, notes: [], shots: [] };
    ctx.current = row; ctx.results.push(row);
    try {
      if (needsBrowser && !setupAttempted) {
        setupAttempted = true;
        try { await setupBrowser(ctx); }
        catch (error) {
          ctx.infrastructure = String(error.stack || error);
          writeFileSync(join(ctx.out, 'infrastructure.log'), ctx.infrastructure + '\n');
        }
      }
      if (needsBrowser && ctx.infrastructure) throw new Error('未执行：服务或浏览器启动受阻，见 infrastructure.log 和报告错误原文');
      await check(ctx); row.ok = true;
    } catch (error) {
      ctx.note(error.message);
      if (needsBrowser && ctx.page && !ctx.infrastructure) {
        try { await shot(ctx, `failure-${id}`); } catch (captureError) { ctx.note(`截图失败：${captureError.message}`); }
      }
    }
    console.log(`[${id}] ${row.ok ? 'PASS' : 'FAIL'} ${name}: ${row.notes.join('；')}`);
  }
} finally {
  if (ctx.page && !ctx.infrastructure) {
    try { await flushCommands(ctx); } catch (error) { ctx.errors.push(`指令留证失败：${error.message}`); }
  }
  if (ctx.browser) {
    try { await ctx.browser.close(); } catch (error) { ctx.errors.push(`关闭浏览器失败：${error.message}`); }
  }
  const errors = ctx.results.find(r => r.id === 2);
  if (errors && !ctx.infrastructure) {
    errors.ok = ctx.errors.length === 0;
    errors.notes = [`pageerror/console.error 及浏览器错误共 ${ctx.errors.length} 条`, ...ctx.errors];
  }
  const buttons = ctx.results.find(r => r.id === 9);
  if (buttons && ctx.buttonFailures.length) { buttons.ok = false; buttons.notes.push(...ctx.buttonFailures); }
  writeReport(ctx);
}
console.log('\n最终逐条结果（含整个流程的页面错误）：');
for (const row of ctx.results) console.log(`${row.id}. ${row.ok ? '通过' : '失败'} ${row.name}`);
console.log(`报告：${join(ctx.out, '报告.md')}`);
process.exitCode = ctx.results.length === 17 && ctx.results.every(row => row.ok) ? 0 : 1;
