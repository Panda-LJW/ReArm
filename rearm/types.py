"""Only shared data definitions live here. Angles: degrees; distances: mm."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Params:
    delta1: float
    delta2: float
    delta3: float
    h: float
    L1: float
    L2: float
    e: float
    beta: float
    gamma: float
    x_b: float
    y_b: float
    psi_b: float

    def updated(self, values: dict[str, float]) -> Params:
        return Params(**(asdict(self) | values))

    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in fields(self))


@dataclass(frozen=True)
class Settings:
    nominal: Params
    bounds: dict[str, tuple[float, float]]
    joint_limits: np.ndarray
    board_mm: np.ndarray
    min_downward: float
    thresholds: dict[str, Any]
    sim: dict[str, Any]
    camera: dict[str, Any]


@dataclass(frozen=True)
class Pose:
    q: np.ndarray
    condition: float | None = None


@dataclass(frozen=True)
class ArmState:
    q: np.ndarray
    direction: np.ndarray
    load: float
    temperature: float
    voltage: float

    def features(self) -> np.ndarray:
        return np.r_[self.q, self.direction, self.load, self.temperature]


@dataclass
class Shot:
    timestamp: float
    q: list[float]
    direction: list[float]
    load: float
    temperature: float
    voltage: float
    predicted: list[float]
    observed: list[float] | None
    residual: list[float] | None
    uncertainty: list[float]
    version_id: str
    anomalous: bool
    role: str = "task"

    def features(self) -> np.ndarray:
        return np.array([*self.q, *self.direction, self.load, self.temperature])


@dataclass(frozen=True)
class FitResult:
    params: Params
    rms: float
    sse: float
    success: bool
    free: tuple[str, ...]


@dataclass(frozen=True)
class Hypothesis:
    name: str
    groups: tuple[str, ...]
    fit: FitResult
    bic: float


@dataclass(frozen=True)
class Diagnosis:
    best: Hypothesis
    ranked: tuple[Hypothesis, ...]
    deltas: dict[str, float]
    gear_steps: dict[str, int]
    changes: tuple[str, ...]
    proposed: FitResult
    ambiguous: tuple[str, ...] = ()


@dataclass(frozen=True)
class GuardReport:
    accepted: bool
    candidate_median: float
    old_median: float
    reduction: float
    in_bounds: bool
    reasons: tuple[str, ...]
    shots: int


@dataclass(frozen=True)
class Version:
    id: str
    params: Params
    residual_id: str
    accepted: bool
    meta: dict[str, Any]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Event:
    kind: str
    timestamp: float
    data: dict[str, Any]


class State(str, Enum):
    NORMAL = "正常"
    ALARM = "发现异常"
    RECOGNIZE = "认旧状态"
    DIAGNOSE = "诊断"
    CALIBRATE = "校准"
    GUARD = "护栏"
    REJECTED = "已拒绝"
    TRAINING = "重训残差"


@dataclass(frozen=True)
class TrainingSet:
    features: np.ndarray
    targets: np.ndarray
    timestamps: np.ndarray


@dataclass(frozen=True)
class TrainingReport:
    accepted: bool
    geometry_median: float
    old_median: float
    new_median: float
    train_count: int
    holdout_count: int


@dataclass(frozen=True)
class Damage:
    kind: str
    amount: float = 0.0
    components: tuple[Damage, ...] = ()


def jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Enum):
        return value.value
    return value
