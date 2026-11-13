import json
from pathlib import Path
import numpy as np


class ZeroResidual:
    def predict(self, feats: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        shape = np.asarray(feats).shape[:-1] + (2,)
        return np.zeros(shape), np.zeros(shape)

    def fit(self, feats: np.ndarray, targets: np.ndarray) -> None:
        pass

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({"kind": "zero"}))

    def load(self, path: str | Path) -> None:
        if json.loads(Path(path).read_text()).get("kind") != "zero":
            raise ValueError("not a ZeroResidual artifact")
