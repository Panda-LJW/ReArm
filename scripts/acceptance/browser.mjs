import { createRequire } from 'node:module';
import { readdirSync, existsSync, readFileSync, mkdirSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

export const BASE = 'http://127.0.0.1:8031';
const require = createRequire(import.meta.url);

function installedBrowser() {
  const npx = join(homedir(), '.npm/_npx');
  const pc = readdirSync(npx).sort().map(d => join(npx, d, 'node_modules/playwright-core'))
    .find(path => existsSync(join(path, 'package.json')));
  if (!pc) throw new Error('未找到 ~/.npm/_npx/*/node_modules/playwright-core；未安装新依赖');
  const cache = join(homedir(), 'Library/Caches/ms-playwright');
  const versions = readdirSync(cache).filter(d => d.startsWith('chromium_headless_shell-'))
    .sort((a, b) => Number(b.split('-').at(-1)) - Number(a.split('-').at(-1)));
  const executables = versions.flatMap(d => readdirSync(join(cache, d))
    .map(platform => join(cache, d, platform, 'chrome-headless-shell')));
  const chrome = executables.find(existsSync);
  if (!chrome) throw new Error('未找到指定缓存里的 chrome-headless-shell；未换用其他浏览器');
  return { chromium: require(pc).chromium, chrome, pc };
}

export async function setupBrowser(ctx) {
  if (process.env.REARM_SERVER_READY !== '0') {
    const path = join(ctx.out, 'server.log');
    throw new Error('8031 临时服务未就绪，未尝试启动浏览器。\n' +
      (existsSync(path) ? readFileSync(path, 'utf8') : '没有服务日志；请通过 node1.sh 运行。'));
  }
  const { chromium, chrome, pc } = installedBrowser();
  ctx.browserPaths = { chrome, pc };
  ctx.browser = await chromium.launch({ executablePath: chrome, headless: true,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  ctx.context = await ctx.browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  // 拦截非本机 HTTP 请求，记录为错误；不允许测试页面访问另一台主机。
  await ctx.context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === BASE || ['data:', 'blob:'].includes(url.protocol)) return route.continue();
    ctx.errors.push(`禁止外部请求：${url.href}`);
    return route.abort('blockedbyclient');
  });
  await ctx.context.exposeBinding('__node1Command', (_source, entry) => ctx.commands.push(entry));
  await ctx.context.addInitScript(() => {
    const pending = [];
    window.__node1Audit = { pending, hookSeen: false };
    // 只观察记录数组的追加，不发送命令、不改数组内容。跨 reload/reset 保留完整记录。
    let mock;
    const wrapped = new WeakSet();
    Object.defineProperty(window, '__rearmMock', { configurable: true, get: () => mock, set(value) {
      mock = value;
      const commands = value?.commands;
      if (!Array.isArray(commands) || wrapped.has(commands)) return;
      wrapped.add(commands); window.__node1Audit.hookSeen = true;
      const record = entry => pending.push(window.__node1Command(JSON.parse(JSON.stringify(entry))));
      commands.forEach(record);
      const push = commands.push;
      Object.defineProperty(commands, 'push', { configurable: true, writable: true,
        value(...entries) { entries.forEach(record); return Reflect.apply(push, this, entries); } });
    } });
    // 防止任何地址参数或错误实现连到真主机；本机旧页面 /ws 仍可被观测。
    const NativeWebSocket = window.WebSocket;
    window.WebSocket = class extends NativeWebSocket {
      constructor(url, protocols) {
        const parsed = new URL(url, location.href);
        if (parsed.hostname !== '127.0.0.1' || parsed.port !== '8031')
          throw new Error('验收禁止外部 WebSocket：' + parsed.href);
        super(url, protocols);
      }
    };
  });
  ctx.page = await ctx.context.newPage();
  ctx.page.setDefaultTimeout(3000);
  ctx.page.setDefaultNavigationTimeout(10000);
  ctx.page.on('pageerror', error => ctx.errors.push(`pageerror: ${error.message}`));
  ctx.page.on('console', message => { if (message.type() === 'error') ctx.errors.push(`console.error: ${message.text()}`); });
  await ctx.page.goto(BASE);
}

export async function flushCommands(ctx) {
  if (ctx.page && !ctx.page.isClosed()) {
    const hook = await ctx.page.evaluate(async () => {
      await Promise.all(window.__node1Audit?.pending || []);
      return { array: Array.isArray(window.__rearmMock?.commands), observed: !!window.__node1Audit?.hookSeen };
    });
    ctx.commandHookSeen ||= hook.array && hook.observed;
  }
}

export async function shot(ctx, name, evidenceKey) {
  mkdirSync(join(ctx.out, 'screenshots'), { recursive: true });
  const file = `${ctx.runId}-${name}.png`;
  await ctx.page.screenshot({ path: join(ctx.out, 'screenshots', file) });
  ctx.current.shots.push(file);
  if (evidenceKey) ctx.evidence.set(evidenceKey, file);
  return file;
}

export async function fresh(ctx, name = 'production') {
  await flushCommands(ctx);
  await ctx.page.goto(`${BASE}/#${name}`);
  // 只换 hash 的 goto 不会重新加载文档，上一条检查留下的弹窗和状态会带过来；这里强制重载。
  await ctx.page.reload();
  // 等连接就绪（急停可点）再开始量，否则会量到启动瞬间“连接就绪后可操作”的过渡态。
  await ctx.page.locator('[data-action="estop"]:not([aria-disabled="true"])').waitFor({ state: 'visible' });
  await ctx.page.locator(`[data-page="${name}"]`).waitFor({ state: 'visible' });
}

export async function nav(ctx, name) {
  await ctx.page.locator(`[data-nav="${name}"]`).click();
  const root = ctx.page.locator(`[data-page="${name}"]`);
  await root.waitFor({ state: 'visible' });
  ctx.assert((await root.innerText()).trim().length > 0, `${name} 页面内容为空`);
  return root;
}

export async function status(ctx, text, timeout = 3000) {
  await ctx.page.waitForFunction(expected => document.querySelector('[data-status]')?.textContent.trim() === expected,
    text, { timeout });
}

export async function openConfirmation(ctx) {
  const recipe = ctx.page.locator('[data-recipe]').first();
  await recipe.waitFor({ state: 'attached' });
  const tag = await recipe.evaluate(el => el.tagName);
  if (tag === 'OPTION') {
    const value = await recipe.getAttribute('value');
    await recipe.locator('..').selectOption(value);
  } else if (tag === 'SELECT') {
    const value = await recipe.locator('option').first().getAttribute('value');
    await recipe.selectOption(value);
  } else if (await recipe.isVisible()) await recipe.click();
  await ctx.page.locator('[data-action="start"]').click();
  const dialog = ctx.page.getByRole('dialog');
  await dialog.waitFor({ state: 'visible' });
  ctx.assert((await dialog.innerText()).includes('确认工作区附近无人'), '确认框缺少工作区无人提示');
  return dialog;
}

export async function readyToRun(ctx) {
  await openConfirmation(ctx);
  await ctx.page.locator('[data-confirm-check]').check();
  const confirm = ctx.page.locator('[data-action="confirm"]');
  ctx.assert(await confirm.getAttribute('aria-disabled') !== 'true', '勾选后确认仍不可用');
  return confirm;
}
