import numpy as np
from rearm.interfaces import Geometry, ResidualModel
from rearm.types import Params


class SelfModel:
    def __init__(self, geometry: Geometry, residual: ResidualModel):
        self.geometry, self.residual = geometry, residual

    def predict(self, params: Params, q: np.ndarray, feats: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        correction, uncertainty = self.residual.predict(feats)
        return self.geometry.predict(params, q) + correction, uncertainty
