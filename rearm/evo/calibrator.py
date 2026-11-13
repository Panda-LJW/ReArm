import numpy as np
from scipy.optimize import least_squares
from rearm.interfaces import Geometry
from rearm.types import FitResult, Params, Settings, Shot


class Calibrator:
    """Robust bounded fitting of only the requested parameters, with a weak prior."""
    def __init__(self, config: Settings, geometry: Geometry):
        self.config, self.geometry = config, geometry

    def fit(self, reference: Params, shots: list[Shot], free: tuple[str, ...], snap: bool = False) -> FitResult:
        shots = [s for s in shots if s.observed is not None]
        if not shots or not free:
            raise ValueError("fitting needs observations and free parameters")
        if any(k not in reference.names() for k in free) or len(set(free)) != len(free):
            raise ValueError("invalid free parameter list")
        q, observed = np.array([s.q for s in shots]), np.array([s.observed for s in shots])
        c = self.config.thresholds["fit"]
        lo, hi = np.array([self.config.bounds[k] for k in free]).T
        prior = np.array([getattr(reference, k) for k in free])
        scale = hi - lo

        def solve(base, names, initial):
            if not names:
                return base, True
            lower, upper = np.array([self.config.bounds[k] for k in names]).T
            ref = np.array([getattr(reference, k) for k in names])
            def objective(x):
                p = base.updated(dict(zip(names, x)))
                error = (self.geometry.predict(p, q) - observed).ravel()
                penalty = np.sqrt(c["regularization"]) * (x - ref) / (upper - lower)
                return np.r_[error, penalty]
            tolerance = self.config.thresholds["numeric"]["optimizer_tolerance"]
            result = least_squares(objective, np.clip(initial, lower, upper),
                bounds=(lower, upper), loss="huber", f_scale=c["huber_mm"],
                x_scale=upper-lower, max_nfev=c["max_nfev"],
                ftol=tolerance, xtol=tolerance, gtol=tolerance)
            return base.updated(dict(zip(names, result.x))), bool(result.success)

        starts = [prior]
        for name in ("delta1", "delta2"):
            if name in free:
                for value in c["multistarts_deg"]:
                    start = prior.copy()
                    start[free.index(name)] = value
                    if not any(np.array_equal(start, other) for other in starts):
                        starts.append(start)
        best_params, best_sse, success = reference, np.inf, False
        for initial in starts:
            params, ok = solve(reference, free, initial)
            sse = float(np.sum((self.geometry.predict(params, q) - observed) ** 2))
            if sse < best_sse:
                best_params, best_sse, success = params, sse, ok
            # Additional starts are needed for large/local-minimum fits, not a solved noise floor.
            if ok and np.sqrt(sse / len(shots)) <= c["restart_stop_rms_mm"]:
                break
        if snap:
            snapped = {}
            for name in ("delta1", "delta2", "delta3"):
                if name in free:
                    value = getattr(best_params, name)
                    grid = np.round(value / c["snap_step_deg"]) * c["snap_step_deg"]
                    if abs(value - grid) < c["snap_tolerance_deg"] and self.config.bounds[name][0] <= grid <= self.config.bounds[name][1]:
                        snapped[name] = float(grid)
            if snapped:
                names = tuple(k for k in free if k not in snapped)
                params, ok = solve(best_params.updated(snapped), names, [getattr(best_params, k) for k in names])
                sse = float(np.sum((self.geometry.predict(params, q) - observed) ** 2))
                if np.sqrt(sse / len(shots)) <= np.sqrt(best_sse / len(shots)) + c["snap_accept_mm"]:
                    best_params, best_sse, success = params, sse, ok
        return FitResult(best_params, float(np.sqrt(best_sse / len(shots))), best_sse, success, free)
