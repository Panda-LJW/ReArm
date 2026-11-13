import numpy as np
from rearm.interfaces import Geometry, ResidualModel
from rearm.types import Settings, Shot, Version
from collections.abc import Callable


class StateRecognizer:
    def __init__(self, config: Settings, geometry: Geometry,
                 residual_loader: Callable[[str], ResidualModel]):
        self.config, self.geometry, self.residual_loader = config, geometry, residual_loader

    def match(self, probes: list[Shot], versions: list[Version]) -> tuple[str, float] | None:
        c = self.config.thresholds["recognizer"]
        if len(probes) != c["probes"] or any(s.observed is None for s in probes):
            return None
        q, xy = np.array([s.q for s in probes]), np.array([s.observed for s in probes])
        feats = np.array([s.features() for s in probes])
        scores = []
        for version in versions:
            if not version.accepted or not np.all(self.geometry.valid(version.params, q)):
                continue
            correction, _ = self.residual_loader(version.residual_id).predict(feats)
            rms = float(np.sqrt(np.mean(np.sum((self.geometry.predict(version.params, q) + correction - xy) ** 2, axis=1))))
            scores.append((version.id, rms))
        scores.sort(key=lambda pair: pair[1])
        if scores and scores[0][1] < c["rms_mm"] and (len(scores) == 1 or scores[0][1] < c["runner_up_ratio"] * scores[1][1]):
            return scores[0]
        return None
