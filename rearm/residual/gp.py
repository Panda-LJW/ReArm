from pathlib import Path
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF
from rearm.types import Settings


class GPResidual:
    """Deterministic GP with vector correction cap and posterior standard deviation.

    Artifacts contain numeric training data and hyperparameters, never executable pickle.
    Persistence is the explicit ResidualModel protocol exception to pure algorithms.
    """
    def __init__(self, config: Settings):
        self.options = dict(config.thresholds["residual"])
        self.model = None
        self.features = self.targets = None

    def _scaled(self, feats):
        return np.asarray(feats, dtype=float) / np.asarray(self.options["feature_scale"])

    def fit(self, feats: np.ndarray, targets: np.ndarray) -> None:
        feats, targets = np.asarray(feats, dtype=float), np.asarray(targets, dtype=float)
        if feats.ndim != 2 or feats.shape[1] != len(self.options["feature_scale"]) or targets.shape != (len(feats), 2) or not len(feats):
            raise ValueError("invalid GP training shapes")
        if not np.isfinite(feats).all() or not np.isfinite(targets).all():
            raise ValueError("nonfinite GP training data")
        self.features, self.targets = feats.copy(), targets.copy()
        self.model = GaussianProcessRegressor(
            kernel=ConstantKernel(self.options["signal_mm"] ** 2, constant_value_bounds="fixed")
                    * RBF(self.options["length_scale"], length_scale_bounds="fixed"),
            alpha=self.options["noise_mm"] ** 2, optimizer=None, normalize_y=False)
        self.model.fit(self._scaled(feats), targets)

    def predict(self, feats: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        feats = np.asarray(feats, dtype=float)
        single = feats.ndim == 1
        x = np.atleast_2d(feats)
        if self.model is None:
            mean, std = np.zeros((len(x), 2)), np.full((len(x), 2), self.options["signal_mm"])
        else:
            mean, std = self.model.predict(self._scaled(x), return_std=True)
            if std.ndim == 1:
                std = np.repeat(std[:, None], 2, axis=1)
        norm = np.linalg.norm(mean, axis=1, keepdims=True)
        mean *= np.minimum(1, self.options["cap_mm"] / np.maximum(norm, np.finfo(float).eps))
        return (mean[0], std[0]) if single else (mean, std)

    def save(self, path: str | Path) -> None:
        if self.model is None:
            raise ValueError("cannot save an unfitted GP")
        import json
        with Path(path).open("wb") as stream:
            np.savez_compressed(stream, features=self.features, targets=self.targets,
                                options=json.dumps(self.options), schema=1)

    def load(self, path: str | Path) -> None:
        import json
        with np.load(path, allow_pickle=False) as saved:
            if int(saved["schema"]) != 1:
                raise ValueError("unsupported GP artifact")
            self.options = json.loads(str(saved["options"]))
            self.fit(saved["features"], saved["targets"])
