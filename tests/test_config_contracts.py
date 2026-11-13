from dataclasses import replace
from pathlib import Path
import shutil
import numpy as np
import pytest
import yaml
from rearm.app import build_app
from rearm.config import load_config
from rearm.model.pose_pool import PosePool
from rearm.types import jsonable


def test_acceptance_thresholds_unchanged(config):
    assert config.thresholds["detector"]=={"window":3,"alarm_mm":6.0}
    assert config.thresholds["guard"]["median_mm"]==3
    assert config.thresholds["guard"]["reduction"]==0.7
    assert config.thresholds["recognizer"]["probes"]==3
    assert config.thresholds["recognizer"]["rms_mm"]==3
    assert config.thresholds["recognizer"]["runner_up_ratio"]==0.5
    assert config.thresholds["eval"]["trials"]==100
    assert config.thresholds["eval"]["diagnosis_rate"]==0.95
    assert config.thresholds["eval"]["recovery_shots"]==20


@pytest.mark.parametrize("section,key,value",[("detector","window",0),("guard","reduction",1.1),
    ("residual","feature_scale",[1]),("residual","noise_mm",float('nan')),("fit","max_nfev",2.5)])
def test_config_rejects_invalid_thresholds(tmp_path,section,key,value):
    root=Path(__file__).resolve().parents[1]
    shutil.copytree(root/"config",tmp_path/"config")
    path=tmp_path/"config/thresholds.yaml"
    data=yaml.safe_load(path.read_text());data[section][key]=value;path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError): load_config(tmp_path/"config")


def test_extension_unobservable_on_axis(config,geometry,pool):
    for extension in config.sim["extensions_mm"]:
        np.testing.assert_allclose(geometry.predict(config.nominal.updated({"e":extension}),pool),
                                   geometry.predict(config.nominal,pool),atol=1e-10)
    off_axis=config.nominal.updated({"gamma":3})
    assert np.max(np.linalg.norm(geometry.predict(off_axis.updated({"e":40}),pool)-geometry.predict(off_axis,pool),axis=1))>0


def test_sim_non_geometric_channels_and_disable(config,geometry,pool):
    from rearm.sim.sim_arm import SimArm
    clean=replace(config,sim=config.sim|{"noise_mm":0,"nongeometric":False})
    arm=SimArm(clean,geometry);arm.move_to(pool[0],30);arm.laser(True)
    np.testing.assert_equal(arm.observe_spot(),geometry.predict(clean.nominal,pool[0]))
    active=replace(clean,sim=clean.sim|{"nongeometric":True})
    other=SimArm(active,geometry);other.move_to(pool[0],30);other.laser(True)
    assert not np.allclose(other.observe_spot(),geometry.predict(clean.nominal,pool[0]))


def test_separate_geometry_and_residual_rollbacks(config,tmp_path):
    app=build_app(config,tmp_path)
    first=app.store.head()
    second_id=app.store.commit(first.params.updated({"x_b":10}),"r9999",{})
    app.store.checkout(first.id,"geometry")
    assert app.store.head().params==first.params and app.store.head().residual_id=="r9999"
    app.store.checkout(first.id,"residual")
    assert app.store.head().params==first.params and app.store.head().residual_id=="zero"
    assert not app.arm.laser_on


def test_baseline_all_parameter_fit(config,tmp_path):
    truth=config.nominal.updated({k:getattr(config.nominal,k)+v for k,v in config.thresholds["eval"]["baseline_offsets"].items()})
    app=build_app(config,tmp_path,true_params=truth)
    report=app.baseline()
    assert report.accepted and report.candidate_median<=3
    assert app.store.head().residual_id=="zero"
    assert isinstance(jsonable(report),dict)
