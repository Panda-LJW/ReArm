import cv2
import numpy as np
from rearm.types import Settings


class BoardLocator:
    def __init__(self, config: Settings):
        self.options = config.camera
        dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, self.options["dictionary"]))
        self.detector = cv2.aruco.ArucoDetector(dictionary)

    def locate(self, image: np.ndarray) -> np.ndarray:
        corners, ids, _ = self.detector.detectMarkers(image)
        if ids is None:
            raise ValueError("board markers missing")
        found = {int(i): c.reshape(4, 2) for i, c in zip(ids.ravel(), corners)}
        if not all(i in found for i in self.options["marker_ids"]):
            raise ValueError("all four board markers required")
        half = self.options["marker_size_mm"] / 2
        offsets = np.array([[-half, half], [half, half], [half, -half], [-half, -half]])
        pixels = np.concatenate([found[i] for i in self.options["marker_ids"]])
        board = np.concatenate([np.asarray(center)+offsets for center in self.options["marker_centers_mm"]])
        matrix, _ = cv2.findHomography(pixels, board, method=0)
        if matrix is None or not np.isfinite(matrix).all():
            raise ValueError("degenerate board homography")
        return matrix

    def to_board(self, points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        points = np.asarray(points, dtype=float)
        shape = points.shape
        return cv2.perspectiveTransform(points.reshape(-1, 1, 2), matrix).reshape(shape)
