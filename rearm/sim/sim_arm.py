import numpy as np
from rearm.interfaces import Geometry
from rearm.types import ArmState, Params, Settings


class SimArm:
    """Hidden physical state is never passed to fitting or diagnosis."""
    def __init__(self, config: Settings, geometry: Geometry, params: Params | None = None, seed: int | None = None):
        self.config, self.geometry = config, geometry
        self.true_params = params or config.nominal
        self.rng = np.random.default_rng(config.sim["seed"] if seed is None else seed)
        self.q = np.array(config.thresholds["task"]["initial_q"], dtype=float)
        self.direction = np.zeros(3)
        self.shots = 0
        self.laser_on = False
        self.load = config.sim["load"]
        self.looseness = config.sim["looseness_mm"]

    def move_to(self, q: np.ndarray, speed: float) -> None:
        q = np.asarray(q, dtype=float)
        limits = self.config.joint_limits
        if q.shape != (3,) or not np.isfinite(q).all() or np.any(q < limits[:, 0]) or np.any(q > limits[:, 1]) or speed <= 0:
            raise ValueError("invalid movement")
        self.direction = np.sign(q - self.q)
        self.q = q.copy()

    def read_state(self) -> ArmState:
        c = self.config.sim
        return ArmState(self.q.copy(), self.direction.copy(), self.load,
                        c["ambient_c"] + min(self.shots * c["heat_c_per_shot"], c["max_heat_c"]), c["voltage"])

    def laser(self, on: bool) -> None:
        self.laser_on = bool(on)

    def observe_spot(self) -> np.ndarray | None:
        if not self.laser_on:
            return None
        state = self.read_state()
        self.shots += 1
        if not self.geometry.valid(self.true_params, self.q):
            return None
        spot = self.geometry.predict(self.true_params, self.q).copy()
        c = self.config.sim
        if c["nongeometric"]:
            # Backlash is signed by approach; sag depends on reach and live load.
            theta2 = np.deg2rad(self.q[1] + self.true_params.delta2)
            total = theta2 + np.deg2rad(self.q[2] + self.true_params.delta3)
            reach = (self.true_params.L1 * np.cos(theta2) + (self.true_params.L2 + self.true_params.e)
                     * np.cos(total)) / (self.true_params.L1 + self.true_params.L2 + self.true_params.e)
            spot += np.array([c["backlash_mm"] * state.direction[0],
                c["backlash_mm"] * state.direction[1] + c["sag_mm"] * self.load * (1 + reach)
                + c["drift_mm_per_degree"] * (state.temperature - c["ambient_c"])])
        if self.looseness:
            spot += self.rng.normal(0, self.looseness, 2)
        spot += self.rng.normal(0, c["noise_mm"], 2)
        return spot if np.all(np.abs(spot) <= self.config.board_mm / 2) else None
