from collections.abc import Callable
import numpy as np
from scipy.optimize import least_squares
from rearm.interfaces import Geometry
from rearm.types import Params, Settings


class NumericalIK:
    def __init__(self, config: Settings, geometry: Geometry):
        self.config, self.geometry = config, geometry

    def solve(self, target: np.ndarray, params: Params, pool: np.ndarray,
              correction: Callable[[np.ndarray], np.ndarray] | None = None) -> np.ndarray:
        target = np.asarray(target, dtype=float)
        if target.shape != (2,) or not np.isfinite(target).all() or np.any(np.abs(target) > self.config.board_mm / 2):
            raise ValueError("target outside board or nonfinite")
        c, limits = self.config.thresholds["ik"], self.config.joint_limits
        def error(q):
            point = self.geometry.predict(params, q)
            return point + (correction(q) if correction else 0) - target
        starts = np.argsort(np.linalg.norm(self.geometry.predict(params, pool) - target, axis=1))[:c["starts"]]
        best, best_error = None, np.inf
        for i in starts:
            fit = least_squares(error, pool[i], bounds=(limits[:, 0], limits[:, 1]), max_nfev=c["max_nfev"])
            loss = float(np.linalg.norm(error(fit.x)))
            if self.geometry.valid(params, fit.x) and loss < best_error:
                best, best_error = fit.x, loss
            if best_error <= c["tolerance_mm"]:
                return best
        if best is None or best_error > c["tolerance_mm"]:
            raise ValueError(f"unreachable target; best residual {best_error:.3f} mm")
        return best
