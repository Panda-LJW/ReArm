"""Composition/orchestration boundary; algorithms never perform I/O or call the UI."""
from __future__ import annotations

from collections import deque
from dataclasses import asdict
from pathlib import Path
from threading import Event as ThreadEvent, RLock
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
        self.stop_requested = ThreadEvent()
        self.stop_lock = RLock()
        self.stop_generation = self.stopping = 0
        self.laser_lock = RLock()
        self.laser_on = False
        self.estop_error = None
        self.busy = False
        self.active_command = None
        self.heal_start = None
        self.last_recovery_shots = 0
        self.last_recognition_shots = 0
        self.started = time.time()
        self.stats = {"recoveries": 0, "recognitions": 0, "rejections": 0, "manual_switches": 0,
                      "recovery_shots": [], "faults": {}, "history": []}
        self.last_preview = self.last_switch = None

    def record_recovery(self, kind, probes, shots, version_id=None, code=None, after_mm=None):
        # One row per self-healing attempt for the panel's history table.
        errors = [float(np.linalg.norm(s.residual)) for s in probes if s.residual is not None]
        self.stats["history"] = (self.stats["history"] + [{"timestamp": time.time(), "kind": kind, "code": code,
            "version_id": version_id, "shots": shots, "before_mm": float(np.median(errors)) if errors else None,
            "after_mm": None if after_mm is None else float(after_mm)}])[-self.config.thresholds["ui"]["history"]:]

    def emit(self, kind: str, **data):
        self.bus.publish(Event(kind, time.time(), data))

    def transition(self, state: State):
        self.state = state
        self.emit("state", state=state.value, heal_start=self.heal_start)

    def check_estop(self):
        if self.stop_requested.is_set():
            raise ValueError("emergency stop active; reset before operating")

    def set_laser(self, on: bool):
        # Only serialize the laser write, never the movement/observation workflow.
        with self.laser_lock:
            if on:
                self.check_estop()
            self.arm.laser(on)
            self.laser_on = bool(on)
            self.emit("laser", laser_on=self.laser_on)

    def estop(self):
        # Latch before touching any lock or driver, including unsupported hardware.
        with self.stop_lock:
            self.stop_requested.set()
            self.stop_generation += 1
            self.stopping += 1
            self.emit("estop", estop=True, laser_on=self.laser_on, estop_error=None)
        try:
            self.set_laser(False)
            self.estop_error = None
        except Exception:
            self.estop_error = "laser shutdown failed; check hardware emergency stop"
        with self.stop_lock:
            self.stopping -= 1
            result = {"estop": True, "laser_on": self.laser_on, "estop_error": self.estop_error}
            self.emit("safety", **result)
        return result

    def reset_estop(self):
        if self.busy or not self.lock.acquire(blocking=False):
            raise ValueError("operation still stopping; wait before resetting emergency stop")
        try:
            with self.stop_lock:
                generation = self.stop_generation
                if self.stopping:
                    raise ValueError("operation still stopping; wait before resetting emergency stop")
            try:
                self.set_laser(False)
            except Exception as error:
                raise ValueError("laser shutdown failed; cannot reset emergency stop") from error
            with self.stop_lock:
                if self.stopping or generation != self.stop_generation:
                    raise ValueError("operation still stopping; wait before resetting emergency stop")
                self.estop_error = None
                self.stop_requested.clear()
                self.emit("estop_reset", estop=False, laser_on=self.laser_on, estop_error=None)
            result = self.snapshot()
            self.emit("snapshot", snapshot=result)
            return result
        finally:
            self.lock.release()

    def model(self, version=None) -> Predictor:
        version = version or self.store.head()
        return self.predictor_factory(self.residual_loader(version.residual_id))

    def shoot(self, q: np.ndarray, anomalous=False, role="task") -> Shot:
        self.check_estop()
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
                self.heal_start = self.sequence
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
            self.check_estop()
            self.heal_start = None
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
            self.check_estop()
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
            self.check_estop()
            start = self.sequence
            self.heal_start = start
            old = self.store.head()
            self.transition(State.RECOGNIZE)
            count = self.config.thresholds["recognizer"]["probes"]
            probes = [self.shoot(q, True, "recognition") for q in self.probe_pool[:count]]
            self.last_recognition_shots = len(probes)
            match = self.store.match(probes)
            self.check_estop()
            if match is not None:
                self.store.checkout(match[0])
                self.emit("switch", version_id=match[0], rms=match[1], probe_shots=len(probes))
                self.detector.reset()
                self.transition(State.NORMAL)
                self.last_recovery_shots = self.sequence-start
                self.stats["recognitions"] += 1
                self.stats["recovery_shots"].append(self.last_recovery_shots)
                self.record_recovery("recognition", probes, self.last_recovery_shots, match[0], after_mm=match[1])
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
                self.check_estop()
                meta = {"kind": "geometry", "diagnosis": jsonable(diagnosis), "guard": jsonable(report),
                        "fit_q": [s.q for s in shots], "holdout_q": [s.q for s in holdout]}
                if report.accepted and fit.success:
                    # A changed geometry invalidates the residual coordinates; preserve old GP in its version.
                    self.store.commit(fit.params, "zero", meta)
                    self.stats["recoveries"] += 1
                    self.stats["recovery_shots"].append(self.sequence-start)
                    code = diagnosis.best.name.split(":")[0]
                    self.stats["faults"][code] = self.stats["faults"].get(code, 0) + 1
                    self.record_recovery("repair", probes, self.sequence-start, self.store.head().id, diagnosis.best.name, report.candidate_median)
                    self.transition(State.NORMAL)
                else:
                    self.stats["rejections"] += 1
                    self.store.reject(fit.params, meta, report.reasons or ("optimizer failed",))
                    self.record_recovery("rejected", probes, self.sequence-start, None, diagnosis.best.name, report.candidate_median)
                    self.transition(State.REJECTED)
            except ValueError as error:
                self.check_estop()
                self.store.reject(old.params, {"kind": "insufficient_observations"}, (str(error),))
                self.record_recovery("rejected", probes, self.sequence-start)
                self.transition(State.REJECTED)
            self.detector.reset()
            self.last_recovery_shots = self.sequence-start
            self.emit("snapshot", snapshot=self.snapshot())

    def retrain(self):
        with self.lock:
            self.check_estop()
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
                self.check_estop()
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
            self.check_estop()
            self.store.checkout(version_id, component)
            self.detector.reset()
            self.transition(State.NORMAL)
            self.emit("snapshot", snapshot=self.snapshot())

    def preview(self, version_id):
        """Fire the fixed probe poses and compare a stored version with the current one, without switching."""
        with self.lock:
            self.check_estop()
            if self.state not in (State.NORMAL, State.REJECTED):
                raise ValueError("machine busy; preview needs an idle arm")
            head, candidate = self.store.head(), self.store.get(version_id)
            current_model, candidate_model = self.model(head), self.model(candidate)
            rows = []
            for q in self.probe_pool[:self.config.thresholds["recognizer"]["probes"]]:
                self.check_estop()
                shot = self.shooter.shoot(q, candidate, candidate_model, True, "preview")
                self.shot_log.append(shot)
                current = current_model.predict(head.params, np.asarray(shot.q), shot.features())[0]
                observed = None if shot.observed is None else np.asarray(shot.observed)
                rows.append({"q": shot.q, "observed": shot.observed, "candidate": shot.predicted,
                             "current": current.tolist(),
                             "candidate_mm": None if observed is None else float(np.linalg.norm(observed - shot.predicted)),
                             "current_mm": None if observed is None else float(np.linalg.norm(observed - current))})
            self.check_estop()
            measured = [r for r in rows if r["candidate_mm"] is not None]
            limit = self.config.thresholds["guard"]["median_mm"]
            candidate_median = float(np.median([r["candidate_mm"] for r in measured])) if measured else None
            current_median = float(np.median([r["current_mm"] for r in measured])) if measured else None
            self.last_preview = {"version_id": version_id, "from": head.id, "time": time.time(), "shots": rows,
                                 "candidate_median": candidate_median, "current_median": current_median,
                                 "limit_mm": limit, "passed": candidate_median is not None and candidate_median <= limit}
            self.emit("preview", preview=self.last_preview)
            return self.last_preview

    def switch(self, version_id, confirm, component="both", force=False, operator="panel"):
        """Manual version change: needs a fresh passing preview (or force), and can be undone briefly."""
        with self.lock:
            self.check_estop()
            ui = self.config.thresholds["ui"]
            if confirm != version_id:
                raise ValueError("confirmation does not match the selected version")
            head = self.store.head()
            undo = (self.last_switch is not None and self.last_switch["to"] == head.id
                    and self.last_switch["from"] == version_id and time.time() - self.last_switch["time"] <= ui["undo_s"])
            preview = self.last_preview
            fresh = (preview is not None and preview["version_id"] == version_id and preview["from"] == head.id
                     and time.time() - preview["time"] <= ui["preview_valid_s"])
            if not undo and not fresh:
                raise ValueError("run a fresh preview of this version before switching")
            if not undo and not preview["passed"] and not force:
                raise ValueError("preview did not pass; switching needs force")
            self.rollback(version_id, component)
            self.stats["manual_switches"] += 1
            self.last_switch = {"from": head.id, "to": version_id, "time": time.time(), "operator": operator,
                                "undo": undo, "forced": bool(force and not undo and not preview["passed"])}
            self.last_preview = None
            self.emit("manual_switch", **self.last_switch)

    def snapshot(self):
        with self.lock:
            return jsonable({"state": self.state, "head": self.store.head(), "versions": self.store.list(),
                "estop": self.stop_requested.is_set(), "laser_on": self.laser_on, "estop_error": self.estop_error,
                "busy": self.busy, "active_command": self.active_command, "heal_start": self.heal_start,
                "command_shots": {"baseline": self.config.thresholds["fit"]["baseline_shots"] + self.config.thresholds["guard"]["poses"],
                                  "preview": self.config.thresholds["recognizer"]["probes"], "retrain": 0},
                "recent": list(self.recent), "diagnosis": self.last_diagnosis,
                "guard": self.last_guard, "training": self.last_training,
                "alarms": self.alarms, "shots": self.sequence, "history_limit": self.config.thresholds["ui"]["history"],
                "simulation": self.damage_callback is not None,
                "stats": self.stats | {"uptime_s": time.time() - self.started, "alarms": self.alarms, "shots": self.sequence},
                "preview": self.last_preview, "last_switch": self.last_switch})

    def command(self, name, payload):
        if name == "estop":
            return self.estop()
        if name == "reset_estop":
            return self.reset_estop()
        self.check_estop()
        if not self.lock.acquire(blocking=False):
            raise ValueError("machine busy; wait for the current operation")
        try:
            self.check_estop()
            self.busy, self.active_command = True, name
            self.emit("operation", busy=True, active_command=name)
            if name == "selfcheck":
                for _ in range(self.config.thresholds["detector"]["window"]):
                    self.step()
            elif name == "baseline":
                self.baseline()
            elif name == "retrain":
                self.retrain()
            elif name == "preview":
                self.preview(payload["version_id"])
            elif name == "switch":
                self.switch(payload["version_id"], payload.get("confirm"), payload.get("component", "both"),
                            bool(payload.get("force")), str(payload.get("operator", "panel")))
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
            self.check_estop()
        finally:
            if self.stop_requested.is_set() and self.state not in (State.NORMAL, State.REJECTED):
                self.transition(State.REJECTED)
            self.busy, self.active_command = False, None
            self.emit("operation", busy=False, active_command=None)
            try:
                self.emit("snapshot", snapshot=self.snapshot())
            finally:
                self.lock.release()
        return self.snapshot()
