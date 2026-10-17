import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from app.services.robot.base import Point3D, RobotStopped
from app.services.robot.config import RobotConfig
from app.services.robot.dobot_driver import (
    FEEDBACK_SIZE,
    DobotDriver,
    DobotError,
    parse_feedback,
    read_feedback,
    send_dashboard,
)
from app.services.robot.paper_frame import PaperFrame
from app.services.strokes import air_path
from tests.fake_mg400 import FakeMG400, build_packet

# Cartulina de 210×297 mm: x del papel → +y del robot, y del papel → −x del robot.
ORIGIN, X_AXIS, Y_AXIS = [300.0, -100.0, 20.0], [300.0, 110.0, 20.0], [3.0, -100.0, 20.0]
Z_UP = 28.0  # z del papel (20) + lift_mm (8)

PATH: list[dict[str, Any]] = [
    {"op": "move", "x": 10.0, "y": 20.0, "z": "up"},
    {"op": "down"},
    {"op": "line", "x": 30.0, "y": 20.0, "pressure": 0.8},
    {"op": "line", "x": 30.0, "y": 40.0, "pressure": 0.3},
    {"op": "up"},
]


def cfg(**over: object) -> RobotConfig:
    base = {
        "driver": "dobot",
        "ip": "127.0.0.1",
        "origin": ORIGIN,
        "x_axis": X_AXIS,
        "y_axis": Y_AXIS,
        "dip_dwell_s": 0,
    }
    return RobotConfig.model_validate({**base, **over})


@pytest.fixture()
def fake() -> Iterator[FakeMG400]:
    f = FakeMG400()
    yield f
    f.close()


def driver(fake: FakeMG400, **over: object) -> DobotDriver:
    d = DobotDriver(
        cfg(**over),
        dashboard_port=fake.dashboard_port,
        move_port=fake.move_port,
        feedback_port=fake.feedback_port,
        sync_timeout=5,
    )
    d.connect()
    d.home()
    return d


# --- feedback --------------------------------------------------------------------------------


def test_parse_feedback_reads_mode_pose_and_flags() -> None:
    fb = parse_feedback(build_packet(5, (1.5, -2.5, 30.0, 4.0), alarm=True))
    assert (fb.mode, fb.pose, fb.alarm, fb.enabled) == (5, (1.5, -2.5, 30.0, 4.0), True, True)


def test_parse_feedback_rejects_bad_packets() -> None:
    with pytest.raises(ValueError, match="bytes"):
        parse_feedback(b"\x00" * 10)
    with pytest.raises(ValueError, match="TestValue"):
        parse_feedback(b"\x00" * FEEDBACK_SIZE)


def test_read_feedback_from_socket(fake: FakeMG400) -> None:
    fb = read_feedback("127.0.0.1", fake.feedback_port)
    assert fb.mode == 4 and fb.pose == (300.0, 0.0, 50.0, 0.0)


def test_send_dashboard_single_command(fake: FakeMG400) -> None:
    assert send_dashboard("127.0.0.1", "EnableRobot()", port=fake.dashboard_port) == (0, "")
    assert send_dashboard("127.0.0.1", "RobotMode()", port=fake.dashboard_port) == (0, "5")
    assert fake.dashboard == ["EnableRobot()", "RobotMode()"]


# --- marco de la cartulina -------------------------------------------------------------------


def test_paper_frame_maps_paper_mm_to_robot_xy() -> None:
    f = PaperFrame.from_points(*[(p[0], p[1], p[2]) for p in (ORIGIN, X_AXIS, Y_AXIS)])
    assert (f.width, f.height) == pytest.approx((210, 297))
    assert f.to_robot(0, 0) == pytest.approx((300, -100))
    assert f.to_robot(10, 20) == pytest.approx((280, -90))
    f.check_inside(210, 297)
    with pytest.raises(ValueError, match="fuera de la cartulina"):
        f.check_inside(215, 10)


def test_paper_frame_rejects_bad_calibrations() -> None:
    with pytest.raises(ValueError, match="mínimo"):
        PaperFrame.from_points((0, 0, 0), (10, 0, 0), (0, 200, 0))
    with pytest.raises(ValueError, match="perpendiculares"):
        PaperFrame.from_points((0, 0, 0), (200, 0, 0), (150, 150, 0))


# --- conexión y arranque ---------------------------------------------------------------------


def test_home_enables_robot_and_sets_speeds_in_order(fake: FakeMG400) -> None:
    d = driver(fake)
    assert fake.dashboard[:1] == ["GetErrorID()"] or fake.dashboard[0] == "EnableRobot()"
    cmds = [c for c in fake.dashboard if c != "GetErrorID()"]
    assert cmds == [
        "EnableRobot()",
        "SpeedFactor(20)",
        "User(0)",
        "Tool(0)",
        "SpeedL(30)",
        "AccL(30)",
        "CP(0)",
    ]
    assert d.frame is not None and d.frame.z_paper == 20
    assert fake.motion == []  # home() no mueve el brazo
    d.disconnect()


def test_connect_fails_clearly_when_robot_is_unreachable() -> None:
    d = DobotDriver(cfg(), dashboard_port=1, move_port=1, feedback_port=1, connect_timeout=0.5)
    with pytest.raises(DobotError, match="No se pudo conectar"):
        d.connect()


def test_connect_refuses_when_robot_has_an_alarm() -> None:
    f = FakeMG400(mode=9, alarm=True)
    d = DobotDriver(
        cfg(), dashboard_port=f.dashboard_port, move_port=f.move_port, feedback_port=f.feedback_port
    )
    try:
        with pytest.raises(DobotError, match="alarma activa"):
            d.connect()
        assert not any(c.startswith("ClearError") for c in f.dashboard)  # nunca limpia solo
    finally:
        d.disconnect()
        f.close()


# --- ejecución -------------------------------------------------------------------------------


def test_execute_translates_strokes_to_movl_and_reports_progress(fake: FakeMG400) -> None:
    d = driver(fake)
    seen: list[float] = []
    d.execute(PATH, seen.append)
    assert fake.movl() == [
        "MovL(280.000,-90.000,28.000,0.000)",  # move: pluma arriba
        "MovL(280.000,-90.000,20.000,0.000)",  # down: modo lápiz → sin presión
        "MovL(280.000,-70.000,20.000,0.000)",
        "MovL(260.000,-70.000,20.000,0.000)",
        "MovL(260.000,-70.000,28.000,0.000)",  # up
    ]
    assert fake.motion.count("Sync()") >= 2
    assert seen[0] == 0.0 and seen[-1] == 1.0 and seen == sorted(seen)
    d.disconnect()


def test_pressure_lowers_z_when_not_in_pencil_mode(fake: FakeMG400) -> None:
    d = driver(fake, pencil_mode=False, press_depth_mm=2.0)
    d.execute(PATH, lambda _: None)
    zs = [float(c.split(",")[2]) for c in fake.movl()]
    assert zs == pytest.approx([28.0, 18.4, 18.4, 19.4, 28.0])  # 20 − presión×2
    d.disconnect()


def test_lifts_first_if_the_brush_starts_low(fake: FakeMG400) -> None:
    fake.pose = (300.0, 0.0, 20.0, 0.0)
    d = driver(fake)
    d.execute(PATH[:2] + PATH[-1:], lambda _: None)
    assert fake.movl()[0] == "MovL(300.000,0.000,28.000,0.000)"
    d.disconnect()


def test_dip_goes_to_the_inkwell_and_back(fake: FakeMG400) -> None:
    d = driver(
        fake, pencil_mode=False, ink=[200.0, 100.0, 5.0], dip_depth_mm=3, dip_clearance_mm=30
    )
    d.execute([{"op": "dip"}, *PATH], lambda _: None)
    assert fake.movl()[:4] == [
        "MovL(300.000,0.000,35.000,0.000)",  # sube en el sitio a la altura de viaje
        "MovL(200.000,100.000,35.000,0.000)",
        "MovL(200.000,100.000,2.000,0.000)",  # tinta − profundidad
        "MovL(200.000,100.000,35.000,0.000)",
    ]
    d.disconnect()


def test_pencil_mode_skips_the_ink(fake: FakeMG400) -> None:
    d = driver(fake)  # modo lápiz por defecto
    d.execute([{"op": "dip"}, *PATH], lambda _: None)
    assert not any("200.000,100.000" in c for c in fake.movl()) and len(fake.movl()) == 5
    d.disconnect()


def test_dry_run_never_lowers_the_pen(fake: FakeMG400) -> None:
    d = driver(fake, pencil_mode=False, press_depth_mm=5)
    d.execute(air_path(PATH), lambda _: None)
    assert {float(c.split(",")[2]) for c in fake.movl()} == {28.0}
    d.disconnect()


# --- validación previa y errores -------------------------------------------------------------


def test_path_outside_the_paper_is_rejected_before_any_movement(fake: FakeMG400) -> None:
    d = driver(fake)
    bad = [*PATH, {"op": "move", "x": 400.0, "y": 10.0, "z": "up"}]
    with pytest.raises(DobotError, match="fuera de la cartulina"):
        d.execute(bad, lambda _: None)
    assert fake.motion == []
    d.disconnect()


def test_requires_calibration_and_ink_before_moving(fake: FakeMG400) -> None:
    d = driver(fake, origin=None)
    with pytest.raises(DobotError, match="Falta calibrar"):
        d.execute(PATH, lambda _: None)
    d.disconnect()
    d2 = driver(fake, pencil_mode=False)  # sin tintero
    with pytest.raises(DobotError, match="tintero"):
        d2.execute([{"op": "dip"}, *PATH], lambda _: None)
    assert fake.motion == []
    d2.disconnect()


def test_command_error_resets_queue_and_lifts_the_pen(fake: FakeMG400) -> None:
    fake.fail_movl_at = 4  # falla con la pluma abajo
    d = driver(fake)
    with pytest.raises(DobotError, match="ErrorID -20000"):
        d.execute(PATH, lambda _: None)
    assert "ResetRobot()" in fake.dashboard
    assert fake.movl()[-1].endswith(f",{Z_UP:.3f},0.000)")  # último movimiento: subir
    d.disconnect()


def test_stop_during_a_move_raises_resets_and_lifts(fake: FakeMG400) -> None:
    d = driver(fake)
    fake.hold_sync.set()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            d.execute(PATH, lambda _: None)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=run)
    t.start()
    assert fake.sync_received.wait(5)
    d.stop()
    t.join(10)
    assert errors and isinstance(errors[0], RobotStopped)
    assert "ResetRobot()" in fake.dashboard
    assert fake.movl()[-1].endswith(f",{Z_UP:.3f},0.000)")
    d.disconnect()


def test_alarm_while_moving_aborts_without_trying_to_move(fake: FakeMG400) -> None:
    d = driver(fake)
    fake.hold_sync.set()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            d.execute(PATH, lambda _: None)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=run)
    t.start()
    assert fake.sync_received.wait(5)
    n_before = len(fake.movl())
    fake.mode, fake.alarm = 9, True  # p. ej. colisión
    t.join(10)
    assert errors and isinstance(errors[0], DobotError) and "alarma" in str(errors[0])
    assert len(fake.movl()) == n_before  # con alarma no se intenta mover
    assert not any(c.startswith("ClearError") for c in fake.dashboard)
    d.disconnect()


def test_pause_and_resume_use_the_dashboard(fake: FakeMG400) -> None:
    d = driver(fake)
    d.pause()
    d.resume()
    assert fake.dashboard[-2:] == ["Pause()", "Continue()"]
    d.disconnect()


def test_protocol_methods_and_standalone_dip(fake: FakeMG400) -> None:
    d = driver(fake, pencil_mode=False, ink=[200.0, 100.0, 5.0])
    d.calibrate(Point3D(*ORIGIN), Point3D(*X_AXIS), Point3D(*Y_AXIS), 21.0)
    assert d.frame is not None and d.frame.z_paper == 21.0
    d.dip_brush()
    assert any("200.000,100.000,2.000" in c for c in fake.movl())
    d.disconnect()
    time.sleep(0.05)
