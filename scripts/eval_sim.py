"""Run the unrelaxed §7 criteria. Exit nonzero if any criterion fails.

The evaluator may inspect simulator truth ONLY as an independent audit oracle;
diagnosis and calibration receive Shot observations, never injected damage labels.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
import numpy as np
from rearm.app import build_app
from rearm.config import load_config
from rearm.types import jsonable


def evaluate(output: Path, trials: int | None = None, run_pytest=True):
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config")
    options = config.thresholds["eval"]
    trials = options["trials"] if trials is None else trials
    if trials < 1:
        raise ValueError("trials must be positive")
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime = root / "runtime"
    runtime.mkdir(exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="eval-", dir=runtime))
    raw_path = output.with_suffix(".jsonl")
    records = []
    started = time.perf_counter()
    def record(value):
        records.append(jsonable(value))
        with raw_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(jsonable(value), ensure_ascii=False, allow_nan=False)+"\n")
    raw_path.write_text("")
    rng = np.random.default_rng(options["seed"])
    params = config.nominal.updated({k:getattr(config.nominal,k)+v for k,v in options["baseline_offsets"].items()})
    baseline = build_app(config, run_root/"baseline", seed=options["seed"], true_params=params)
    baseline_report = baseline.baseline()
    targets = rng.uniform(-config.board_mm/2+options["target_margin_mm"], config.board_mm/2-options["target_margin_mm"], (options["baseline_targets"],2))
    hits, target_errors = 0, []
    for target in targets:
        try:
            shot=baseline.target(target)
            error=float(np.linalg.norm(np.asarray(shot.observed)-target)) if shot.observed is not None else np.inf
        except ValueError:
            error=np.inf
        target_errors.append(error)
        hits += error <= options["hit_radius_mm"]
    record({"category":"baseline","hits":int(hits),"count":len(targets),"targets":targets,
            "errors_mm":target_errors,"guard":baseline_report,"fitted_params":baseline.store.head().params})
    healthy=build_app(config,run_root/"healthy",seed=options["seed"]+1)
    for _ in range(options["no_damage_shots"]): healthy.step()
    record({"category":"false_alarm","shots":options["no_damage_shots"],"alarms":healthy.alarms})

    cases=[]
    worse_count=0
    if baseline_report.accepted:
        q=baseline.pool[config.thresholds["fit"]["baseline_shots"]+config.thresholds["guard"]["poses"]:]
        q=q[baseline.geometry.valid(params,q)][:options["audit_poses"]]
        truth=baseline.geometry.predict(params,q)
        before=np.median(np.linalg.norm(baseline.geometry.predict(config.nominal,q)-truth,axis=1))
        after=np.median(np.linalg.norm(baseline.geometry.predict(baseline.store.head().params,q)-truth,axis=1))
        worse_count+=int(after>before)
        record({"category":"baseline_independent_audit","old_mm":before,"new_mm":after,"poses":len(q)})
    for case_index, case in enumerate(options["injury_cases"]):
        label=case["kind"]+("_"+str(case["amounts"][0]) if len(case["amounts"])==1 else "")
        summary={"label":label,"kind":case["kind"],"trials":trials,"alarms_in_3":0,"diagnosed_correct":0,
                 "recovered":0,"repeat_in_3":0,"restored":0,"accepted_worse":0,"max_recovery_shots":0,"holdout_medians":[]}
        for trial in range(trials):
            seed=options["seed"]+(case_index+1)*options["trials"]+trial
            app=build_app(config,run_root/label/f"{trial:03d}",seed=seed)
            initial=app.store.head()
            amount=case["amounts"][trial % len(case["amounts"]) ]
            payload={"kind":case["kind"],"amount":amount}
            if case["kind"]=="combination":
                payload["components"]=[{"kind":"j1","amount":1},{"kind":"j2","amount":-1}]
            app.command("inject",payload)
            # Monitor exactly three shots; recovery is counted separately from the alarm shot.
            for _ in range(options["alarm_shots"]): app.step(recover=False)
            alarm=app.alarms>0
            summary["alarms_in_3"]+=int(alarm)
            diagnosed=False
            if alarm:
                app.recover()
                diagnosis=app.last_diagnosis
                diagnosed=diagnosis is not None and diagnosis.best.name==case["hypothesis"]
                if diagnosed and case["kind"] in ("j1","j2"):
                    name="delta1" if case["kind"]=="j1" else "delta2"
                    diagnosed=diagnosis.gear_steps.get(name)==amount
                if diagnosed and case["kind"]=="extension":
                    diagnosed=abs(diagnosis.deltas.get("e",np.inf)-amount)<options["parameter_tolerance"]
            summary["diagnosed_correct"]+=int(diagnosed)
            healed=app.store.head()
            report=app.last_guard
            recovery_shots=app.last_recovery_shots
            accepted=healed.id!=initial.id
            recovered=accepted and report is not None and report.candidate_median<=config.thresholds["guard"]["median_mm"] and recovery_shots<=options["recovery_shots"]
            summary["recovered"]+=int(recovered)
            if alarm: summary["max_recovery_shots"]=max(summary["max_recovery_shots"],recovery_shots)
            if report is not None: summary["holdout_medians"].append(report.candidate_median)
            audit=None
            if accepted:
                used=np.array(healed.meta["fit_q"]+healed.meta["holdout_q"])
                q=app.pool[~np.any(np.all(np.isclose(app.pool[:,None],used[None]),axis=-1),axis=1)]
                q=q[app.geometry.valid(app.arm.true_params,q)][:options["audit_poses"]]
                truth=app.geometry.predict(app.arm.true_params,q)
                before=float(np.median(np.linalg.norm(app.geometry.predict(initial.params,q)-truth,axis=1)))
                after=float(np.median(np.linalg.norm(app.geometry.predict(healed.params,q)-truth,axis=1)))
                worse=int(after>before)
                summary["accepted_worse"]+=worse; worse_count+=worse
                audit={"old_mm":before,"new_mm":after,"poses":len(q)}
                app.command("inject",{"kind":"restore"})
                app.command("selfcheck",{})
                summary["restored"]+=int(app.store.head().id==initial.id and app.last_recovery_shots==3)
                app.command("inject",payload)
                app.command("selfcheck",{})
                summary["repeat_in_3"]+=int(app.store.head().id==healed.id and app.last_recovery_shots==3)
            record({"category":"injury_trial","label":label,"trial":trial,"seed":seed,"damage":payload,
                    "alarm_in_3":alarm,"diagnosed_correct":diagnosed,"recovered":recovered,
                    "diagnosis":app.last_diagnosis,"guard":report,"recovery_shots":recovery_shots,
                    "accepted":accepted,"independent_audit":audit})
            if (trial+1)%max(1,trials//4)==0:
                print(f"{label}: {trial+1}/{trials}, alarm {summary['alarms_in_3']}, diagnosis {summary['diagnosed_correct']}, recovered {summary['recovered']}",flush=True)
        cases.append(summary)
    menu=build_app(config,run_root/"unmodeled",seed=options["seed"]+9999)
    initial=menu.store.head().id
    menu.command("inject",{"kind":"loose"})
    menu.command("selfcheck",{})
    rejected=any(not v.accepted for v in menu.store.list()) and menu.store.head().id==initial
    record({"category":"unmodeled","rejected":rejected,"guard":menu.last_guard,"head":menu.store.head().id})

    residual_config=replace(config,sim=config.sim | {"nongeometric":True})
    learner=build_app(residual_config,run_root/"residual",seed=options["seed"]+8888)
    for _ in range(options["residual_shots"]):
        learner.step(learner.probe_pool[int(rng.integers(len(learner.probe_pool)))])
    first_train=learner.retrain()
    first_gp_version=learner.store.head().id
    learner.command("inject",{"kind":"weight"})
    for _ in range(options["residual_shots"]):
        learner.step(learner.probe_pool[int(rng.integers(len(learner.probe_pool)))])
    second_train=learner.retrain()
    worse_count+=int(first_train.accepted and first_train.new_median>first_train.old_median)
    worse_count+=int(second_train.accepted and second_train.new_median>second_train.old_median)
    record({"category":"residual","initial":first_train,"after_weight":second_train,"first_gp_version":first_gp_version})
    # A fresh process-equivalent composition reloads artifacts from disk for every accepted version.
    prediction_errors=[]
    snapshots={}
    q=learner.probe_pool[:options["audit_poses"]]
    feats=np.column_stack([q,np.ones_like(q),np.full(len(q),learner.arm.load),np.full(len(q),learner.arm.read_state().temperature)])
    for v in learner.store.list():
        if v.accepted: snapshots[v.id]=learner.model(v).predict(v.params,q,feats)[0]
    reloaded=build_app(residual_config,run_root/"residual")
    for vid,pred in snapshots.items():
        reloaded.rollback(vid)
        v=reloaded.store.head()
        prediction_errors.append(float(np.max(np.abs(reloaded.model(v).predict(v.params,q,feats)[0]-pred))))
    record({"category":"rollback","versions":len(snapshots),"max_prediction_error_mm":max(prediction_errors)})

    pytest_info={"passed":False,"count":0,"failures":0,"skipped":0,"executed":False}
    if run_pytest:
        result=subprocess.run([str(root/".venv/bin/pytest"),"-q",f"--junitxml={output.parent/'pytest.xml'}"],cwd=root,capture_output=True,text=True)
        (output.parent/"pytest_output.txt").write_text(result.stdout+result.stderr)
        xml=ET.parse(output.parent/"pytest.xml")
        suites=list(xml.getroot().iter("testsuite"))
        pytest_info={"passed":result.returncode==0,"count":sum(int(s.attrib.get("tests",0)) for s in suites),
                     "failures":sum(int(s.attrib.get("failures",0))+int(s.attrib.get("errors",0)) for s in suites),
                     "skipped":sum(int(s.attrib.get("skipped",0)) for s in suites),"executed":True}
    measured={"baseline":{"hits":int(hits),"count":len(targets),"rate":hits/len(targets),"guard":jsonable(baseline_report)},
              "false_alarms":healthy.alarms,"cases":jsonable(cases),"accepted_worse":worse_count,
              "unmodeled_rejected":rejected,"gp_initial":jsonable(first_train),"gp_weight":jsonable(second_train),
              "rollback_max_mm":max(prediction_errors),"pytest":pytest_info}
    criteria={
        "基线":bool(baseline_report.accepted and hits/len(targets)>=options["baseline_rate"]),
        "误报":healthy.alarms==0,
        "发现":all(c["alarms_in_3"]==trials for c in cases),
        "诊断":all(c["diagnosed_correct"]/trials>=options["diagnosis_rate"] for c in cases if c["kind"]!="combination"),
        "新伤恢复":all(c["recovered"]==trials for c in cases),
        "旧伤恢复":all(c["repeat_in_3"]==trials for c in cases),
        "伤愈识别":all(c["restored"]==trials for c in cases),
        "护栏":worse_count==0,
        "菜单外的伤":rejected,
        "残差模型":first_train.accepted and first_train.new_median<first_train.geometry_median and second_train.accepted and second_train.new_median<second_train.old_median,
        "回退":max(prediction_errors)==0,
        "测试":pytest_info["passed"],
    }
    complete_sample=trials>=options["trials"]
    metadata={"timestamp":datetime.now(timezone.utc).isoformat(),"seed":options["seed"],"trials_per_class":trials,
              "complete_sample":complete_sample,"elapsed_seconds":time.perf_counter()-started,
              "python":platform.python_version(),"platform":platform.platform(),"runtime_evidence":str(run_root.relative_to(root)),
              "dependencies":{name:importlib.metadata.version(name) for name in ("numpy","scipy","scikit-learn","opencv-contrib-python","fastapi","pytest")},
              "config_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/"config").glob("*.yaml"))}}
    full={"metadata":metadata,"criteria":criteria,"measured":measured}
    output.with_suffix(".json").write_text(json.dumps(jsonable(full),ensure_ascii=False,indent=2,allow_nan=False))
    lines=["# ReArm 仿真实测验收", "", f"生成时间：{metadata['timestamp']}。固定种子：{options['seed']}。耗时：{metadata['elapsed_seconds']:.2f} 秒。", "",
           f"每类 {trials} 次；{'完整验收样本' if complete_sample else '调试运行，不满足每类 100 次要求'}。原第 7 节标准未修改。", "",
           "## 验收结果", "", "| 项 | 实测 | 结果 |", "|---|---|---|"]
    details={"基线":f"全参数校准；随机靶点 {hits}/{len(targets)} 命中（{hits/len(targets):.1%}），命中半径 10 mm",
             "误报":f"无伤 {options['no_damage_shots']} 发，报警 {healthy.alarms} 次",
             "发现":"见逐类表；所有试验均计入分母，未报警记失败",
             "诊断":"见逐类表；J1/J2 同时要求类型与格数正确",
             "新伤恢复":"见逐类表；成功要求报警后 ≤20 发且留出中位数 ≤3 mm",
             "旧伤恢复":"见逐类表；第二次相同伤严格只用 3 发探测",
             "伤愈识别":"见逐类表；必须切回该试验初始版本",
             "护栏":f"采纳更差版本 {worse_count} 次；用未拟合/未护栏的姿势独立审计",
             "菜单外的伤":f"随机松动：{'拒绝并保留原版本' if rejected else '未成功拒绝'}",
             "残差模型":f"几何 {first_train.geometry_median:.4f} → GP {first_train.new_median:.4f} mm；加配重后旧 GP {second_train.old_median:.4f} → 重训 {second_train.new_median:.4f} mm",
             "回退":f"重新加载 {len(snapshots)} 个已采纳版本，最大预测差 {max(prediction_errors):.12g} mm",
             "测试":f"pytest {pytest_info['count']} 项，失败 {pytest_info['failures']}，跳过 {pytest_info['skipped']}；实际执行 {pytest_info['executed']}"}
    lines += [f"| {name} | {details[name]} | {'通过' if ok else '未达标'} |" for name,ok in criteria.items()]
    lines += ["", "## 每类伤的完整计数", "", "| 类别 | ≤3 发报警 | 类型及格数正确 | 新伤恢复 | 旧伤 3 发 | 复原识别 | 最大恢复发数 | 护栏中位数最大值 mm |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for c in cases:
        maximum=max(c["holdout_medians"],default=float('nan'))
        lines.append(f"| {c['label']} | {c['alarms_in_3']}/{trials} | {c['diagnosed_correct']}/{trials} | {c['recovered']}/{trials} | {c['repeat_in_3']}/{trials} | {c['restored']}/{trials} | {c['max_recovery_shots'] if c['max_recovery_shots'] else '未触发'} | {maximum:.4f} |")
    lines += ["", "## 口径和无法满足项", "",
        "- J1/J2 的 100 次均匀覆盖 −2、−1、+1、+2 格；底座平移覆盖正负 20 mm，旋转覆盖正负 10°；组合伤为 J1 +1 格与 J2 −1 格。",
        "- 每次独立初始化版本库与随机种子；诊断不读取注入标签或真实参数。先观测 3 发，再识旧 3 发，未识别才诊断和护栏。",
        "- 延长杆两种幅度各测 100 次。默认 β=γ=0 时，末端延长完全沿光轴移动，射线与平面交点不变；因此发现、诊断、恢复和复原指标不能伪称通过。",
        "- δ1 与 ψ_b 只以 δ1+ψ_b 出现。底座纯旋转与 J1 零偏的光点完全相同；BIC 倾向自由参数更少的 H1，因此可以恢复预测，但无法可靠诊断物理伤类型。",
        "- 基线使用配置中的隐藏装配偏差进行全参数拟合；并不声称辨识出每个参数真值。普通伤试验以名义几何为已校准初始状态。",
        "- 四个护栏姿势不参与拟合或主动选点；额外审计姿势不参与拟合和护栏，真实参数只在评估器的独立审计中使用。",
        "- 加配重为小幅非几何变化，按目标文档采用手动重训；不作为几何伤发现率的分母。菜单外伤用随机松动独立测拒绝。",
        f"- 残差初训 {first_train.train_count}/{first_train.holdout_count} 条训练/时间留出；配重重训 {second_train.train_count}/{second_train.holdout_count} 条。留出样本未混回最终模型。",
        "", "## 证据", "", f"- 聚合 JSON：`{output.with_suffix('.json').name}`。", f"- 逐次试验：`{raw_path.name}`。", f"- 每发和事件日志、版本、残差数值模型：`{metadata['runtime_evidence']}`。", "- pytest 原始输出：`pytest_output.txt`；JUnit：`pytest.xml`。", "- 配置 SHA-256、依赖版本、Python 版本和种子见聚合 JSON。"]
    output.write_text("\n".join(lines)+"\n")
    # The progress file always reflects measured values, not forecasts or constants.
    progress=root/"PROGRESS.md"
    text=progress.read_text()
    marker="\n## 最新完整实测\n"
    text=text.split(marker)[0]+marker+f"\n报告：{output.relative_to(root) if output.is_relative_to(root) else output}。每类 {trials} 次。\n\n"
    text+="\n".join(f"- {name}：{'通过' if ok else '未达标'}；{details[name]}。" for name,ok in criteria.items())+"\n"
    progress.write_text(text)
    print(json.dumps({"criteria":criteria,"elapsed_seconds":metadata["elapsed_seconds"],"report":str(output)},ensure_ascii=False,indent=2),flush=True)
    return complete_sample and all(criteria.values())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("reports/eval_sim_report.md"))
    parser.add_argument("--trials",type=int,help="debug only when below 100; never called a full acceptance run")
    parser.add_argument("--skip-pytest",action="store_true",help="debug only; test criterion remains failed")
    args=parser.parse_args()
    raise SystemExit(0 if evaluate(args.output.resolve(),args.trials,not args.skip_pytest) else 1)


if __name__=="__main__": main()
