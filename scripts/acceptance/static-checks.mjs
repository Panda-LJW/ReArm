import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { execFileSync } from 'node:child_process';

// T0 开工时读取；以后不能随 main 移动自动更新。
export const MAIN_AT_START = '57785e8f95837f0d2384b4f5968cba225821434c';
export const git = (...args) => execFileSync('git', args, { encoding: 'utf8' }).trim();

export function checkPytest(ctx) {
  const passed = Number(process.env.REARM_PYTEST_PASSED);
  const code = Number(process.env.REARM_PYTEST_EXIT);
  ctx.note(`pytest exit=${code}，${passed} passed；原始输出：pytest.log`);
  ctx.assert(process.env.REARM_PYTEST_EXIT !== undefined && code === 0 && passed >= 324,
    'pytest 必须全部通过且通过数 ≥324');
}

function* jsFiles(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* jsFiles(path);
    else if (entry.isFile() && entry.name.endsWith('.js')) yield path;
  }
}

// 全源文本扫描，包括注释和命名空间；不擅自添加规格未允许的豁免。
export function addressHits(source) {
  const hits = [];
  for (const [index, line] of source.split('\n').entries()) {
    for (const match of line.matchAll(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g)) {
      if (match[0].split('.').every(n => Number(n) <= 255))
        hits.push({ line: index + 1, value: match[0], host: match[0] });
    }
    for (const match of line.matchAll(/\b(?:https?|wss?):\/\/([^\s/"'`<>\\]+)/g)) {
      // 没有 authority 的协议片段（如 "ws://"）不属于主机名。
      const authority = match[1].split(/[?#]/, 1)[0];
      const host = authority.slice(authority.lastIndexOf('@') + 1).replace(/:\d+$/, '');
      if (host) hits.push({ line: index + 1, value: match[0], host: host.toLowerCase() });
    }
  }
  return hits;
}

export function checkAddresses(ctx) {
  // 只有两类命中不算地址，都单列进报告：
  // 1. XML 命名空间标识符（逐字匹配下列完整字符串）：浏览器不会去连接它，createElementNS 必须写它。
  // 2. 不是合法主机名的占位写法（含中文或省略号，如注释里的 ws://主机:端口）。
  const NAMESPACES = ['http://www.w3.org/2000/svg', 'http://www.w3.org/1999/xlink'];
  const validHost = host => /^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$/.test(host);
  const bad = [], vendor = [], exempt = [];
  let files = 0;
  for (const path of jsFiles(join(ctx.root, 'rearm/ui/static'))) {
    files++;
    const file = relative(ctx.root, path);
    const lines = readFileSync(path, 'utf8').split('\n');
    for (const hit of addressHits(lines.join('\n'))) {
      const entry = { file, ...hit };
      const line = lines[hit.line - 1];
      if (file.startsWith('rearm/ui/static/vendor/')) vendor.push(entry);
      else if (!validHost(hit.host)) exempt.push({ ...entry, why: '占位写法，不是合法主机名' });
      else if (hit.host === 'www.w3.org' && NAMESPACES.some(ns => line.includes(`"${ns}"`) || line.includes(`'${ns}'`)))
        exempt.push({ ...entry, why: 'XML 命名空间标识符' });
      else if (!['localhost', '127.0.0.1'].includes(hit.host)) bad.push(entry);
    }
  }
  ctx.vendorHits = vendor;
  ctx.addressFailures = bad;
  ctx.note(`扫描 ${files} 个 JS；非 vendor 违规 ${bad.length} 处；vendor 命中 ${vendor.length} 处（单列，不计失败）`);
  for (const hit of bad) ctx.note(`${hit.file}:${hit.line} ${hit.value}`);
  for (const hit of exempt) ctx.note(`不计失败（${hit.why}）：${hit.file}:${hit.line} ${hit.value}`);
  ctx.assert(bad.length === 0, '存在 localhost、127.0.0.1 以外的地址');
}

export function checkHygiene(ctx) {
  const tracked = git('ls-files', '-z').split('\0');
  const zip = tracked.includes('海报素材包.zip');
  const main = git('rev-parse', 'main');
  ctx.note(`海报素材包.zip tracked=${zip}；main=${main}；开工基线=${MAIN_AT_START}`);
  ctx.assert(!zip && main === MAIN_AT_START, '素材包已被跟踪或 main 已改变');
}
