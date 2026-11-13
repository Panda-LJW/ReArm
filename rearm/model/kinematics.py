import numpy as np
from rearm.types import Params, Settings


class Kinematics:
    def __init__(self, config: Settings):
        self.config = config

    def ray(self, params: Params, q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        q = np.asarray(q, dtype=float)
        theta = np.deg2rad(q + np.array([params.delta1, params.delta2, params.delta3]))
        phi = theta[..., 0] + np.deg2rad(params.psi_b)
        theta2, total = theta[..., 1], theta[..., 1] + theta[..., 2]
        radius = params.L1 * np.cos(theta2) + (params.L2 + params.e) * np.cos(total)
        height = params.h + params.L1 * np.sin(theta2) + (params.L2 + params.e) * np.sin(total)
        radial = np.stack([np.sin(phi), np.cos(phi), np.zeros_like(phi)], axis=-1)
        tangent = np.stack([np.cos(phi), -np.sin(phi), np.zeros_like(phi)], axis=-1)
        origin = radius[..., None] * radial + np.array([params.x_b, params.y_b, 0])
        origin[..., 2] = height
        alpha, gamma = total + np.deg2rad(params.beta), np.deg2rad(params.gamma)
        direction = np.cos(gamma) * np.cos(alpha)[..., None] * radial + np.sin(gamma) * tangent
        direction[..., 2] = np.cos(gamma) * np.sin(alpha)
        return origin, direction

    def predict(self, params: Params, q: np.ndarray) -> np.ndarray:
        origin, direction = self.ray(params, q)
        epsilon = self.config.thresholds["numeric"]["epsilon"]
        dz = direction[..., 2]
        safe_dz = np.where(np.abs(dz) < epsilon, np.where(dz < 0, -epsilon, epsilon), dz)
        return origin[..., :2] - (origin[..., 2] / safe_dz)[..., None] * direction[..., :2]

    def valid(self, params: Params, q: np.ndarray) -> np.ndarray:
        q = np.asarray(q)
        origin, direction = self.ray(params, q)
        point = self.predict(params, q)
        limits = self.config.joint_limits
        return (np.all(np.isfinite(q), axis=-1) & np.all((q >= limits[:, 0]) & (q <= limits[:, 1]), axis=-1)
                & (direction[..., 2] <= -self.config.min_downward) & (origin[..., 2] >= 0)
                & np.all(np.abs(point) <= self.config.board_mm / 2, axis=-1))

    def jacobian(self, params: Params, q: np.ndarray, names: tuple[str, ...]) -> np.ndarray:
        step = self.config.thresholds["pool"]["jacobian_step"]
        return np.stack([(self.predict(params.updated({k: getattr(params, k) + step}), q)
                          - self.predict(params.updated({k: getattr(params, k) - step}), q)) / (2 * step)
                         for k in names], axis=-1)
