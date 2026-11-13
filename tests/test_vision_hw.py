from dataclasses import replace
import cv2
import numpy as np
import pytest
from rearm.sim.sim_camera import SimCamera
from rearm.vision.board import BoardLocator
from rearm.vision.laser_spot import LaserSpotDetector
from rearm.vision.targets import TargetDetector
from rearm.vision.undistort import Undistorter
from rearm.vision.camera import OpenCVCamera
from rearm.hw.real_arm import RealArm
from rearm.hw.servo import ServoDriver
from rearm.hw.laser import LaserDriver


def test_synthetic_perspective_board_spot(config):
    camera = SimCamera(config)
    warp = cv2.getPerspectiveTransform(np.float32([[0,0],[999,0],[999,759],[0,759]]),
                                      np.float32([[20,25],[970,10],[990,735],[10,750]]))
    off, on = camera.render(perspective=warp), camera.render([31.35,-20.7],perspective=warp)
    locator = BoardLocator(config)
    matrix = locator.locate(off)
    point = LaserSpotDetector(config).detect(off, on)
    np.testing.assert_allclose(locator.to_board(point,matrix), [31.35,-20.7], atol=0.6)
    assert LaserSpotDetector(config).detect(off, off) is None
    with pytest.raises(ValueError):
        locator.locate(np.full_like(off, 255))


def test_circular_targets_and_camera_lifecycle(config):
    camera = SimCamera(config)
    targets = [[-70,20],[65,-45],[0,70]]
    frame = camera.render(targets=targets)
    points = TargetDetector(config).detect(frame)
    assert len(points) == len(targets)
    for expected in targets:
        assert np.min(np.linalg.norm(points-camera.pixel(expected),axis=1)) < 0.5
    assert camera.read().shape == frame.shape
    camera.close()
    with pytest.raises(OSError):
        camera.read()


def test_undistortion_nonzero(config):
    config = replace(config,camera=config.camera | {"distortion":[0.1,-0.02,0.001,-0.002,0]})
    undistort = Undistorter(config)
    xyz = np.array([[-0.3,-0.2,1],[0.25,0.12,1]],dtype=float)
    distorted,_ = cv2.projectPoints(xyz,np.zeros(3),np.zeros(3),undistort.matrix,undistort.distortion)
    expected = xyz[:,:2]*1000+np.array([500,380])
    np.testing.assert_allclose(undistort.points(distorted.reshape(-1,2)),expected,atol=1e-5)
    assert undistort.image(SimCamera(config).read()).shape == (760,1000,3)


def test_camera_adapter_with_synthetic_capture(config, monkeypatch):
    frame = SimCamera(config).read()
    class Capture:
        def isOpened(self): return True
        def read(self): return True, frame
        def release(self): pass
    monkeypatch.setattr(cv2,"VideoCapture",lambda _: Capture())
    camera=OpenCVCamera("simulated")
    np.testing.assert_equal(camera.read(),frame)
    camera.close()


def test_hardware_skeleton_fails_closed():
    with pytest.raises(NotImplementedError): RealArm().move_to(np.zeros(3),1)
    with pytest.raises(NotImplementedError): RealArm().read_state()
    with pytest.raises(NotImplementedError): RealArm().laser(True)
    with pytest.raises(NotImplementedError): RealArm().observe_spot()
    with pytest.raises(NotImplementedError): ServoDriver("unused",115200).move_to(np.zeros(3),1)
    with pytest.raises(NotImplementedError): ServoDriver("unused",115200).read_state()
    with pytest.raises(NotImplementedError): LaserDriver("unused").set_enabled(True)
