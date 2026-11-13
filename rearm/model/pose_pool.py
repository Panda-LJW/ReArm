import numpy as np
from rearm.interfaces import Geometry
from rearm.types import Params, Settings


class PosePool:
    def __init__(self, config: Settings, geometry: Geometry):
        self.config, self.geometry = config, geometry

    def generate(self, params: Params, robust_params: tuple[Params, ...] = ()) -> np.ndarray:
        c = self.config.thresholds["pool"]
        rng = np.random.default_rng(c["seed"])
        limits = self.config.joint_limits
        q = rng.uniform(limits[:, 0], limits[:, 1], (c["samples"], 3))
        valid = np.ones(len(q), dtype=bool)
        for p in (params, *robust_params):
            valid &= self.geometry.valid(p, q)
            valid &= np.all(np.abs(self.geometry.predict(p, q)) < self.config.board_mm / 2 - c["margin_mm"], axis=1)
        q = q[valid]
        if len(q) < self.config.thresholds["guard"]["poses"] + self.config.thresholds["fit"]["initial_shots"]:
            raise ValueError("too few safe candidate poses")
        # Deterministic farthest point sampling spreads angles, not only impact points.
        scaled = q / (limits[:, 1] - limits[:, 0])
        chosen = [0]
        distances = np.full(len(q), np.inf)
        for _ in range(min(c["size"], len(q)) - 1):
            distances = np.minimum(distances, np.linalg.norm(scaled - scaled[chosen[-1]], axis=1))
            chosen.append(int(np.argmax(distances)))
        return q[chosen]

    def condition(self, params: Params, poses: np.ndarray, names: tuple[str, ...]) -> float:
        matrix = self.geometry.jacobian(params, poses, names).reshape(-1, len(names))
        s = np.linalg.svd(matrix, compute_uv=False)
        return float(s[0] / max(s[-1], self.config.thresholds["pool"]["condition_epsilon"]))
