from dataclasses import replace
import numpy as np
import pytest
from rearm.model.ik import NumericalIK
from rearm.model.pose_pool import PosePool
from rearm.model.self_model import SelfModel
from rearm.sim.sim_arm import SimArm
from rearm.sim.damage import damaged_params
from rearm.types import Damage


def test_ray_and_validity(config, geometry, pool):
    origin, ray = geometry.ray(config.nominal, pool)
    np.testing.assert_allclose(np.linalg.norm(ray, axis=1), 1)
    assert geometry.valid(config.nominal, pool).all()
    assert not geometry.valid(config.nominal, [0, 0, 0])
    assert not geometry.valid(config.nominal, [100, 40, -100])
    assert (origin[:, 2] >= 0).all()


def test_pose_determinism_and_jacobian(config, geometry, pool):
    np.testing.assert_equal(pool, PosePool(config, geometry).generate(config.nominal))
    jac = geometry.jacobian(config.nominal, pool[:5], ("x_b", "y_b"))
    np.testing.assert_allclose(jac, np.broadcast_to(np.eye(2), jac.shape), atol=1e-7)


def test_ik_round_trip(config, geometry, pool):
    solver = NumericalIK(config, geometry)
    for q in pool[:8]:
        target = geometry.predict(config.nominal, q)
        solved = solver.solve(target, config.nominal, pool)
        np.testing.assert_allclose(geometry.predict(config.nominal, solved), target, atol=0.1)
    with pytest.raises(ValueError):
        solver.solve([999, 0], config.nominal, pool)


def test_sim_noise_direction_damage(config, geometry, pool):
    a, b = SimArm(config, geometry), SimArm(config, geometry)
    for arm in (a, b):
        assert arm.observe_spot() is None
        arm.move_to(pool[0], 30)
        arm.laser(True)
    np.testing.assert_equal(a.observe_spot(), b.observe_spot())
    assert a.read_state().temperature > config.sim["ambient_c"]
    p = damaged_params(config.nominal, Damage("combination", components=(Damage("j1", 1), Damage("extension", 20))), config)
    assert (p.delta1, p.e) == (15, 20)
    with pytest.raises(ValueError):
        damaged_params(p, Damage("j1", 2), config)
    with pytest.raises(ValueError):
        a.move_to([0, 999, 0], 30)


def test_structural_yaw_ambiguity(config, geometry, pool):
    np.testing.assert_allclose(geometry.predict(config.nominal.updated({"delta1": 10}), pool),
                               geometry.predict(config.nominal.updated({"psi_b": 10}), pool))
