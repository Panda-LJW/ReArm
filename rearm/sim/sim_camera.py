import cv2
import numpy as np
from rearm.types import Settings


class SimCamera:
    """Synthetic marked board. Projection may be warped without exposing ground truth to vision."""
    def __init__(self, config: Settings):
        self.options = config.camera
        self.board_mm = config.board_mm
        self.spot = None
        self.closed = False

    def pixel(self, xy):
        return np.array([self.options["width"]/2, self.options["height"]/2]) + np.asarray(xy)*np.array([1,-1])*self.options["pixels_per_mm"]

    def render(self, spot=None, targets=(), perspective=None):
        c = self.options
        frame = np.full((c["height"], c["width"], 3), 180, dtype=np.uint8)
        dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, c["dictionary"]))
        size = c["marker_pixels"]
        for marker_id, center in zip(c["marker_ids"], c["marker_centers_mm"]):
            marker = cv2.aruco.generateImageMarker(dictionary, marker_id, size)
            x,y = np.rint(self.pixel(center)-size/2).astype(int)
            frame[y:y+size, x:x+size] = marker[..., None]
        for target in targets:
            cv2.circle(frame, tuple(np.rint(self.pixel(target)).astype(int)), c["target_radius_px"], (20,20,20), -1)
        if spot is not None:
            x,y = self.pixel(spot)
            yy,xx = np.indices(frame.shape[:2])
            intensity = (255-180)*np.exp(-((xx-x)**2+(yy-y)**2)/(2*c["spot_sigma_px"]**2))
            frame[..., 2] = np.clip(frame[..., 2].astype(float)+intensity, 0, 255).astype(np.uint8)
        if perspective is not None:
            frame = cv2.warpPerspective(frame, perspective, (c["width"],c["height"]), borderValue=(180,180,180))
        return frame

    def read(self):
        if self.closed:
            raise OSError("camera closed")
        return self.render(self.spot)

    def close(self):
        self.closed = True
