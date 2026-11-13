import time
import numpy as np
from rearm.interfaces import ArmIO, Predictor
from rearm.types import Settings, Shot, Version


class Shooter:
    def __init__(self, config: Settings, arm: ArmIO):
        self.config, self.arm = config, arm

    def shoot(self, q: np.ndarray, version: Version, model: Predictor,
              anomalous: bool = False, role: str = "task") -> Shot:
        self.arm.move_to(q, self.config.thresholds["task"]["speed"])
        time.sleep(self.config.thresholds["task"]["settle_seconds"])
        state = self.arm.read_state()
        predicted, uncertainty = model.predict(version.params, state.q, state.features())
        try:
            self.arm.laser(True)
            observed = self.arm.observe_spot()
        finally:
            self.arm.laser(False)
        residual = None if observed is None else observed - predicted
        return Shot(time.time(), state.q.tolist(), state.direction.tolist(), state.load,
                    state.temperature, state.voltage, predicted.tolist(),
                    None if observed is None else observed.tolist(),
                    None if residual is None else residual.tolist(), uncertainty.tolist(), version.id, anomalous, role)
