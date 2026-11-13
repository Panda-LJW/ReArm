import cv2
import numpy as np
from rearm.types import Settings


class Undistorter:
    def __init__(self, config: Settings):
        self.matrix = np.asarray(config.camera["matrix"], dtype=float)
        self.distortion = np.asarray(config.camera["distortion"], dtype=float)

    def image(self, frame: np.ndarray) -> np.ndarray:
        return cv2.undistort(frame, self.matrix, self.distortion)

    def points(self, points: np.ndarray) -> np.ndarray:
        points = np.asarray(points, dtype=float)
        return cv2.undistortPoints(points.reshape(-1, 1, 2), self.matrix, self.distortion, P=self.matrix).reshape(points.shape)
