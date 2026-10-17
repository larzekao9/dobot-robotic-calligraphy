import json
import uuid
from pathlib import Path
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.main import app
from app.services.jobs import JobRunner, get_runner, make_driver
from app.services.robot.base import Command
from app.services.robot.config import RobotConfig, load_config
from app.services.robot.dobot_driver import DobotDriver, Feedback
from app.services.robot.mock_driver import MockDriver
from tests.conftest import ADMIN

H = ADMIN


@pytest.fixture(autouse=True)
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "robot_config.json"
    monkeypatch.setattr(settings, "robot_config_path", str(path))
    return path


def use_dobot(api: TestClient) -> None:
    body = RobotConfig(driver="dobot", ip="10.0.0.9").model_dump()
    assert api.put("/api/robot/config", json=body, headers=H).status_code == 200


def fake_feedback(monkeypatch: pytest.MonkeyPatch, fb: Feedback | Exception) -> None:
    def read(ip: str) -> Feedback:
        if isinstance(fb, Exception):
            raise fb
        return fb

    monkeypatch.setattr("app.routers.robot.read_feedback", read)


def test_robot_routes_require_the_admin_token(api: TestClient) -> None:
    for method, path in (("get", "/config"), ("get", "/status"), ("post", "/capture/origin")):
        r = getattr(api, method)(f"/api/robot{path}")
        assert (r.status_code, r.json()["error"]["code"]) == (401, "unauthorized")


def test_default_config_is_safe(api: TestClient) -> None:
    cfg = api.get("/api/robot/config", headers=H).json()
    assert cfg["driver"] == "mock" and cfg["pencil_mode"] is True
    assert cfg["calibrated"] is False and cfg["ip"] == "192.168.1.6"
    assert (cfg["speed_factor"], cfg["speed_l"], cfg["accel_l"], cfg["cp"]) == (20, 30, 30, 0)


def test_config_is_saved_and_validated(api: TestClient, config_file: Path) -> None:
    body = {
        **api.get("/api/robot/config", headers=H).json(),
        "speed_factor": 40,
        "pencil_mode": False,
    }
    body.pop("calibrated")
    assert api.put("/api/robot/config", json=body, headers=H).json()["speed_factor"] == 40
    assert json.loads(config_file.read_text())["pencil_mode"] is False
    assert load_config().speed_factor == 40
    for bad in ({"speed_factor": 0}, {"press_depth_mm": 50}, {"ip": "  "}, {"origin": [1, 2]}):
        r = api.put("/api/robot/config", json={**body, **bad}, headers=H)
        assert (r.status_code, r.json()["error"]["code"]) == (422, "validation_error"), bad


def test_status_for_the_simulator_and_for_the_robot(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert api.get("/api/robot/status", headers=H).json()["driver"] == "mock"
    use_dobot(api)
    fake_feedback(monkeypatch, Feedback(5, (300.0, 10.0, 25.0, 0.0), False, True, False))
    s = api.get("/api/robot/status", headers=H).json()
    assert (s["reachable"], s["mode"], s["mode_name"], s["pose"]) == (
        True, 5, "Habilitado y libre", [300.0, 10.0, 25.0, 0.0]
    )  # fmt: skip
    fake_feedback(monkeypatch, ConnectionRefusedError("no route"))
    s = api.get("/api/robot/status", headers=H).json()
    assert s["reachable"] is False and "10.0.0.9" in s["error"]


def test_capture_points_until_calibrated(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert (
        api.post("/api/robot/capture/origin", headers=H).json()["error"]["code"]
        == "driver_not_dobot"
    )
    use_dobot(api)
    fake_feedback(monkeypatch, ConnectionRefusedError("down"))
    r = api.post("/api/robot/capture/origin", headers=H)
    assert (r.status_code, r.json()["error"]["code"]) == (502, "robot_unreachable")

    poses = {
        "origin": (300.0, -100.0, 20.0),
        "x_axis": (300.0, 110.0, 20.0),
        "y_axis": (3.0, -100.0, 20.0),
    }
    for i, (name, (x, y, z)) in enumerate(poses.items()):
        fake_feedback(monkeypatch, Feedback(5, (x, y, z, 0.0), False, True, False))
        cfg = api.post(f"/api/robot/capture/{name}", headers=H).json()
        assert cfg[name] == [x, y, z]
        assert cfg["calibrated"] is (i == 2)
    assert api.post("/api/robot/capture/ink", headers=H).json()["ink"] == [3.0, -100.0, 20.0]
    assert api.post("/api/robot/capture/nope", headers=H).status_code == 422


def test_factory_follows_the_saved_driver(api: TestClient) -> None:
    assert isinstance(make_driver(), MockDriver)
    use_dobot(api)
    assert isinstance(make_driver(), DobotDriver)


class Recorder(MockDriver):
    paths: ClassVar[list[list[Command]]] = []

    def execute(self, path, on_progress):  # type: ignore[no-untyped-def]
        Recorder.paths.append(path)
        super().execute(path, on_progress)


def test_dry_run_keeps_the_pen_up(api: TestClient, engine: Engine) -> None:
    runner = JobRunner(sessionmaker(bind=engine), lambda: Recorder(time_scale=0))
    app.dependency_overrides[get_runner] = lambda: runner
    rid = api.post("/api/names/convert", json={"name": "Carlos"}).json()["request_id"]
    job = api.post("/api/jobs", json={"request_id": rid, "script": "zh"}).json()
    full = [c["op"] for c in job["path"]]
    assert "down" in full and "dip" in full

    r = api.post(f"/api/jobs/{job['id']}/start?dry_run=true")
    assert r.status_code == 200
    runner.wait(uuid.UUID(job["id"]))
    ran = [c["op"] for c in Recorder.paths[-1]]
    assert set(ran) == {"move"} and len(ran) == full.count("move") + full.count("line")
    assert api.get(f"/api/jobs/{job['id']}").json()["status"] == "done"


class FakeRobot:
    """Robot falso para los endpoints: guarda los comandos y cambia de modo como el real."""

    def __init__(self, mode: int = 4, alarm: bool = False) -> None:
        self.mode, self.alarm, self.sent = mode, alarm, []  # type: ignore[var-annotated]
        self.reply = 0

    def feedback(self, ip: str) -> Feedback:
        return Feedback(self.mode, (300.0, 0.0, 20.0, 0.0), False, self.mode != 4, self.alarm)

    def send(self, ip: str, command: str) -> tuple[int, str]:
        self.sent.append(command)
        if self.reply == 0:
            self.mode = {"EnableRobot()": 5, "StartDrag()": 6, "StopDrag()": 5}.get(
                command, self.mode
            )
        return self.reply, ""


@pytest.fixture()
def robot(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> FakeRobot:
    use_dobot(api)
    r = FakeRobot()
    monkeypatch.setattr("app.routers.robot.read_feedback", r.feedback)
    monkeypatch.setattr("app.routers.robot.send_dashboard", r.send)
    return r


def test_enable_requires_admin_and_the_dobot_driver(api: TestClient) -> None:
    assert api.post("/api/robot/enable").status_code == 401
    r = api.post("/api/robot/enable", headers=H)
    assert (r.status_code, r.json()["error"]["code"]) == (409, "driver_not_dobot")
    assert api.post("/api/robot/drag", json={"on": True}, headers=H).status_code == 409


def test_enable_sends_enablerobot_only_when_disabled(api: TestClient, robot: FakeRobot) -> None:
    s = api.post("/api/robot/enable", headers=H).json()
    assert robot.sent == ["EnableRobot()"] and s["mode"] == 5
    api.post("/api/robot/enable", headers=H)  # ya habilitado: no repite el comando
    assert robot.sent == ["EnableRobot()"]


def test_enable_refuses_with_an_alarm_and_never_clears_it(
    api: TestClient, robot: FakeRobot
) -> None:
    robot.mode, robot.alarm = 9, True
    r = api.post("/api/robot/enable", headers=H)
    assert (r.status_code, r.json()["error"]["code"]) == (409, "robot_alarm")
    assert robot.sent == []  # ni EnableRobot ni ClearError


def test_enable_reports_a_rejected_command(api: TestClient, robot: FakeRobot) -> None:
    robot.reply = -1
    r = api.post("/api/robot/enable", headers=H)
    assert (r.status_code, r.json()["error"]["code"]) == (502, "robot_command_failed")
    assert "ErrorID -1" in r.json()["error"]["message"]


def test_drag_needs_an_enabled_robot_then_toggles(api: TestClient, robot: FakeRobot) -> None:
    r = api.post("/api/robot/drag", json={"on": True}, headers=H)  # deshabilitado
    assert (r.status_code, r.json()["error"]["code"]) == (409, "invalid_state")
    assert robot.sent == []
    api.post("/api/robot/enable", headers=H)
    assert api.post("/api/robot/drag", json={"on": True}, headers=H).json()["mode"] == 6
    assert api.post("/api/robot/drag", json={"on": False}, headers=H).json()["mode"] == 5
    assert robot.sent == ["EnableRobot()", "StartDrag()", "StopDrag()"]
    assert (
        api.post("/api/robot/drag", json={}, headers=H).json()["error"]["code"]
        == "validation_error"
    )


def test_unreachable_robot_gives_a_clear_error(
    api: TestClient, robot: FakeRobot, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(ip: str) -> Feedback:
        raise TimeoutError("timed out")

    monkeypatch.setattr("app.routers.robot.read_feedback", down)
    r = api.post("/api/robot/enable", headers=H)
    assert (r.status_code, r.json()["error"]["code"]) == (502, "robot_unreachable")
