import time
import numpy as np
import pytest
from rearm.evo.calibrator import Calibrator
from rearm.evo.diagnoser import Diagnoser
from rearm.evo.detector import AnomalyDetector
from rearm.evo.guard import CalibrationGuard
from rearm.evo.recognizer import StateRecognizer
from rearm.evo.versions import FileVersionStore
from rearm.logging.bus import LocalEventBus
from rearm.logging.shot_log import JsonlShotLog
from rearm.logging.event_log import JsonlEventLog
from rearm.residual.zero import ZeroResidual
from rearm.model.self_model import SelfModel
from rearm.sim.sim_arm import SimArm
from rearm.task.shooter import Shooter
from rearm.types import Event, Shot, Version


def samples(config, geometry, pool, params, count=10):
    arm = SimArm(config, geometry, params)
    shooter = Shooter(config, arm)
    version = Version("v0001", config.nominal, "zero", True, {})
    return [shooter.shoot(q, version, SelfModel(geometry, ZeroResidual())) for q in pool[:count]]


def test_fit_and_diagnosis(config, geometry, pool):
    p = config.nominal.updated({"delta1": 15})
    shots = samples(config, geometry, pool, p, 12)
    fitter = Calibrator(config, geometry)
    diagnosis = Diagnoser(config, geometry, fitter).diagnose(config.nominal, shots)
    assert diagnosis.best.name == "H1"
    assert diagnosis.gear_steps["delta1"] == 1
    assert diagnosis.best.fit.rms < 0.5
    assert diagnosis.ambiguous
    q = Diagnoser(config, geometry, fitter).next_pose(diagnosis, pool, np.array([s.q for s in shots]))
    assert not any(np.allclose(q, s.q) for s in shots)


def test_guard_rejects_and_accepts(config, geometry, pool):
    old = config.nominal
    good = old.updated({"x_b": 20})
    shots = samples(config, geometry, pool, good, 4)
    guard = CalibrationGuard(config, geometry)
    assert guard.check(old, good, shots).accepted
    assert not guard.check(old, old.updated({"x_b": -20}), shots).accepted
    assert not guard.check(old, good, shots[:3]).accepted
    assert not guard.check(old, good.updated({"e": 100}), shots).accepted


def test_detector_isolated_outlier(config, geometry, pool):
    shots = samples(config, geometry, pool, config.nominal, 4)
    detector = AnomalyDetector(config)
    shots[0].residual = [100, 0]
    assert not any(detector.update(s) for s in shots)
    for s in shots[:3]:
        s.residual = [10, 0]
    detector.reset()
    assert [detector.update(s) for s in shots[:3]] == [False, False, True]


def test_version_roundtrip_and_logs(config, geometry, pool, tmp_path):
    bus = LocalEventBus()
    log = JsonlEventLog(tmp_path / "events.jsonl")
    unsubscribe = bus.subscribe(log.append)
    recognizer = StateRecognizer(config, geometry, lambda _: ZeroResidual())
    versions = FileVersionStore(tmp_path / "versions", bus, recognizer)
    first = versions.commit(config.nominal, "zero", {})
    second = versions.commit(config.nominal.updated({"delta1": 15}), "zero", {})
    rejected = versions.reject(config.nominal, {}, ("test",))
    assert versions.head().id == second
    with pytest.raises(ValueError):
        versions.checkout(rejected)
    with pytest.raises(ValueError):
        versions.get("../../outside")
    probes = samples(config, geometry, pool, config.nominal, 3)
    assert versions.match(probes)[0] == first
    versions.checkout(first)
    assert versions.head().params == config.nominal
    shot_log = JsonlShotLog(tmp_path / "shots.jsonl")
    for s in probes:
        shot_log.append(s)
    assert shot_log.read() == probes
    assert "rollback" in [e.kind for e in log.read()]
    unsubscribe()
    before = len(log.read())
    bus.publish(Event("ignored", time.time(), {}))
    assert len(log.read()) == before


def test_shooter_laser_off_on_failure(config, geometry, pool):
    arm = SimArm(config, geometry)
    def fail():
        raise RuntimeError("camera disconnected")
    arm.observe_spot = fail
    with pytest.raises(RuntimeError):
        Shooter(config, arm).shoot(pool[0], Version("v1", config.nominal, "zero", True, {}), SelfModel(geometry, ZeroResidual()))
    assert not arm.laser_on


def test_hypothesis_scoring_precedes_quantization(config,geometry,pool):
    calls=[]
    real=Calibrator(config,geometry)
    class RecordingFitter:
        def fit(self,reference,shots,free,snap=False):
            calls.append(snap)
            return real.fit(reference,shots,free,snap)
    shots=samples(config,geometry,pool,config.nominal.updated({"delta1":15}),10)
    result=Diagnoser(config,geometry,RecordingFitter()).diagnose(config.nominal,shots)
    assert result.best.name=="H1"
    assert calls and not any(calls)


def test_huber_fit_resists_single_bad_measurement(config,geometry,pool):
    truth=config.nominal.updated({"x_b":20})
    shots=samples(config,geometry,pool,truth,12)
    shots[0].observed=np.asarray(shots[0].observed)+[40,-30]
    result=Calibrator(config,geometry).fit(config.nominal,shots,("x_b","y_b"))
    assert abs(result.params.x_b-truth.x_b)<0.5
    assert abs(result.params.y_b-truth.y_b)<0.5


def test_recognizer_rejects_ties_and_missing_observations(config,geometry,pool):
    recognizer=StateRecognizer(config,geometry,lambda _:ZeroResidual())
    versions=[Version("v0001",config.nominal,"zero",True,{}),Version("v0002",config.nominal,"zero",True,{})]
    probes=samples(config,geometry,pool,config.nominal,3)
    assert recognizer.match(probes,versions) is None
    assert recognizer.match(probes,versions[:1])[0]=="v0001"
    probes[0].observed=None
    assert recognizer.match(probes,versions[:1]) is None


def test_small_continuous_shift_is_not_forced_onto_gear_grid(config,geometry,pool):
    truth=config.nominal.updated({"delta1":0.7})
    shots=samples(config,geometry,pool,truth,16)
    fit=Calibrator(config,geometry).fit(config.nominal,shots,("delta1",),snap=True)
    assert abs(fit.params.delta1-truth.delta1)<0.1
