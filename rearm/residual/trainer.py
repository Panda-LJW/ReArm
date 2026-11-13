import numpy as np
from rearm.interfaces import ResidualModel
from rearm.types import Settings, TrainingReport, TrainingSet


class TemporalTrainer:
    def __init__(self, config: Settings):
        self.options = config.thresholds["residual"]

    def train(self, data: TrainingSet, old: ResidualModel, candidate: ResidualModel) -> TrainingReport:
        if len(data.features) < self.options["min_samples"]:
            raise ValueError("not enough clean samples to train")
        order = np.argsort(data.timestamps, kind="stable")
        count = int(len(order) * (1 - self.options["holdout_fraction"]))
        train, holdout = order[:count], order[count:]
        if data.timestamps[train[-1]] >= data.timestamps[holdout[0]]:
            raise ValueError("temporal holdout must be strictly after all training data")
        candidate.fit(data.features[train], data.targets[train])
        target = data.targets[holdout]
        old_pred, _ = old.predict(data.features[holdout])
        new_pred, _ = candidate.predict(data.features[holdout])
        geom = float(np.median(np.linalg.norm(target, axis=1)))
        old_error = float(np.median(np.linalg.norm(target-old_pred, axis=1)))
        new_error = float(np.median(np.linalg.norm(target-new_pred, axis=1)))
        accepted = new_error < old_error - self.options["min_improvement_mm"]
        # Do not refit on holdout after selection: deployed artifact is the one validated.
        return TrainingReport(accepted, geom, old_error, new_error, len(train), len(holdout))
