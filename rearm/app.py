"""The sole application composition root. No network, model API or installation."""
from pathlib import Path
import numpy as np
from rearm.config import load_config
from rearm.evo.calibrator import Calibrator
from rearm.evo.controller import Controller
from rearm.evo.detector import AnomalyDetector
from rearm.evo.diagnoser import Diagnoser
from rearm.evo.guard import CalibrationGuard
from rearm.evo.recognizer import StateRecognizer
from rearm.evo.versions import FileVersionStore
from rearm.logging.bus import LocalEventBus
from rearm.logging.event_log import JsonlEventLog
from rearm.logging.shot_log import JsonlShotLog
from rearm.model.ik import NumericalIK
from rearm.model.kinematics import Kinematics
from rearm.model.pose_pool import PosePool
from rearm.model.self_model import SelfModel
from rearm.residual.dataset import ResidualDataset
from rearm.residual.gp import GPResidual
from rearm.residual.trainer import TemporalTrainer
from rearm.residual.zero import ZeroResidual
from rearm.sim.damage import damaged_params
from rearm.sim.sim_arm import SimArm
from rearm.task.shooter import Shooter
from rearm.types import Damage, Settings


def build_app(config: Settings | None = None, data_dir="runtime", sim=True, seed=None, true_params=None) -> Controller:
    config = config or load_config(Path(__file__).resolve().parents[1] / "config")
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    geometry = Kinematics(config)
    if not sim:
        raise NotImplementedError("v0 hardware driver skeleton only; use --sim")
    arm = SimArm(config, geometry, true_params, seed)
    initial_physical = arm.true_params
    bus = LocalEventBus()
    event_log = JsonlEventLog(root / "events.jsonl")
    bus.subscribe(event_log.append)
    residual_dir = root / "residuals"
    residual_dir.mkdir(exist_ok=True)
    cache = {}
    def residual_loader(residual_id):
        if residual_id == "zero":
            return ZeroResidual()
        if residual_id not in cache:
            if not residual_id.startswith("r") or not residual_id[1:].isdigit():
                raise ValueError("invalid residual artifact id")
            model = GPResidual(config)
            model.load(residual_dir / f"{residual_id}.npz")
            cache[residual_id] = model
        return cache[residual_id]
    def residual_saver(model):
        numbers = [int(p.stem[1:]) for p in residual_dir.glob("r[0-9]*.npz")]
        residual_id = f"r{max(numbers, default=0)+1:04d}"
        temporary = residual_dir / f"{residual_id}.tmp"
        model.save(temporary)
        temporary.replace(residual_dir / f"{residual_id}.npz")
        cache[residual_id] = model
        return residual_id
    store = FileVersionStore(root / "versions", bus, StateRecognizer(config, geometry, residual_loader))
    if not (root / "versions" / "HEAD").exists():
        store.commit(config.nominal, "zero", {"kind": "initial"})
    factory = PosePool(config, geometry)
    pool = factory.generate(config.nominal)
    # Fixed self-check poses must remain visible throughout configured angular bounds.
    envelopes = tuple(config.nominal.updated({name: value}) for name in ("delta1", "delta2") for value in config.bounds[name])
    probe_pool = factory.generate(config.nominal, envelopes)
    fitter = Calibrator(config, geometry)
    def inject(damage: Damage):
        if damage.kind == "restore":
            arm.true_params, arm.load, arm.looseness = initial_physical, config.sim["load"], config.sim["looseness_mm"]
        elif damage.kind == "weight":
            arm.load *= config.sim["weight_multiplier"]
        elif damage.kind == "loose":
            arm.looseness = config.sim["loose_amplitude_mm"]
        elif damage.kind == "combination":
            # Validate all geometry before mutating, so a failed command is atomic.
            damaged_params(arm.true_params, damage, config)
            for part in damage.components:
                inject(part)
        else:
            arm.true_params = damaged_params(arm.true_params, damage, config)
    return Controller(config, arm, geometry, bus, store, JsonlShotLog(root / "shots.jsonl"),
        Shooter(config, arm), AnomalyDetector(config), Diagnoser(config, geometry, fitter), fitter,
        CalibrationGuard(config, geometry), ResidualDataset(config, geometry), TemporalTrainer(config),
        NumericalIK(config, geometry), pool, probe_pool, residual_loader, lambda: GPResidual(config),
        lambda residual: SelfModel(geometry, residual), residual_saver, inject)
