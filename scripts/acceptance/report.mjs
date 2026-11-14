import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { git, MAIN_AT_START } from './static-checks.mjs';

const cell = value => String(value).replaceAll('|', '\\|').replace(/\r?\n/g, '<br>');
export const evidenceNames = [
  ['confirm', '确认框'], ['selfcheck', '自检'], ['recognize', '识别'], ['pick', '抓取'],
  ['place', '放置'], ['inspect', '检查'], ['done', '完成'], ['idle', '待命'],
  ['part-doc', '零件文档'], ['recipe-doc', '配方文档'],
];

export function writeReport(ctx) {
  const passed = ctx.results.filter(r => r.ok).length;
  const lines = ['# 节点①控制台验收报告', '', `时间：${new Date().toISOString()}`, '',
    `结果：${passed}/17 通过。失败或环境受阻均不算通过。`, '',
    '启动：在仓库根运行 `scripts/acceptance/node1.sh`。脚本固定使用 `127.0.0.1:8031`、独立临时数据目录，退出时关闭本次服务。', '',
    `本次临时数据目录：${process.env.REARM_ACCEPTANCE_DATA_DIR || '未创建'}`, '',
    '| # | 检查 | 结果 | 实测值 | 截图文件名 |', '|---|---|---|---|---|'];
  for (const row of ctx.results) {
    lines.push(`| ${row.id} | ${row.name} | ${row.ok ? '通过' : '失败'} | ${cell(row.notes.join('；'))} | ${row.shots.map(s => `[${s}](screenshots/${s})`).join('、') || '未取得'} |`);
  }
  lines.push('', '## 关键截图（清单 9.4）', '', '| 画面 | 本次证据 |', '|---|---|');
  for (const [key, name] of evidenceNames) {
    const file = ctx.evidence.get(key);
    lines.push(`| ${name} | ${file ? `[${file}](screenshots/${file})` : '未取得，不能作为已验证画面'} |`);
  }
  lines.push('', '## vendor 地址命中', '', '`vendor/` 是第三方库，按任务书单独列出，不计第 16 条失败；其他目录没有地址豁免。', '');
  for (const hit of ctx.vendorHits || []) lines.push(`- ${hit.file}:${hit.line} ${hit.value}`);
  if (!ctx.vendorHits?.length) lines.push('本次未发现命中。');
  lines.push('', '## 环境错误原文', '');
  if (ctx.infrastructure) lines.push('```text', ctx.infrastructure, '```');
  else lines.push('无启动阻拦。');
  lines.push('', '## 页面错误', '');
  if (ctx.errors.length) lines.push('```text', ...ctx.errors, '```');
  else lines.push(ctx.infrastructure ? '浏览器检查未执行，不能据此声称零错误。' : '本次未捕获 pageerror 或 console.error。');
  let commits;
  try { commits = git('log', 'main..HEAD', '--oneline') || '（无）'; }
  catch (error) { commits = `读取失败：${error.message}`; }
  lines.push('', '## 提交列表', '', `main 开工基线：\`${MAIN_AT_START}\`。以下为 \`git log main..HEAD --oneline\` 原始结果，包含本节点之前的分支历史。`, '',
    '```text', commits, '```', '', '## 改了什么、哪些没做', '',
    '本轮 T0 新增验收入口和分项检查，页面与业务代码未修改。当前工作区、提交状态见 LOG.md 的本轮记录。', '',
    'T1–T8 未执行；训练录像、零件和工装 3D 模型、后端联调未做。缺失钩子、功能或截图如实记失败，不伪造结果。', '',
    '验收标准按清单与任务书原文执行。现有非 vendor 源码若含 SVG 命名空间或地址示例，也按第 16 条计失败，未放宽扫描规则。', '');
  writeFileSync(join(ctx.out, '报告.md'), lines.join('\n'));
  writeFileSync(join(ctx.out, 'results.json'), JSON.stringify({
    timestamp: new Date().toISOString(), mainBaseline: MAIN_AT_START,
    results: ctx.results, infrastructure: ctx.infrastructure || null, errors: ctx.errors,
    evidence: Object.fromEntries(ctx.evidence), vendorHits: ctx.vendorHits,
    commands: ctx.commands, addresses: ctx.addressFailures,
  }, null, 2) + '\n');
}
