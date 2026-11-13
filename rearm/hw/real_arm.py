import numpy as np
from rearm.types import ArmState


class RealArm:
    """ArmIO-compatible fail-closed skeleton; no unverified real hardware control."""
    def move_to(self, q: np.ndarray, speed: float) -> None:
        raise NotImplementedError("TODO: inject confirmed servo adapter")

    def read_state(self) -> ArmState:
        raise NotImplementedError("TODO: read hardware telemetry")

    def laser(self, on: bool) -> None:
        raise NotImplementedError("TODO: inject laser driver")

    def observe_spot(self) -> np.ndarray | None:
        raise NotImplementedError("TODO: capture off/on frames, undistort, locate board, measure laser centroid")
