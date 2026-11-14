"""训练纯逻辑契约：Node + 虚拟时钟；所有激光指令只送本地 mock。"""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

MODULES = Path(__file__).resolve().parents[1] / 'rearm/ui/static/modules'
NODE = shutil.which('node')

PRELUDE = '''
import assert from "node:assert/strict";
let realConnectionAttempts = 0;
globalThis.WebSocket = class { constructor() { realConnectionAttempts++; throw Error("real WebSocket forbidden"); } };
globalThis.fetch = () => { realConnectionAttempts++; throw Error("real fetch forbidden"); };
'''


def node(script):
    if NODE is None:
        pytest.skip('node not installed')
    result = subprocess.run([NODE, '--input-type=module', '-e', PRELUDE + script
                             + '\nassert.equal(realConnectionAttempts, 0);'],
                            cwd=MODULES, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


CLOCK = '''
function fakeClock(start = 1700000000000) {
  let time = start, serial = 0;
  const tasks = new Map();
  const add = (cb, ms, repeat) => { const id = ++serial; tasks.set(id, {cb, ms, at: time + ms, repeat}); return id; };
  return {
    now: () => time,
    setTimer: (cb, ms) => add(cb, ms, true),
    setTimeout: (cb, ms) => add(cb, ms, false),
    clearTimer: id => tasks.delete(id),
    size: () => tasks.size,
    advance(ms) {
      const end = time + ms;
      for (;;) {
        const entry = [...tasks].sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
        if (!entry || entry[1].at > end) break;
        const [id, task] = entry;
        time = task.at;
        if (task.repeat) task.at += task.ms; else tasks.delete(id);
        task.cb();
      }
      time = end;
    },
  };
}
'''

IMPORTS = '''
import { createMockHost } from "./datasource/mock-host.js";
import { createLaserGuard } from "./trainer/laser-guard.js";
import { initialState, reduce } from "./trainer/store.js";
import { summarize } from "./trainer/metrics.js";
import { CONFIG } from "./trainer/config.js";
import { ARM_PARAMS } from "./arm/arm-params.js";
import { checkJoints, laserRay } from "./arm/fk.js";
'''

GUARD_FIXTURE = CLOCK + IMPORTS + '''
const clock = fakeClock();
const mock = createMockHost({ now: clock.now, setTimer: () => 0, clearTimer: () => {} });
mock.start();
const guard = createLaserGuard({ send: (...args) => mock.send(...args), now: clock.now,
  setTimer: clock.setTimer, clearTimer: clock.clearTimer });
guard.onMessage({ type: "link", online: true });
const joint = (mode = "practice", pass = 1, node = 1, settled = true) =>
  guard.onMessage({ type: "joint_state", mode, pass, node, settled });
const result = (pass = 1, node = 1) => guard.onMessage({ type: "node_result", pass, node });
const commands = () => mock.commands().map(request => request.cmd);
'''


def test_mock_demo_records_real_frames_limits_nodes_and_mutex():
    out = node(IMPORTS + '''
const messages = [], host = createMockHost({ now: () => 1700000000000, setTimer: () => 0, clearTimer: () => {} });
host.subscribe(message => messages.push(message)); host.start(); host.start();
assert.equal(messages.filter(m => m.type === "hello").length, 1);
assert.equal((await host.send("practice_start")).code, "no_demo");
assert.equal((await host.send("demo_start")).ok, true);
assert.equal((await host.send("practice_start")).code, "busy");
host.advance(5500); await host.send("demo_stop");
const demo = messages.find(m => m.type === "demo_trajectory");
const frames = messages.filter(m => m.type === "joint_state" && m.mode === "demo");
assert.deepEqual(demo.samples, frames.map(({t, q, gripper_mm}) => ({t, q, gripper_mm})));
assert.equal(demo.nodes.length, 4);
assert.ok(demo.samples.every(s => s.q.length === 6 && checkJoints(ARM_PARAMS, s.q).ok));
for (let i = 0; i < 6; i++) assert.ok(Math.max(...frames.map(f => f.q[i])) - Math.min(...frames.map(f => f.q[i])) > 0.01);
assert.ok(Math.min(...frames.map(f => f.gripper_mm)) < 15);
for (const node of demo.nodes) {
  const ray = laserRay(ARM_PARAMS, node.q);
  assert.deepEqual(node.ref_spot_base_mm, ray.origin.map((v, i) => (v + 0.25 * ray.direction[i]) * 1000));
}
await host.send("practice_start"); assert.equal((await host.send("demo_start")).code, "busy");
await host.send("practice_stop"); host.stop();
assert.ok(messages.filter(m => m.type === "hello").every(m => m.sim === true));
assert.ok(messages.filter(m => m.v).every(m => m.v === 1 && m.t >= 1700000000000 && Number.isInteger(m.seq)));
const copy = host.commands(); copy[0].cmd = "changed";
assert.equal(host.commands()[0].cmd, "practice_start");
console.log(JSON.stringify({samples: demo.samples.length, nodes: demo.nodes.length}));
''')
    assert out == {'samples': 111, 'nodes': 4}


RUN_PASSES = CLOCK + IMPORTS + '''
async function run(count, guarded = true, seed = 1) {
  const clock = fakeClock(), messages = [];
  const host = createMockHost({ now: clock.now, setTimer: () => 0, clearTimer: () => {}, seed });
  const guard = createLaserGuard({ send: (...args) => host.send(...args), now: clock.now,
    setTimer: clock.setTimer, clearTimer: clock.clearTimer });
  let state = initialState();
  host.subscribe(message => { messages.push(message); state = reduce(state, message); if (guarded) guard.onMessage(message); });
  host.start();
  clock.setTimer(() => host.advance(50), 50);
  await host.send("demo_start"); clock.advance(9000);
  // 动作走完也不自动结束：真实流程是人点第二次才结束。
  assert.equal(messages.filter(m => m.type === "demo_trajectory").length, 0);
  await host.send("demo_stop");
  assert.equal(messages.filter(m => m.type === "demo_trajectory").length, 1);
  await host.send("practice_start");
  while (messages.filter(m => m.type === "pass_result").length < count) {
    clock.advance(50);
    assert.ok(clock.now() < 1700000300000, "practice must terminate within virtual time budget");
  }
  await host.send("practice_stop"); host.stop();
  assert.ok(messages.filter(m => m.type === "joint_state").every(m => checkJoints(ARM_PARAMS, m.q).ok));
  return { messages, state, commands: host.commands(), summary: summarize(state, CONFIG) };
}
'''


def test_mock_and_guard_eight_passes_reproducible_and_physically_consistent():
    out = node(RUN_PASSES + '''
const a = await run(8), b = await run(8), c = await run(8, true, 2);
assert.deepEqual(a, b);
const nodes = a.messages.filter(m => m.type === "node_result"), passes = a.messages.filter(m => m.type === "pass_result");
assert.equal(nodes.length, 32); assert.ok(nodes.every(n => n.valid));
for (let pass = 1; pass <= 8; pass++) assert.deepEqual(nodes.filter(n => n.pass === pass).map(n => n.node), [1,2,3,4]);
for (const n of nodes) {
  assert.deepEqual(n.dev_mm, n.spot_base_mm.map((v, i) => v - n.ref_spot_base_mm[i]));
  assert.equal(n.dev_norm_mm, Math.hypot(...n.dev_mm));
  const settled = a.messages.find(m => m.type === "joint_state" && m.pass === n.pass && m.node === n.node && m.settled);
  assert.equal(n.t - settled.t, 400);
  const ray = laserRay(ARM_PARAMS, settled.q);
  assert.deepEqual(n.spot_base_mm, ray.origin.map((v, i) => (v + ray.direction[i] * 0.25) * 1000));
}
assert.equal(a.messages.filter(m => m.type === "correction").length, 8);
for (const correction of a.messages.filter(m => m.type === "correction" && m.pass < 8)) {
  correction.items.forEach((item, index) => {
    const before = a.messages.find(m => m.type === "joint_state" && m.pass === correction.pass && m.node === index+1 && m.settled);
    const after = a.messages.find(m => m.type === "joint_state" && m.pass === correction.pass+1 && m.node === index+1 && m.settled);
    assert.ok(Math.abs(item.delta - (after.q[0]-before.q[0])*180/Math.PI) < 1e-10);
  });
}
assert.equal(a.messages.filter(m => m.type === "event").length, 8);
assert.equal(a.summary.corrections, 8); assert.equal(a.summary.belowThreshold, true);
assert.notDeepEqual(passes.map(p => p.mean_mm), c.messages.filter(m => m.type === "pass_result").map(p => p.mean_mm));
console.log(JSON.stringify({ means: passes.map(p => p.mean_mm), improved: a.summary.improvedPct }));
''')
    means = out['means']
    assert len(means) == 8
    assert all(b <= a + 0.3 for a, b in zip(means, means[1:]))
    assert means[-1] < 5 and out['improved'] > 60
    assert means == pytest.approx([17.99074257, 11.14755068, 6.88562841, 4.32208129,
                                 2.67983170, 2.43549510, 2.48996305, 2.50609138])


def test_mock_without_laser_produces_invalid_nodes_and_no_success_statistics():
    out = node(RUN_PASSES + '''
const runResult = await run(1, false), {messages, summary, commands} = runResult;
const nodes = messages.filter(m => m.type === "node_result");
assert.equal(nodes.length, 4);
assert.ok(nodes.every(n => !n.valid && n.invalid_reason === "spot_not_found" && n.spot_base_mm === null && n.dev_norm_mm === null));
for (const n of nodes) {
  const settled = messages.find(m => m.type === "joint_state" && m.pass === n.pass && m.node === n.node && m.settled);
  assert.equal(n.t - settled.t, CONFIG.nodeTimeoutMs);
}
assert.equal(summary.lastMeanMm, null); assert.equal(summary.belowThreshold, false);
assert.ok(!commands.some(c => c.cmd.startsWith("laser_")));
assert.equal(messages.find(m => m.type === "correction").applied, false);
console.log(JSON.stringify(nodes.length));
''')
    assert out == 4


def test_guard_auto_renew_matching_result_and_duplicate_node():
    assert node(GUARD_FIXTURE + '''
joint(); joint(); assert.deepEqual(guard.state(), {want:true, auto:true, manual:false, activeNode:{pass:1,node:1}});
clock.advance(1000); result(2, 1); result(1, 2); result(); joint(); clock.advance(5000);
assert.deepEqual(commands(), ["laser_on", "laser_renew", "laser_off"]);
assert.ok(mock.commands().slice(0, 2).every(c => c.ttl_ms === 3000));
assert.equal(clock.size(), 0);
console.log(JSON.stringify(guard.state().want));
''') is False


def test_guard_timeout_closes_and_never_reopens_same_node():
    assert node(GUARD_FIXTURE + '''
joint(); clock.advance(2000); joint(); clock.advance(5000);
assert.equal(commands()[0], "laser_on"); assert.equal(commands().at(-1), "laser_off");
assert.ok(commands().slice(1, -1).every(cmd => cmd === "laser_renew"));
assert.equal(commands().filter(cmd => cmd === "laser_off").length, 1);
assert.equal(clock.size(), 0); console.log(JSON.stringify(guard.state().want));
''') is False


@pytest.mark.parametrize('mode', ['estop', 'fault'])
def test_guard_stops_on_unsafe_mode(mode):
    out = node(GUARD_FIXTURE + f'''
joint(); joint({json.dumps(mode)}); joint({json.dumps(mode)});
assert.equal(guard.manual(true), false); clock.advance(4000);
console.log(JSON.stringify(commands()));
''')
    assert out == ['laser_on', 'laser_off']


def test_guard_disconnect_closes_once_even_when_send_fails():
    assert node(GUARD_FIXTURE + '''
joint(); guard.onMessage({type:"link",online:false}); clock.advance(4000);
assert.equal(guard.manual(true), false);
assert.deepEqual(commands(), ["laser_on", "laser_off"]);
for (const rejected of [false, true]) {
  const offline = createLaserGuard({ send: (...args) => {
    mock.send(...args);
    if (rejected) return Promise.reject(Error("offline"));
    throw Error("offline");
  }, now:clock.now, setTimer:clock.setTimer, clearTimer:clock.clearTimer });
  offline.onMessage({type:"link",online:false});
}
await Promise.resolve(); console.log(JSON.stringify(commands().slice(-2)));
''') == ['laser_off', 'laser_off']


@pytest.mark.parametrize('reason', ['pagehide', 'hidden', 'route', 'estop_click'])
def test_guard_shutdown_sends_off_and_suspends_automatic_reopening(reason):
    out = node(GUARD_FIXTURE + f'''
joint(); guard.shutdown({json.dumps(reason)}); joint("practice", 1, 2);
clock.advance(5000); console.log(JSON.stringify(commands()));
''')
    assert out == ['laser_on', 'laser_off']


def test_guard_shutdown_off_fallback_debounces_only_within_200ms():
    out = node(GUARD_FIXTURE + '''
guard.shutdown("hidden"); clock.advance(100); guard.shutdown("pagehide");
clock.advance(199); guard.shutdown("route"); clock.advance(200); guard.shutdown("route");
console.log(JSON.stringify(commands()));
''')
    assert out == ['laser_off', 'laser_off']


def test_guard_manual_restrictions_renew_and_handover_to_practice():
    out = node(GUARD_FIXTURE + '''
assert.equal(guard.manual(true), true); assert.equal(guard.manual(true), true);
joint("demo", null, null, false); assert.equal(guard.state().manual, true);
clock.advance(1000); assert.equal(guard.state().manual, true);
joint("practice", 1, null, false); assert.equal(guard.manual(true), false); assert.equal(guard.manual(false), false);
joint(); result(); joint("idle", null, null, false);
assert.equal(guard.manual(true), true); assert.equal(guard.manual(false), true);
clock.advance(5000); console.log(JSON.stringify(commands()));
''')
    assert out == ['laser_on', 'laser_renew', 'laser_off', 'laser_on', 'laser_off', 'laser_on', 'laser_off']


def test_mock_ttl_expiry_renewal_estop_and_reset():
    assert node(IMPORTS + '''
const messages = [], mock = createMockHost({now: () => 1700000000000, setTimer: () => 0, clearTimer: () => {}});
mock.subscribe(m => messages.push(m)); mock.start();
await mock.send("laser_on", {ttl_ms:3000}); mock.advance(1000);
assert.equal(messages.filter(m => m.type === "laser_state").at(-1).remaining_ms, 2000);
await mock.send("laser_renew", {ttl_ms:3000}); mock.advance(2999);
assert.equal(messages.filter(m => m.type === "laser_state").at(-1).on, true);
mock.advance(1);
assert.ok(messages.some(m => m.type === "laser_state" && !m.on && m.reason === "ttl_expired" && m.remaining_ms === 0));
assert.equal((await mock.send("laser_renew", {ttl_ms:1000})).ok, false);
await mock.send("demo_start"); mock.advance(900); await mock.send("laser_on"); await mock.send("estop");
const stopped = messages.filter(m => m.type === "joint_state").at(-1).q;
for (const cmd of ["demo_start","demo_stop","practice_start","practice_stop","laser_on","laser_renew","laser_off","mark_node","estop"])
  assert.equal((await mock.send(cmd)).code, "estop");
mock.advance(5000);
assert.deepEqual(messages.filter(m => m.type === "joint_state").at(-1).q, stopped);
assert.equal(messages.filter(m => m.type === "laser_state").at(-1).reason, "estop");
await mock.send("reset_estop"); assert.equal(messages.filter(m => m.type === "joint_state").at(-1).mode, "idle");
assert.equal((await mock.send("laser_on", {ttl_ms:-1})).ok, false);
mock.stop(); console.log(JSON.stringify(true));
''') is True


def test_mock_advance_is_chunk_independent_and_timer_lifecycle_is_idempotent():
    assert node(CLOCK + IMPORTS + '''
async function demo(chunks) {
  const clock = fakeClock(), messages = [], host = createMockHost({now:clock.now, setTimer:clock.setTimer, clearTimer:clock.clearTimer, rateHz:17});
  host.subscribe(m => messages.push(m)); host.start(); host.start(); assert.equal(clock.size(),1);
  await host.send("demo_start"); for (const ms of chunks) host.advance(ms);
  host.stop(); host.stop(); assert.equal(clock.size(),0);
  return messages;
}
assert.deepEqual(await demo([6000]), await demo(Array(60).fill(100)));
const clock = fakeClock(), messages = [], host = createMockHost({now:clock.now, setTimer:clock.setTimer, clearTimer:clock.clearTimer});
host.subscribe(m => messages.push(m)); host.start(); clock.advance(1000); host.stop();
assert.equal(messages.filter(m => m.type === "joint_state").length,21);
assert.equal(messages.filter(m => m.type === "heartbeat").length,2);
console.log(JSON.stringify(true));
''') is True


HOST_FIXTURE = CLOCK + '''
import { createHostSource, commandUrl } from "./datasource/host-source.js";
import { trainerSourceFromParams, sourceFromParams } from "./datasource/index.js";
const clock = fakeClock(), sockets = [], requests = [];
globalThis.setTimeout = clock.setTimeout; globalThis.clearTimeout = clock.clearTimer;
Date.now = clock.now;
class FakeSocket {
  constructor(url) { this.url = url; sockets.push(this); }
  close() { this.closed = true; this.onclose?.(); }
  open() { this.onopen?.(); }
  push(data) { this.onmessage?.({data}); }
}
const fakeFetch = async (url, options) => { requests.push({url, ...options}); return {json:async () => ({v:1,ok:true,code:"ok",msg:"",seq:JSON.parse(options.body).seq})}; };
'''


def test_host_url_post_envelope_and_network_failure_are_fake_only():
    assert node(HOST_FIXTURE + '''
assert.equal(commandUrl("ws://10.0.0.5:9000/ws"), "http://10.0.0.5:9000/api/v1/command");
assert.equal(commandUrl("wss://example.invalid:9443/ws?x=1#z"), "https://example.invalid:9443/api/v1/command");
const host = createHostSource({url:"ws://example.invalid/ws",WebSocketImpl:FakeSocket,fetchImpl:fakeFetch});
assert.equal(sockets.length,0);
assert.deepEqual(await host.send("demo_start",{v:9,seq:-1,cmd:"ignored",t:-1}), {v:1,ok:true,code:"ok",msg:"",seq:1});
await host.send("demo_stop");
assert.equal(requests[0].method,"POST"); assert.equal(requests[0].headers["Content-Type"],"application/json");
assert.deepEqual(JSON.parse(requests[0].body), {v:1,seq:1,cmd:"demo_start",t:clock.now()});
assert.equal(JSON.parse(requests[1].body).seq,2);
const failed = createHostSource({url:"ws://example.invalid/ws",WebSocketImpl:FakeSocket,fetchImpl:async () => {throw Error("offline");}});
assert.deepEqual(await failed.send("demo_start"), {ok:false,code:"network",msg:"offline"});
console.log(JSON.stringify(true));
''') is True


def test_host_raw_messages_offline_timeout_retry_and_stop_cleanup():
    assert node(HOST_FIXTURE + '''
const host = createHostSource({url:"ws://example.invalid/ws",WebSocketImpl:FakeSocket,fetchImpl:fakeFetch}), seen = [];
const unsubscribe = host.subscribe(m => seen.push(m)); host.start(); host.start(); assert.equal(sockets.length,1);
sockets[0].open(); assert.equal(seen.at(-1).online,true);
const frame = {v:1,type:"joint_state",seq:1,t:clock.now(),q:[0,0,0,0,0,0]};
sockets[0].push(JSON.stringify(frame)); assert.deepEqual(seen.at(-1),frame);
const oldMessage = sockets[0].onmessage;
for (const data of ["null", "[]", "1", "bad json", '{"v":2}', null]) sockets[0].push(data);
assert.equal(seen.filter(m => m.v).length,1);
clock.advance(2999); assert.notEqual(seen.at(-1).online,false);
clock.advance(1); assert.deepEqual(seen.at(-1), {type:"link",online:false,reason:"timeout"});
assert.equal(sockets[0].closed,true);
const afterTimeout = seen.length;
sockets[0].push({v:1,type:"heartbeat",seq:2,t:clock.now()});
assert.equal(seen.length,afterTimeout);
sockets[0].close(); assert.equal(seen.at(-1).online,false);
clock.advance(999); assert.equal(sockets.length,1); clock.advance(1); assert.equal(sockets.length,2);
const count = seen.length; oldMessage({data:JSON.stringify(frame)}); assert.equal(seen.length,count);
sockets[1].open(); assert.equal(seen.at(-1).online,true); unsubscribe(); host.stop(); clock.advance(10000);
assert.equal(sockets.length,2); assert.equal(clock.size(),0); assert.equal(sockets[1].closed,true);
console.log(JSON.stringify(true));
''') is True


def test_host_selection_rejects_invalid_backend_never_falls_back_and_keeps_legacy():
    assert node(HOST_FIXTURE + '''
globalThis.WebSocket = FakeSocket; globalThis.fetch = fakeFetch;
const host = trainerSourceFromParams(new URLSearchParams({backend:"wss://example.invalid:9001/ws"})), seen=[];
assert.equal(host.kind,"host"); assert.equal(sockets.length,0);
host.subscribe(m => seen.push(m)); host.start(); sockets[0].onerror(); clock.advance(1000);
assert.equal(sockets.length,2); assert.ok(seen.every(m => m.type === "link")); assert.equal(host.kind,"host"); host.stop();
globalThis.WebSocket = class { constructor() { throw Error("constructor failed"); } };
const rejected = trainerSourceFromParams(new URLSearchParams({backend:"ws://example.invalid/ws"}));
rejected.start(); clock.advance(3000); rejected.stop(); assert.equal(clock.size(),0);
for (const backend of ["", "http://example.invalid", "example.invalid", "ws://", "file:///tmp/test"])
  assert.throws(() => trainerSourceFromParams(new URLSearchParams({backend})));
assert.equal(trainerSourceFromParams(new URLSearchParams()).kind,"mock");
globalThis.document = new EventTarget();
assert.equal(sourceFromParams(new URLSearchParams()).kind,"panel");
assert.equal(sourceFromParams(new URLSearchParams({twin:"sim"})).kind,"sim");
assert.equal(sourceFromParams(new URLSearchParams({twin:"device",device:"ws://example.invalid/ws"})).kind,"device");
console.log(JSON.stringify(true));
''') is True


def test_host_silent_connection_reports_timeout_then_close_even_already_offline():
    assert node(HOST_FIXTURE + '''
const host = createHostSource({url:"ws://example.invalid/ws",WebSocketImpl:FakeSocket,fetchImpl:fakeFetch}), seen=[];
host.subscribe(m => seen.push(m)); host.start(); clock.advance(3000);
assert.deepEqual(seen.at(-1), {type:"link",online:false,reason:"timeout"});
assert.equal(sockets[0].closed,true);
sockets[0].close(); assert.deepEqual(seen.at(-1), {type:"link",online:false,reason:"timeout"});
host.stop(); clock.advance(4000); assert.equal(sockets.length,1); assert.equal(clock.size(),0);
console.log(JSON.stringify(true));
''') is True


def test_store_immutable_out_of_order_duplicates_stale_mode_and_bounded_events():
    assert node(IMPORTS + '''
function freeze(value) { if (value && typeof value === "object") { Object.freeze(value); Object.values(value).forEach(freeze); } return value; }
let state = freeze(initialState());
const apply = message => { const before = JSON.stringify(state); const next = reduce(state, freeze(message)); assert.equal(JSON.stringify(state), before); assert.notEqual(next,state); state = freeze(next); };
apply({type:"link",online:true}); apply({v:1,type:"joint_state",seq:10,t:100,mode:"practice",pass:2,node:3});
apply({v:1,type:"joint_state",seq:1,t:1,mode:"idle",pass:1,node:1});
apply({v:1,type:"node_result",seq:20,t:200,pass:2,node:3,valid:true,dev_norm_mm:4});
apply({v:1,type:"node_result",seq:20,t:200,pass:2,node:3,valid:true,dev_norm_mm:4});
apply({v:1,type:"node_result",seq:2,t:2,pass:1,node:1,valid:true,dev_norm_mm:18});
apply({v:1,type:"node_result",seq:3,t:3,pass:2,node:3,valid:false});
apply({v:1,type:"pass_result",seq:30,t:300,pass:2,mean_mm:4,max_mm:4,valid_nodes:1,total_nodes:1});
apply({v:1,type:"pass_result",seq:4,t:4,pass:1,mean_mm:18,max_mm:18,valid_nodes:1,total_nodes:1});
apply({v:1,type:"correction",seq:31,t:301,pass:2,applied:true});
apply({v:1,type:"correction",seq:31,t:301,pass:2,applied:true});
assert.deepEqual(state.passes.map(p => p.pass),[1,2]); assert.equal(Object.keys(state.passes[1].nodes).length,1);
assert.equal(state.passes[1].nodes[3].valid,true); assert.deepEqual(state.currentNode,{pass:2,node:3});
const metrics = summarize(state,CONFIG);
assert.equal(metrics.corrections,1); assert.equal(metrics.lastMeanMm,4); assert.equal(metrics.firstMeanMm,18); assert.ok(metrics.improvedPct > 60);
assert.equal(metrics.belowThreshold,true); assert.equal(summarize(state,{thresholdMm:3}).belowThreshold,false);
apply({type:"link",online:false}); assert.equal(state.mode,"practice"); assert.equal(state.stale,true);
apply({type:"link",online:true}); assert.equal(state.stale,false);
for (let seq=100;seq<205;seq++) apply({v:1,type:"event",seq,t:seq,name:"test"});
assert.equal(state.events.length,100); assert.equal(state.events[0].seq,105);
apply({v:1,type:"event",seq:204,t:204,name:"test"}); assert.equal(state.events.length,100);
console.log(JSON.stringify(true));
''') is True


def test_metrics_empty_zero_baseline_and_laser_mismatch_use_message_time():
    assert node(IMPORTS + '''
let state = initialState(); assert.ok(Object.values(summarize(state,CONFIG)).every(value => value === null));
for (const m of [{type:"panel_laser",want:true,t:1000}, {type:"laser_state",on:false,t:1500}]) state=reduce(state,m,1500);
assert.equal(summarize(state).laserMismatch,false);
state=reduce(state,{type:"heartbeat",t:2000}); assert.equal(summarize(state).laserMismatch,false);
state=reduce(state,{type:"heartbeat",t:2001}); assert.equal(summarize(state).laserMismatch,false);
state=reduce(state,{type:"laser_state",on:false,t:2001},2001); assert.equal(summarize(state).laserMismatch,true);
state=reduce(state,{type:"laser_state",on:true,t:2002},2002); assert.equal(summarize(state).laserMismatch,false);
state=reduce(state,{type:"panel_laser",want:false,t:2003}); assert.equal(summarize(state).laserMismatch,false);
state=reduce(state,{type:"laser_state",on:true,t:3004},3004); assert.equal(summarize(state).laserMismatch,true);
state=reduce(state,{type:"pass_result",pass:1,mean_mm:0,max_mm:0,valid_nodes:4,total_nodes:4,t:4000});
assert.equal(summarize(state).improvedPct,null); assert.equal(summarize(state).lastMeanMm,0);
state=reduce(initialState(),{type:"pass_result",pass:1,mean_mm:null,max_mm:null,valid_nodes:0,total_nodes:4,t:4000});
state=reduce(state,{type:"pass_result",pass:2,mean_mm:4,max_mm:4,valid_nodes:4,total_nodes:4,t:5000});
assert.equal(summarize(state).firstMeanMm,null); assert.equal(summarize(state).improvedPct,null);
console.log(JSON.stringify(true));
''') is True


def test_logic_has_no_dom_and_frontend_has_no_literal_host_address():
    # 纯逻辑文件逐个列出：trainer.js 和 views/ 负责页面接线，本来就要碰 DOM，不在此列。
    logic = ['config.js', 'store.js', 'metrics.js', 'laser-guard.js']
    paths = [MODULES / 'trainer' / name for name in logic] + [MODULES / 'datasource' / name for name in ['host-source.js', 'mock-host.js']]
    assert all(path.exists() for path in paths)
    for path in paths:
        text = path.read_text()
        assert not any(word in text for word in ['document.', 'querySelector', 'getElementById']), path
    # 仅检查字面量；注释里的示例不参与。保留字符串中的 //，避免错误删掉待检查的地址。
    tokens = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`|//[^\n]*|/\*[\s\S]*?\*/')
    for path in list(MODULES.parent.rglob('*.js')) + list(MODULES.parent.rglob('*.html')):
        for match in tokens.finditer(path.read_text()):
            token = match.group()
            if token.startswith(('//', '/*')):
                continue
            assert not re.search(r'wss?://[0-9A-Za-z]', token), path


def test_mock_pinhole_projection_center_offset_small_deviation_and_degree_text():
    node(RUN_PASSES + '''
import {endPoses} from './arm/fk.js';
const runData=await run(8), messages=runData.messages;
const camera=messages.find(m=>m.type==='hello').camera;
assert.equal(camera.width,640);assert.equal(camera.height,480);
const demo=messages.find(m=>m.type==='demo_trajectory');
const fy=480/(2*Math.tan(58*Math.PI/360)), fx=640/(2*Math.tan(87*Math.PI/360));
for(const n of demo.nodes){
 assert.ok(Math.abs(n.ref_spot_px[0]-320)<1e-9);
 assert.ok(Math.abs(n.ref_spot_px[1]-(240+fy*20/250))<1e-9);
}
for(const result of messages.filter(m=>m.type==='node_result')){
 const n=demo.nodes.find(n=>n.id===result.node), m=endPoses(ARM_PARAMS,n.q).camera;
 const relative=result.spot_base_mm.map((v,i)=>v/1000-m[4*i+3]);
 const local=[0,1,2].map(j=>relative.reduce((sum,v,i)=>sum+v*m[4*i+j],0));
 const expected=[320-fx*local[1]/local[0],240-fy*local[2]/local[0]];
 assert.ok(expected.every((v,i)=>Math.abs(v-result.spot_px[i])<1e-9));
 assert.ok(Math.hypot(...result.spot_px.map((v,i)=>v-n.ref_spot_px[i]))<40);
}
for(const correction of messages.filter(m=>m.type==='correction')){
 assert.ok(correction.llm_text.includes('°'));assert.ok(!correction.llm_text.includes('deg'));
 assert.ok(!correction.llm_text.includes('-'));assert.ok(!correction.llm_text.includes('−0.00'));
 assert.ok(correction.items.every(item=>item.unit==='deg'));
}
// 同一个 hello.camera 分辨率同时用于两类光点的投影，缺失时回退 640×480。
const host=createMockHost({now:()=>0,setTimer:()=>0,clearTimer:()=>{},camera:{width:1280,height:960}}), doubled=[];
host.subscribe(m=>doubled.push(m));host.start();await host.send('demo_start');host.advance(6000);await host.send('demo_stop');
const d=doubled.find(m=>m.type==='demo_trajectory');
for(let i=0;i<d.nodes.length;i++)assert.ok(d.nodes[i].ref_spot_px.every((v,j)=>Math.abs(v-demo.nodes[i].ref_spot_px[j]*2)<1e-9));
host.stop();console.log('{}');
''')


@pytest.mark.parametrize('offset', [-86400000, 86400000])
def test_laser_mismatch_uses_injected_local_receipt_not_host_clock(offset):
    assert node(IMPORTS + '''
Date.now=()=>{throw Error('pure functions must not read the clock');};
let state=reduce(initialState(),{type:'panel_laser',want:true,t:10000,seq:1});
const report=Object.freeze({type:'laser_state',on:false,t:OFFSET+10000,seq:1,received_at:999999999});
state=reduce(state,report,10500);
assert.equal(state.laser.received_at,10500);assert.equal(report.received_at,999999999);
assert.equal(summarize(state).laserMismatch,false);
state=reduce(state,{...report,seq:2,t:OFFSET+10001},11000);
assert.equal(summarize(state).laserMismatch,false);
state=reduce(state,{...report,seq:3,t:OFFSET+10002},11001);
assert.equal(summarize(state).laserMismatch,true);
// 旧回报不覆盖已归并结果，也不把晚到时刻伪装成新的状态回报。
const latest=state.laser;
state=reduce(state,report,20000);assert.equal(state.laser,latest);
state=reduce(state,{...report,seq:4,t:OFFSET+10003,on:true},11002);
assert.equal(summarize(state).laserMismatch,false);
state=reduce(state,{type:'panel_laser',want:false,t:12000,seq:2});
assert.equal(summarize(state).laserMismatch,false);
state=reduce(state,{type:'heartbeat',t:9e15},15000);
assert.equal(summarize(state).laserMismatch,false);
state=reduce(state,{...report,seq:5,t:OFFSET+10004,on:true},13001);
assert.equal(summarize(state).laserMismatch,true);
const missing=reduce(initialState(),report);
assert.equal(missing.laser.received_at,null);assert.equal(summarize(missing).laserMismatch,null);
console.log('true');
'''.replace('OFFSET', str(offset))) is True


@pytest.mark.parametrize('ttl,wait,renew', [(900, 650, 300), (6000, 2200, 1000)])
def test_guard_hello_controls_ttl_renewal_and_node_deadline(ttl, wait, renew):
    assert node(GUARD_FIXTURE + '''
guard.onMessage({type:'hello',laser_ttl_ms:TTL,node_timeout_ms:WAIT});
joint();assert.equal(mock.commands().at(-1).ttl_ms,TTL);
clock.advance(RENEW-1);assert.deepEqual(commands(),['laser_on']);
clock.advance(1);assert.equal(mock.commands().at(-1).cmd,'laser_renew');
assert.equal(mock.commands().at(-1).ttl_ms,TTL);
clock.advance(WAIT-RENEW-1);assert.equal(guard.state().want,true);
clock.advance(1);assert.equal(guard.state().want,false);assert.equal(commands().at(-1),'laser_off');
assert.equal(clock.size(),0);joint();assert.equal(guard.state().want,false);
console.log('true');
'''.replace('TTL', str(ttl)).replace('WAIT', str(wait)).replace('RENEW', str(renew))) is True


@pytest.mark.parametrize('value', ['undefined', 'null', '0', '-1', 'NaN', 'Infinity', '"900"', 'true'])
def test_guard_invalid_hello_timings_restore_defaults_independently(value):
    assert node(GUARD_FIXTURE + '''
// 先收到有效配置，再收到缺失或非法字段，也应恢复默认值。
guard.onMessage({type:'hello',laser_ttl_ms:900,node_timeout_ms:500});
guard.onMessage({type:'hello',laser_ttl_ms:VALUE,node_timeout_ms:VALUE});
joint();assert.equal(mock.commands().at(-1).ttl_ms,3000);
clock.advance(999);assert.deepEqual(commands(),['laser_on']);
clock.advance(1);assert.equal(mock.commands().at(-1).cmd,'laser_renew');
clock.advance(999);assert.equal(guard.state().want,true);
clock.advance(1);assert.equal(guard.state().want,false);
guard.onMessage({type:'hello',laser_ttl_ms:900,node_timeout_ms:VALUE});
joint('practice',1,2);clock.advance(300);assert.equal(mock.commands().at(-1).ttl_ms,900);
clock.advance(1699);assert.equal(guard.state().want,true);clock.advance(1);assert.equal(guard.state().want,false);
guard.onMessage({type:'hello',laser_ttl_ms:VALUE,node_timeout_ms:500});
joint('practice',1,3);assert.equal(mock.commands().at(-1).ttl_ms,3000);
clock.advance(500);assert.equal(guard.state().want,false);assert.equal(clock.size(),0);
console.log('true');
'''.replace('VALUE', value)) is True


def test_guard_updated_hello_reschedules_active_timers_without_resetting_node_start():
    assert node(GUARD_FIXTURE + '''
joint();clock.advance(200);
guard.onMessage({type:'hello',laser_ttl_ms:600,node_timeout_ms:500});
clock.advance(199);assert.deepEqual(commands(),['laser_on']);clock.advance(1);
assert.equal(mock.commands().at(-1).cmd,'laser_renew');assert.equal(mock.commands().at(-1).ttl_ms,600);
clock.advance(99);assert.equal(guard.state().want,true);clock.advance(1);
assert.equal(guard.state().want,false);assert.equal(clock.size(),0);
joint('practice',1,2);clock.advance(100);
guard.onMessage({type:'hello',laser_ttl_ms:900,node_timeout_ms:50});
assert.equal(guard.state().want,false);assert.equal(clock.size(),0);
// 极短的合法等待时间若在设置计时器时已耗尽，不能先关再误开。
let reads=0;const sent=[];
const short=createLaserGuard({send:cmd=>sent.push(cmd),now:()=>reads++ ? 1 : 0,
 setTimer:clock.setTimer,clearTimer:clock.clearTimer});
short.onMessage({type:'hello',laser_ttl_ms:1,node_timeout_ms:0.5});
short.onMessage({type:'link',online:true});
short.onMessage({type:'joint_state',mode:'practice',pass:1,node:1,settled:true});
assert.deepEqual(sent,['laser_off']);assert.equal(clock.size(),0);
console.log('true');
''') is True


def test_host_silence_watchdog_refresh_retry_interval_and_stop_during_retry():
    assert node(HOST_FIXTURE + '''
const host=createHostSource({url:'ws://example.invalid/ws',WebSocketImpl:FakeSocket,fetchImpl:fakeFetch,offlineAfterMs:80,retryMs:25});
const seen=[];host.subscribe(m=>seen.push(m));host.start();sockets[0].open();
clock.advance(79);sockets[0].push('invalid json');clock.advance(79);
assert.notEqual(sockets[0].closed,true);assert.equal(seen.at(-1).online,true);
const staleOpen=sockets[0].onopen,staleClose=sockets[0].onclose,staleError=sockets[0].onerror;
clock.advance(1);assert.equal(sockets[0].closed,true);
assert.deepEqual(seen.at(-1),{type:'link',online:false,reason:'timeout'});
const count=seen.length;staleOpen();staleClose();staleError();assert.equal(seen.length,count);
clock.advance(24);assert.equal(sockets.length,1);clock.advance(1);assert.equal(sockets.length,2);
sockets[1].open();assert.deepEqual(seen.at(-1),{type:'link',online:true,reason:'connected'});
clock.advance(80);assert.equal(sockets[1].closed,true);host.stop();clock.advance(1000);
assert.equal(sockets.length,2);assert.equal(clock.size(),0);
// 握手一直未完成也不能卡住，stop 后取消看门狗与重连。
host.start();clock.advance(80);assert.equal(sockets[2].closed,true);
clock.advance(25);assert.equal(sockets.length,4);host.stop();assert.equal(clock.size(),0);
console.log('true');
''') is True


@pytest.mark.parametrize('result,expected', [
    ({'mean_mm': 2, 'max_mm': 6.9, 'valid_nodes': 4, 'total_nodes': 4}, False),
    ({'mean_mm': 2, 'max_mm': 5, 'valid_nodes': 4, 'total_nodes': 4}, True),
    ({'mean_mm': 2, 'max_mm': 4, 'valid_nodes': 3, 'total_nodes': 4}, False),
    ({'mean_mm': None, 'max_mm': None, 'valid_nodes': 0, 'total_nodes': 4}, False),
    ({'mean_mm': 0, 'max_mm': 0, 'valid_nodes': 0, 'total_nodes': 0}, False),
    ({'mean_mm': 2, 'max_mm': 4, 'valid_nodes': 4, 'total_nodes': 4, 'below_threshold': False}, False),
    ({'mean_mm': 2, 'max_mm': 6.9, 'valid_nodes': 3, 'total_nodes': 4, 'below_threshold': True}, True),
])
def test_pass_threshold_uses_host_boolean_or_inclusive_max_and_all_valid(result, expected):
    assert node(IMPORTS + f'''
const state=reduce(initialState(),{{type:'pass_result',pass:1,...{json.dumps(result)}}});
assert.equal(summarize(state).belowThreshold,{json.dumps(expected)});
console.log('true');
''') is True
