"""Load YAML once at the composition boundary; never silently relax limits."""
from pathlib import Path
import numpy as np
import yaml
from rearm.types import Params, Settings


def load_config(root: str | Path = "config") -> Settings:
    root = Path(root)
    def read(name):
        with (root / name).open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
        if not isinstance(value, dict):
            raise ValueError(f"{name}: expected mapping")
        return value
    arm, thresholds, sim, camera = (read(n) for n in
        ("arm_nominal.yaml", "thresholds.yaml", "sim.yaml", "camera.yaml"))
    params = Params(**arm["params"])
    bounds = {k: tuple(map(float, v)) for k, v in arm["bounds"].items()}
    if set(bounds) != set(params.names()):
        raise ValueError("parameter bounds must cover every parameter")
    for k, (lo, hi) in bounds.items():
        if not np.isfinite([lo, hi, getattr(params, k)]).all() or not lo <= getattr(params, k) <= hi or lo >= hi:
            raise ValueError(f"invalid parameter/bounds: {k}")
    limits = np.asarray(arm["joint_limits"], dtype=float)
    if limits.shape != (3, 2) or not np.all(limits[:, 0] < limits[:, 1]):
        raise ValueError("invalid joint limits")
    board = np.array(arm["board_mm"], dtype=float)
    if board.shape != (2,) or not np.all(board > 0) or not 0 < arm["min_downward"] <= 1:
        raise ValueError("invalid board/ray constraints")
    for section in ("detector", "recognizer", "fit", "guard", "residual", "pool", "ik", "numeric", "task", "eval", "ui"):
        if not isinstance(thresholds.get(section), dict):
            raise ValueError(f"missing thresholds: {section}")
    if not 0 < thresholds["guard"]["reduction"] <= 1 or not 0 < thresholds["residual"]["holdout_fraction"] < 1:
        raise ValueError("invalid guard or temporal split")
    if thresholds["detector"]["window"] < 1 or sim["noise_mm"] < 0:
        raise ValueError("invalid detector or noise")
    if len(camera["marker_ids"]) != 4 or len(set(camera["marker_ids"])) != 4:
        raise ValueError("exactly four distinct board markers required")
    return Settings(params, bounds, limits, board, arm["min_downward"], thresholds, sim, camera)
