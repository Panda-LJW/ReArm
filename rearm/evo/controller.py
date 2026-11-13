"""Composition/orchestration boundary; algorithms never perform I/O or call the UI."""
from __future__ import annotations

from collections import deque
from dataclasses import asdict
from pathlib import Path
from threading import RLock
import time
import numpy as np

from rearm.interfaces import (ArmIO, DatasetBuilder, Detector, Diagnostic, EventBus, Fitter,
    Geometry, Guard, IKSolver, Predictor, ResidualModel, ShotLog, ShotRunner, Trainer, VersionStore)
from rearm.types import Damage, Event, Settings, Shot, State, jsonable


class Controller:
    def __init__(self, config: Settings, arm: ArmIO, geometry: Geometry, bus: EventBus,
                 store: VersionStore, shot_log: ShotLog, shooter: ShotRunner,
                 detector: Detector, diagnoser: Diagnostic, fitter: Fitter, guard: Guard,
                 dataset: DatasetBuilder, trainer: Trainer, ik: IKSolver,
                 pool: np.ndarray, probe_pool: np.ndarray, residual_loader,
                 residual_factory, predictor_factory, residual_saver, damage_callback=None):
        self.config, self.arm, self.geometry, self.bus = config, arm, geometry, bus
        self.store, self.shot_log, self.shooter = store, shot_log, shooter
        self.detector, self.diagnoser, self.fitter, self.guard = detector, diagnoser, fitter, guard
        self.dataset, self.trainer, self.ik = dataset, trainer, ik
        self.pool, self.probe_pool = pool, probe_pool
        self.residual_loader, self.residual_factory = residual_loader, residual_factory
        self.predictor_factory, self.residual_saver = predictor_factory, residual_saver
        self.damage_callback = damage_callback
        self.state = State.NORMAL
        self.last_diagnosis = self.last_guard = self.last_training = None
        self.recent = deque(maxlen=config.thresholds["ui"]["history"])
        self.sequence = 0
        self.alarms = 0
        self.lock = RLock()
        self.last_recovery_shots = 0
        self.last_recognition_shots = 0

    def emit(self, kind: str, **data):
        self.bus.publish(Event(kind, time.time(), data))

    def transition(self, state: State):
        self.state = state
        self.emit("state", state=state.value)

    def model(self, version=None) -> Predictor:
        version = version or self.store.head()
        return self.predictor_factory(self.residual_loader(version.residual_id))

    def shoot(self, q: np.ndarray, anomalous=False, role="task") -> Shot:
        version = self.store.head()
        shot = self.shooter.shoot(q, version, self.model(version), anomalous, role)
        # Exclude the first suspect shot too, before the 3-shot alarm is latched.
        shot.anomalous |= shot.residual is None or np.linalg.norm(shot.residual) > self.config.thresholds["detector"]["alarm_mm"]
        self.shot_log.append(shot)
        self.recent.append(shot)
        self.sequence += 1
        self.emit("shot", shot=jsonable(shot))
        return shot

    def step(self, q: np.ndarray | None = None, recover=True) -> Shot:
        with self.lock:
            if q is None:
                q = self.probe_pool[self.sequence % len(self.probe_pool)]
            shot = self.shoot(q, self.state != State.NORMAL)
            if self.detector.update(shot):
                self.alarms += 1
                self.transition(State.ALARM)
                self.emit("alarm", count=self.alarms)
                if recover:
                    self.recover()
            return shot

    def target(self, xy: np.ndarray) -> Shot:
        with self.lock:
            version = self.store.head()
            residual = self.residual_loader(version.residual_id)
            previous = self.arm.read_state()
            def correction(q):
                feats = np.r_[q, np.sign(q-previous.q), previous.load, previous.temperature]
                return residual.predict(feats)[0]
            q = self.ik.solve(xy, version.params, self.pool, correction)
            return self.step(q)

    def baseline(self):
        with self.lock:
            self.transition(State.CALIBRATE)
            old = self.store.head()
            n = self.config.thresholds["fit"]["baseline_shots"]
            shots = [self.shoot(q, True, "baseline_fit") for q in self.pool[:n]]
            fit = self.fitter.fit(old.params, shots, old.params.names())
            self.emit("calibration", mode="baseline", result=jsonable(fit))
            self.transition(State.GUARD)
            count = self.config.thresholds["guard"]["poses"]
            holdout = [self.shoot(q, True, "baseline_holdout") for q in self.pool[n:n+count]]
            report = self.guard.check(old.params, fit.params, holdout)
            self.last_guard = report
            if report.accepted and fit.success:
                self.store.commit(fit.params, "zero", {"kind": "baseline", "guard": jsonable(report)})
            else:
                self.store.reject(fit.params, {"kind": "baseline", "guard": jsonable(report)}, report.reasons or ("optimizer failed",))
            self.detector.reset()
            self.transition(State.NORMAL if report.accepted or report.old_median <= self.config.thresholds["guard"]["median_mm"] else State.REJECTED)
            self.emit("snapshot", snapshot=self.snapshot())
            return report

    def recover(self):
        with self.lock:
            start = self.sequence
            old = self.store.head()
            self.transition(State.RECOGNIZE)
            count = self.config.thresholds["recognizer"]["probes"]
            probes = [self.shoot(q, True, "recognition") for q in self.probe_pool[:count]]
            self.last_recognition_shots = len(probes)
            match = self.store.match(probes)
            if match is not None:
                self.store.checkout(match[0])
                self.emit("switch", version_id=match[0], rms=match[1], probe_shots=len(probes))
                self.detector.reset()
                self.transition(State.NORMAL)
                self.last_recovery_shots = self.sequence-start
                self.emit("snapshot", snapshot=self.snapshot())
                return
            self.transition(State.DIAGNOSE)
            fit_options = self.config.thresholds["fit"]
            reserved = self.probe_pool[-self.config.thresholds["guard"]["poses"]:]
            available = self.probe_pool[count:-len(reserved)]
            shots = list(probes)
            for q in available[:fit_options["initial_shots"] - len(shots)]:
                shots.append(self.shoot(q, True, "diagnostic"))
            try:
                diagnosis = self.diagnoser.diagnose(old.params, shots)
                for _ in range(fit_options["active_shots"]):
                    used = np.concatenate([np.array([s.q for s in shots]), reserved])
                    q = self.diagnoser.next_pose(diagnosis, self.probe_pool, used)
                    shots.append(self.shoot(q, True, "active_diagnostic"))
                    diagnosis = self.diagnoser.diagnose(old.params, shots)
                self.last_diagnosis = diagnosis
                self.emit("diagnosis", diagnosis=jsonable(diagnosis))
                self.transition(State.CALIBRATE)
                fit = diagnosis.proposed
                self.emit("calibration", mode="recovery", result=jsonable(fit))
                self.transition(State.GUARD)
                holdout = [self.shoot(q, True, "guard") for q in reserved]
                report = self.guard.check(old.params, fit.params, holdout)
                self.last_guard = report
                meta = {"kind": "geometry", "diagnosis": jsonable(diagnosis), "guard": jsonable(report),
                        "fit_q": [s.q for s in shots], "holdout_q": [s.q for s in holdout]}
                if report.accepted and fit.success:
                    # A changed geometry invalidates the residual coordinates; preserve old GP in its version.
                    self.store.commit(fit.params, "zero", meta)
                    self.transition(State.NORMAL)
                else:
                    self.store.reject(fit.params, meta, report.reasons or ("optimizer failed",))
                    self.transition(State.REJECTED)
            except ValueError as error:
                self.store.reject(old.params, {"kind": "insufficient_observations"}, (str(error),))
                self.transition(State.REJECTED)
            self.detector.reset()
            self.last_recovery_shots = self.sequence-start
            self.emit("snapshot", snapshot=self.snapshot())

    def retrain(self):
        with self.lock:
            previous_state = self.state
            if previous_state != State.NORMAL:
                raise ValueError("resolve the geometry anomaly before residual training")
            self.transition(State.TRAINING)
            old = self.store.head()
            try:
                ids = {v.id for v in self.store.list() if v.accepted and v.params == old.params}
                data = self.dataset.build(self.shot_log.read(), old.params, ids)
                candidate = self.residual_factory()
                report = self.trainer.train(data, self.residual_loader(old.residual_id), candidate)
                self.last_training = report
                if report.accepted:
                    residual_id = self.residual_saver(candidate)
                    self.store.commit(old.params, residual_id, {"kind": "residual", "training": jsonable(report)})
                self.emit("retrained", report=jsonable(report), accepted=report.accepted)
                return report
            finally:
                self.transition(previous_state)
                self.emit("snapshot", snapshot=self.snapshot())

    def rollback(self, version_id, component="both"):
        with self.lock:
            self.store.checkout(version_id, component)
            self.detector.reset()
            self.transition(State.NORMAL)
            self.emit("snapshot", snapshot=self.snapshot())

    def snapshot(self):
        with self.lock:
            return jsonable({"state": self.state, "head": self.store.head(), "versions": self.store.list(),
                "recent": list(self.recent), "diagnosis": self.last_diagnosis,
                "guard": self.last_guard, "training": self.last_training,
                "alarms": self.alarms, "shots": self.sequence, "history_limit": self.config.thresholds["ui"]["history"],
                "simulation": self.damage_callback is not None})

    def command(self, name, payload):
        with self.lock:
            if name == "selfcheck":
                for _ in range(self.config.thresholds["detector"]["window"]):
                    self.step()
            elif name == "baseline":
                self.baseline()
            elif name == "retrain":
                self.retrain()
            elif name == "rollback":
                self.rollback(payload["version_id"], payload.get("component", "both"))
            elif name == "inject":
                if self.damage_callback is None:
                    raise ValueError("damage injection is simulation-only")
                def decode(value):
                    return Damage(value["kind"], float(value.get("amount", 0)), tuple(decode(v) for v in value.get("components", [])))
                damage = decode(payload)
                self.damage_callback(damage)
                self.emit("damage_injected", damage=jsonable(damage))
            else:
                raise ValueError("unknown command")
            result = self.snapshot()
            self.emit("snapshot", snapshot=result)
            return result
