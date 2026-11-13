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
    required = {
        "detector": ("window", "alarm_mm"), "recognizer": ("probes", "rms_mm", "runner_up_ratio"),
        "fit": ("huber_mm", "regularization", "max_nfev", "multistarts_deg", "snap_step_deg",
                "snap_tolerance_deg", "snap_accept_mm", "restart_stop_rms_mm", "noise_floor_mm",
                "initial_shots", "active_shots", "baseline_shots", "baseline_freeze"),
        "guard": ("poses", "median_mm", "reduction", "bound_tolerance"),
        "residual": ("cap_mm", "holdout_fraction", "min_samples", "max_samples", "length_scale",
                     "noise_mm", "signal_mm", "feature_scale", "min_improvement_mm"),
        "pool": ("seed", "samples", "size", "margin_mm", "jacobian_step", "condition_epsilon"),
        "ik": ("starts", "max_nfev", "tolerance_mm", "invalid_penalty"),
        "numeric": ("epsilon", "optimizer_tolerance"), "task": ("speed", "settle_seconds", "initial_q"),
        "ui": ("host", "port", "history"),
    }
    for section, keys in required.items():
        for key in keys:
            if key not in thresholds[section]:
                raise ValueError(f"missing threshold {section}.{key}")
    def check_finite(value, path):
        if isinstance(value, dict):
            for key, item in value.items(): check_finite(item, f"{path}.{key}")
        elif isinstance(value, list):
            for item in value: check_finite(item, path)
        elif isinstance(value, (float, int)) and not np.isfinite(value):
            raise ValueError(f"nonfinite configuration: {path}")
    for name, value in (("thresholds", thresholds), ("sim", sim), ("camera", camera)):
        check_finite(value, name)
    for section, keys in {
        "detector": ("window", "alarm_mm"), "recognizer": ("probes", "rms_mm"),
        "fit": ("max_nfev", "huber_mm", "initial_shots", "baseline_shots", "snap_step_deg"),
        "guard": ("poses", "median_mm"), "residual": ("cap_mm", "min_samples", "max_samples", "length_scale", "noise_mm", "signal_mm"),
        "pool": ("samples", "size", "jacobian_step", "condition_epsilon"),
        "ik": ("starts", "max_nfev", "tolerance_mm"), "numeric": ("epsilon", "optimizer_tolerance"),
        "task": ("speed",), "ui": ("port", "history"),
    }.items():
        if any(thresholds[section][key] <= 0 for key in keys):
            raise ValueError(f"nonpositive configuration in {section}")
    for section, keys in {"detector": ("window",), "recognizer": ("probes",),
        "fit": ("max_nfev", "initial_shots", "active_shots", "baseline_shots"), "guard": ("poses",),
        "residual": ("min_samples", "max_samples"), "pool": ("samples", "size"),
        "ik": ("starts", "max_nfev"), "ui": ("port", "history")}.items():
        if any(type(thresholds[section][key]) is not int for key in keys):
            raise ValueError(f"integer count required in {section}")
    if len(thresholds["residual"]["feature_scale"]) != 8 or min(thresholds["residual"]["feature_scale"]) <= 0:
        raise ValueError("eight positive residual feature scales required")
    if thresholds["residual"]["max_samples"] < thresholds["residual"]["min_samples"]:
        raise ValueError("residual sample bounds inverted")
    if not 0 < thresholds["recognizer"]["runner_up_ratio"] < 1:
        raise ValueError("invalid recognition runner-up ratio")
    if not 0 < thresholds["guard"]["reduction"] <= 1 or not 0 < thresholds["residual"]["holdout_fraction"] < 1:
        raise ValueError("invalid guard or temporal split")
    if thresholds["detector"]["window"] < 1 or sim["noise_mm"] < 0:
        raise ValueError("invalid detector or noise")
    if len(camera["marker_ids"]) != 4 or len(set(camera["marker_ids"])) != 4:
        raise ValueError("exactly four distinct board markers required")
    if np.asarray(camera["matrix"]).shape != (3, 3) or np.asarray(camera["marker_centers_mm"]).shape != (4, 2):
        raise ValueError("invalid camera matrix or board centers")
    if camera["marker_size_mm"] <= 0 or camera["pixels_per_mm"] <= 0:
        raise ValueError("invalid camera scale")
    if thresholds["task"]["settle_seconds"] < 0 or thresholds["fit"]["regularization"] < 0:
        raise ValueError("negative settling time or regularization")
    return Settings(params, bounds, limits, board, arm["min_downward"], thresholds, sim, camera)
