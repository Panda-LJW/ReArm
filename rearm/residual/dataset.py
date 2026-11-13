import numpy as np
from rearm.interfaces import Geometry
from rearm.types import Params, Settings, Shot, TrainingSet


class ResidualDataset:
    def __init__(self, config: Settings, geometry: Geometry):
        self.config, self.geometry = config, geometry

    def build(self, shots: list[Shot], params: Params, version_ids: set[str]) -> TrainingSet:
        valid = [s for s in shots if not s.anomalous and s.observed is not None
                 and s.residual is not None and s.role == "task" and s.version_id in version_ids
                 and np.linalg.norm(s.residual) <= self.config.thresholds["detector"]["alarm_mm"]]
        valid.sort(key=lambda s: s.timestamp)
        valid = valid[-self.config.thresholds["residual"]["max_samples"]:]
        if not valid:
            return TrainingSet(np.empty((0, 8)), np.empty((0, 2)), np.empty(0))
        q = np.array([s.q for s in valid])
        return TrainingSet(np.array([s.features() for s in valid]),
            np.array([s.observed for s in valid]) - self.geometry.predict(params, q),
            np.array([s.timestamp for s in valid]))
