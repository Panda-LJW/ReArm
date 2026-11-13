from dataclasses import replace
import numpy as np
import pytest
from rearm.app import build_app
from rearm.residual.gp import GPResidual
from rearm.residual.zero import ZeroResidual
from rearm.residual.dataset import ResidualDataset
from rearm.residual.trainer import TemporalTrainer
from rearm.types import State, TrainingSet


def test_gp_cap_uncertainty_and_persistence(config, tmp_path):
    rng = np.random.default_rng(7)
    x = rng.normal(size=(60, 8))
    y = np.column_stack([x[:, 0], 2*x[:, 1]])
    gp = GPResidual(config)
    gp.fit(x, y)
    path = tmp_path / "gp.npz"
    gp.save(path)
    restored = GPResidual(config)
    restored.load(path)
    mean, std = gp.predict(x)
    np.testing.assert_equal(mean, restored.predict(x)[0])
    assert np.all(std >= 0)
    assert np.all(np.linalg.norm(mean, axis=1) <= config.thresholds["residual"]["cap_mm"] + 1e-10)
    assert np.mean(gp.predict(np.full((1, 8), 1000))[1]) > np.mean(std)


def test_temporal_training_and_exclusion(config, geometry, tmp_path):
    config = replace(config, sim=config.sim | {"nongeometric": True})
    app = build_app(config, tmp_path)
    for i in range(100):
        app.shoot(app.probe_pool[i % len(app.probe_pool)])
    data = ResidualDataset(config, geometry).build(app.shot_log.read(), config.nominal, {app.store.head().id})
    report = TemporalTrainer(config).train(data, ZeroResidual(), GPResidual(config))
    assert report.accepted
    assert report.new_median < report.geometry_median
    shots = app.shot_log.read()
    shots[0].anomalous = True
    shots[1].role = "guard"
    assert len(ResidualDataset(config, geometry).build(shots, config.nominal, {app.store.head().id}).features) == len(shots)-2


def test_closed_loop_recognition_and_recovery(config, tmp_path):
    app = build_app(config, tmp_path)
    initial = app.store.head().id
    app.command("inject", {"kind": "j1", "amount": 1})
    app.command("selfcheck", {})
    damaged = app.store.head().id
    assert damaged != initial
    assert app.state == State.NORMAL
    assert app.last_recovery_shots <= 20
    assert app.last_guard.accepted
    meta = app.store.head().meta
    assert not any(np.allclose(a,b) for a in meta["fit_q"] for b in meta["holdout_q"])
    app.command("inject", {"kind": "restore"})
    app.command("selfcheck", {})
    assert app.store.head().id == initial
    assert app.last_recovery_shots == 3
    app.command("inject", {"kind": "j1", "amount": 1})
    app.command("selfcheck", {})
    assert app.store.head().id == damaged
    assert app.last_recovery_shots == 3
    app.rollback(initial)
    assert app.store.head().id == initial


def test_failed_training_restores_state(config, tmp_path):
    app = build_app(config, tmp_path)
    with pytest.raises(ValueError, match="not enough"):
        app.retrain()
    assert app.state == State.NORMAL


def test_zero_save_load(tmp_path):
    zero = ZeroResidual()
    zero.save(tmp_path / "zero.json")
    zero.load(tmp_path / "zero.json")
    np.testing.assert_equal(zero.predict(np.zeros(8))[0], [0, 0])


def test_retraining_without_improvement_keeps_head(config,tmp_path):
    config=replace(config,sim=config.sim|{"noise_mm":0,"nongeometric":False})
    app=build_app(config,tmp_path)
    original=app.store.head().id
    for q in app.probe_pool:
        app.shoot(q)
    report=app.retrain()
    assert report.old_median==report.new_median==0
    assert not report.accepted
    assert app.store.head().id==original
    assert list((tmp_path/"residuals").glob("*.npz"))==[]
