from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from rearm.config import load_config
from rearm.model.kinematics import Kinematics
from rearm.model.pose_pool import PosePool


@pytest.fixture
def config():
    return load_config(Path(__file__).resolve().parents[1] / "config")


@pytest.fixture
def geometry(config):
    return Kinematics(config)


@pytest.fixture
def pool(config, geometry):
    return PosePool(config, geometry).generate(config.nominal)
