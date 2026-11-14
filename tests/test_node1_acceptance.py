"""验收器的反例测试；不启动浏览器、不占端口、不修改产品文件。"""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def node(script):
    executable = shutil.which('node')
    assert executable, '节点①验收要求已有 Node'
    result = subprocess.run([executable, '--input-type=module', '-e', script],
                            cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('source,host', [
    ('const host = "192.168.2.3";', '192.168.2.3'),
    ('const url = "wss://robot.example:8031/stream";', 'robot.example'),
    ('const url = "https://localhost@robot.example/api";', 'robot.example'),
    ('// ws://主机:端口/路径', '主机:端口'),
    ('document.createElementNS("http://www.w3.org/2000/svg", "path")', 'www.w3.org'),
])
def test_address_scan_rejects_external_literals_including_comments_and_namespace(source, host):
    hits = node(f"""
import {{ addressHits }} from './scripts/acceptance/static-checks.mjs';
console.log(JSON.stringify(addressHits({json.dumps(source)})));
""")
    assert host in [hit['host'] for hit in hits]


def test_address_scan_preserves_local_hosts_and_ignores_empty_protocol_fragments():
    hits = node("""
import { addressHits } from './scripts/acceptance/static-checks.mjs';
console.log(JSON.stringify(addressHits('"http://localhost:8031/"; "ws://127.0.0.1:8031/"; "ws://"; "wss://"; 999.1.1.1;')));
""")
    assert hits and all(hit['host'] in {'localhost', '127.0.0.1'} for hit in hits)


def test_production_sequence_rejects_missing_extra_reordered_and_nonadjacent_repeat():
    result = node("""
import { EXPECTED_PHASES as expected, normalizePhases } from './scripts/acceptance/production-checks.mjs';
const valid = ['自检中', '自检中', '就绪', ...expected.slice(1)];
const invalid = [expected.slice(1), [...expected, '完成'],
  [expected[1], expected[0], ...expected.slice(2)],
  [...expected.slice(0, -1), '就绪', '完成', '待命']];
const equals = input => JSON.stringify(normalizePhases(input)) === JSON.stringify(expected);
console.log(JSON.stringify({ valid: equals(valid), invalid: invalid.map(equals) }));
""")
    assert result == {'valid': True, 'invalid': [False] * 4}


@pytest.mark.parametrize('exit_code,passed', [('1', '324'), ('0', '323'), ('0', '0')])
def test_pytest_gate_does_not_pass_on_failure_or_insufficient_count(exit_code, passed):
    result = node(f"""
import {{ checkPytest }} from './scripts/acceptance/static-checks.mjs';
process.env.REARM_PYTEST_EXIT = {json.dumps(exit_code)};
process.env.REARM_PYTEST_PASSED = {json.dumps(passed)};
const notes = []; let error = null;
try {{ checkPytest({{note: x => notes.push(x), assert: (ok, text) => {{ if (!ok) throw new Error(text); }} }}); }}
catch (e) {{ error = e.message; }}
console.log(JSON.stringify({{notes,error}}));
""")
    assert result['error'] == 'pytest 必须全部通过且通过数 ≥324'
