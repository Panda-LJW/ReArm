from collections import deque
import numpy as np
from rearm.types import Settings, Shot


class AnomalyDetector:
    def __init__(self, config: Settings):
        self.config = config.thresholds["detector"]
        self.errors = deque(maxlen=self.config["window"])

    def update(self, shot: Shot) -> bool:
        error = np.inf if shot.residual is None else float(np.linalg.norm(shot.residual))
        self.errors.append(error)
        # A complete median window suppresses one isolated outlier without hiding a persistent shift.
        return (len(self.errors) == self.errors.maxlen
                and np.median(self.errors) > self.config["alarm_mm"])

    def reset(self) -> None:
        self.errors.clear()
