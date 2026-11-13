import cv2
import numpy as np
from rearm.types import Settings


class TargetDetector:
    def __init__(self, config: Settings):
        self.options = config.camera

    def detect(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        _, mask = cv2.threshold(gray, self.options["target_threshold"], 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        points = []
        for contour in contours:
            area, perimeter = cv2.contourArea(contour), cv2.arcLength(contour, True)
            if not self.options["target_min_area"] <= area <= self.options["target_max_area"] or perimeter == 0:
                continue
            if 4*np.pi*area/perimeter**2 < self.options["target_circularity"]:
                continue
            moments = cv2.moments(contour)
            points.append([moments["m10"]/moments["m00"], moments["m01"]/moments["m00"]])
        return np.asarray(points, dtype=float).reshape(-1, 2)
