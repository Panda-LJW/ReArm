import numpy as np
from rearm.interfaces import Geometry
from rearm.types import GuardReport, Params, Settings, Shot


class CalibrationGuard:
    def __init__(self, config: Settings, geometry: Geometry):
        self.config, self.geometry = config, geometry

    def check(self, old: Params, candidate: Params, holdout: list[Shot]) -> GuardReport:
        c = self.config.thresholds["guard"]
        valid = len(holdout) == c["poses"] and all(s.observed is not None for s in holdout)
        in_bounds = all(lo - c["bound_tolerance"] <= getattr(candidate, k) <= hi + c["bound_tolerance"]
                        for k, (lo, hi) in self.config.bounds.items())
        if valid:
            q, xy = np.array([s.q for s in holdout]), np.array([s.observed for s in holdout])
            old_median = float(np.median(np.linalg.norm(self.geometry.predict(old, q) - xy, axis=1)))
            candidate_median = float(np.median(np.linalg.norm(self.geometry.predict(candidate, q) - xy, axis=1)))
            valid = bool(np.all(self.geometry.valid(candidate, q)))
        else:
            old_median = candidate_median = np.inf
        reduction = 1 - candidate_median / max(old_median, self.config.thresholds["numeric"]["epsilon"]) if np.isfinite(old_median) else -np.inf
        reasons = []
        if not valid:
            reasons.append("missing observations or invalid holdout poses")
        if not in_bounds:
            reasons.append("parameter bounds exceeded")
        if candidate_median > c["median_mm"]:
            reasons.append("holdout median exceeds 3 mm")
        if reduction < c["reduction"]:
            reasons.append("holdout improvement below 70 percent")
        return GuardReport(not reasons, candidate_median, old_median, float(reduction), in_bounds, tuple(reasons), len(holdout))
