from itertools import combinations
import numpy as np
from rearm.interfaces import Fitter, Geometry
from rearm.types import Diagnosis, Hypothesis, Params, Settings, Shot


class Diagnoser:
    def __init__(self, config: Settings, geometry: Geometry, fitter: Fitter):
        self.config, self.geometry, self.fitter = config, geometry, fitter

    def diagnose(self, reference: Params, shots: list[Shot]) -> Diagnosis:
        groups = {"H1": ("delta1",), "H2": ("delta2",), "H3": ("e",),
                  "H4": ("x_b", "y_b", "psi_b")}
        models = [(name, (name,), names) for name, names in groups.items()]
        models += [("H5:" + "+".join(pair), pair, groups[pair[0]] + groups[pair[1]])
                   for pair in combinations(groups, 2)]
        models += [("H6", ("H6",), tuple(k for k in reference.names() if k not in self.config.thresholds["fit"]["baseline_freeze"]))]
        n = 2 * sum(s.observed is not None for s in shots)
        if n < 2:
            raise ValueError("no measured points for diagnosis")
        ranked = []
        # All hypotheses explain the SAME sensor, hence share its configured
        # measurement variance. Gaussian known-variance BIC (constant omitted):
        # -2 log L + k log n = SSE / sigma^2 + k log n.
        variance = self.config.thresholds["fit"]["measurement_sigma_mm"] ** 2
        for name, members, free in models:
            # BIC compares continuous fits with k continuous degrees of freedom.
            # Snapping before scoring unfairly constrains H1/H2 while leaving H4
            # free to fit measurement noise. Quantize only the selected calibration.
            fit = self.fitter.fit(reference, shots, free, snap=False)
            bic = fit.sse / variance + len(free) * np.log(n)
            ranked.append(Hypothesis(name, members, fit, float(bic)))
        ranked.sort(key=lambda h: h.bic)
        best = ranked[0]
        proposed = self.fitter.fit(reference, shots, best.fit.free, snap=True)
        deltas = {k: getattr(proposed.params, k) - getattr(reference, k) for k in best.fit.free}
        step = self.config.thresholds["fit"]["snap_step_deg"]
        epsilon = self.config.thresholds["numeric"]["epsilon"]
        steps = {k: int(round(v / step)) for k, v in deltas.items() if k.startswith("delta") and abs(v) > epsilon}
        # A hypothesis is a set of parameters allowed to change, not a claim that
        # every one DID change. Report only groups retained by the final fit.
        # Exact grid zeros are removed; no magnitude-based damage whitelist.
        changes = tuple(group for group in best.groups if group == "H6" or
                        any(abs(deltas.get(name, 0)) > epsilon for name in groups[group]))
        ambiguous = ("delta1 and psi_b are observationally equivalent",) if "delta1" in best.fit.free or "psi_b" in best.fit.free else ()
        return Diagnosis(best, tuple(ranked), deltas, steps, changes, proposed, ambiguous)

    def next_pose(self, diagnosis: Diagnosis, pool: np.ndarray, used: np.ndarray) -> np.ndarray:
        first, second = diagnosis.ranked[:2]
        valid = self.geometry.valid(first.fit.params, pool) & self.geometry.valid(second.fit.params, pool)
        if len(used):
            valid &= ~np.any(np.all(np.isclose(pool[:, None], used[None]), axis=-1), axis=1)
        choices = pool[valid]
        if not len(choices):
            raise ValueError("no unused valid discriminating pose")
        separation = np.linalg.norm(self.geometry.predict(first.fit.params, choices)
                                    - self.geometry.predict(second.fit.params, choices), axis=1)
        return choices[int(np.argmax(separation))].copy()
