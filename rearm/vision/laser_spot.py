import cv2
import numpy as np
from rearm.types import Settings


class LaserSpotDetector:
    def __init__(self, config: Settings):
        self.options = config.camera

    def detect(self, off: np.ndarray, on: np.ndarray) -> np.ndarray | None:
        if off.shape != on.shape:
            raise ValueError("laser frame pair shape mismatch")
        # Positive red-channel difference suppresses unchanged red objects and texture.
        before = off[..., 2] if off.ndim == 3 else off
        after = on[..., 2] if on.ndim == 3 else on
        delta = np.maximum(after.astype(float)-before.astype(float), 0)
        mask = (delta >= self.options["spot_threshold"]).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        candidates = [i for i in range(1, count) if self.options["spot_min_pixels"] <= stats[i, cv2.CC_STAT_AREA] <= self.options["spot_max_pixels"]]
        if not candidates:
            return None
        best = max(candidates, key=lambda i: float(delta[labels == i].sum()))
        ys, xs = np.nonzero(labels == best)
        weights = delta[ys, xs]
        return np.array([np.average(xs, weights=weights), np.average(ys, weights=weights)])
