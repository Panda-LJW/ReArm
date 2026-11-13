import json
import pytest
from rearm.app import build_app
from rearm.sim.sim_camera import SimCamera
from rearm.ui.server import create_server
from tests.test_ui_architecture import request


def healed_controller(config, tmp_path):
    controller = build_app(config, tmp_path)
    controller.command("inject", {"kind": "j1", "amount": 1})
    controller.command("selfcheck", {})
    assert controller.store.head().id != "v0001"
    return controller


def test_switch_requires_fresh_preview_and_matching_confirmation(config, tmp_path):
    controller = healed_controller(config, tmp_path)
    healed = controller.store.head().id
    with pytest.raises(ValueError, match="preview"):
        controller.command("switch", {"version_id": "v0001", "confirm": "v0001"})
    preview = controller.preview("v0001")
    # The arm is still damaged, so the undamaged initial model must fail the preview.
    assert not preview["passed"] and preview["candidate_median"] > preview["current_median"]
    assert controller.store.head().id == healed, "preview must not switch"
    with pytest.raises(ValueError, match="force"):
        controller.command("switch", {"version_id": "v0001", "confirm": "v0001"})
    with pytest.raises(ValueError, match="confirmation"):
        controller.command("switch", {"version_id": "v0001", "confirm": "v0002", "force": True})
    controller.command("switch", {"version_id": "v0001", "confirm": "v0001", "force": True})
    assert controller.store.head().id == "v0001" and controller.last_switch["forced"]
    # Undo within the window needs no new preview.
    controller.command("switch", {"version_id": healed, "confirm": healed})
    assert controller.store.head().id == healed and controller.last_switch["undo"]
    assert controller.snapshot()["stats"]["manual_switches"] == 2


def test_passing_preview_allows_switch_and_raw_rollback_is_not_remote(config, tmp_path):
    controller = healed_controller(config, tmp_path)
    healed = controller.store.head().id
    controller.command("inject", {"kind": "restore"})
    assert controller.preview("v0001")["passed"]
    controller.command("switch", {"version_id": "v0001", "confirm": "v0001"})
    assert controller.store.head().id == "v0001"
    with pytest.raises(ValueError, match="unknown command"):
        controller.command("rollback", {"version_id": healed})


def test_panel_endpoints_camera_fault_codes_and_event_feed(config, tmp_path):
    controller = build_app(config, tmp_path)
    initial = controller.snapshot() | {"history_limit": config.thresholds["ui"]["history"], "camera": {"width": 1}}
    server = create_server(controller, controller.bus, initial, SimCamera(config), config.thresholds["ui"]["camera_jpeg_quality"])
    status, body = request(server, "/api/camera.jpg")
    assert status == 200 and body[:2] == b"\xff\xd8"
    status, body = request(server, "/api/fault-codes")
    assert status == 200 and "H1" in body.decode()
    assert request(server, "/api/command/inject", "POST", {"kind": "j1", "amount": 1})[0] == 200
    assert request(server, "/api/command/selfcheck", "POST", {})[0] == 200
    view = json.loads(request(server, "/api/state")[1])
    kinds = [event["kind"] for event in view["events"]]
    assert "damage_injected" in kinds and "alarm" in kinds and "version_committed" in kinds
    assert view["camera"] == {"width": 1}, "static display settings survive snapshots"
    assert view["stats"]["recoveries"] == 1
    no_camera = create_server(controller, controller.bus, initial)
    assert request(no_camera, "/api/camera.jpg")[0] == 404
