import math
import threading
import uuid

import pytest
from fastapi.testclient import TestClient

from app.errors import AppError
from app.schemas.jobs import Layout
from app.services.jobs import JobRunner
from app.services.robot.base import RobotStopped
from app.services.robot.mock_driver import MockDriver
from app.services.strokes import (
    PRESSURE_END,
    PRESSURE_START,
    build_commands,
    command_durations,
    estimate_seconds,
    fit_char_size,
    place_text,
    preview_strokes,
    simplify,
    split_words,
)

SQUARE = [[[0.0, 0.0], [1024.0, 0.0], [1024.0, 1024.0]], [[0.0, 512.0], [1024.0, 512.0]]]


def glyphs(_: str) -> list[list[list[float]]]:
    return SQUARE


# --- trazos ----------------------------------------------------------------------------------


def test_split_words_ignores_separators() -> None:
    assert split_words("卡洛斯·马尔塔") == ["卡洛斯", "马尔塔"]
    assert split_words("アナ・マリア") == ["アナ", "マリア"]
    assert split_words(" ") == []


def test_simplify_keeps_endpoints_and_drops_collinear_points() -> None:
    pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0), (3.0, 5.0)]
    assert simplify(pts, 0.1) == [(0.0, 0.0), (3.0, 0.0), (3.0, 5.0)]
    assert simplify([(0.0, 0.0), (1.0, 1.0)], 0.1) == [(0.0, 0.0), (1.0, 1.0)]


def test_place_text_centers_horizontal_line_in_mm() -> None:
    layout = Layout(char_size_mm=40, spacing_mm=10, margin_mm=10)
    placed = place_text("abc", glyphs, layout)
    xs = [min(p[0] for s in c.strokes for p in s) for c in placed]
    assert xs == pytest.approx([(210 - 140) / 2 + i * 50 for i in range(3)])
    ys = [min(p[1] for s in c.strokes for p in s) for c in placed]
    assert ys == pytest.approx([(297 - 40) / 2] * 3)
    assert max(p[0] for s in placed[-1].strokes for p in s) == pytest.approx(xs[-1] + 40)


def test_place_text_vertical_columns_run_right_to_left() -> None:
    layout = Layout(orientation="vertical", char_size_mm=30, spacing_mm=5, margin_mm=10)
    placed = place_text("ab·cd", glyphs, layout)
    first = min(p[0] for s in placed[0].strokes for p in s)  # 'a', primera palabra
    third = min(p[0] for s in placed[2].strokes for p in s)  # 'c', segunda palabra
    assert first > third
    assert min(p[1] for s in placed[1].strokes for p in s) > min(
        p[1] for s in placed[0].strokes for p in s
    )


def test_place_text_wraps_each_word_on_its_own_line() -> None:
    placed = place_text("ab·cd", glyphs, Layout(char_size_mm=30, spacing_mm=5))
    y = [min(p[1] for s in c.strokes for p in s) for c in placed]
    assert y[0] == y[1] < y[2] == y[3]


def test_place_text_overflow_and_empty() -> None:
    with pytest.raises(AppError) as exc:
        place_text("abcdefgh", glyphs, Layout(paper="A5", char_size_mm=40, auto_fit=False))
    assert exc.value.code == "layout_overflow"
    with pytest.raises(AppError) as exc2:
        place_text("·", glyphs, Layout())
    assert exc2.value.code == "empty_text"


def test_auto_fit_shrinks_characters_to_fit() -> None:
    layout = Layout(paper="A5", char_size_mm=40, spacing_mm=8)
    placed = place_text("abcdef", glyphs, layout)  # 6×40 + 5×8 = 280 mm no caben en 118 mm
    xs = [p[0] for c in placed for s in c.strokes for p in s]
    assert max(xs) - min(xs) <= 118.0001
    assert fit_char_size(["abcdef"], layout) == pytest.approx(13, abs=0.01)
    assert fit_char_size(["ab"], layout) == 40  # lo que cabe no se toca
    with pytest.raises(AppError) as exc:  # ni reduciendo cabe: queda por debajo de 10 mm
        place_text("abcdefgh", glyphs, layout)
    assert exc.value.code == "layout_overflow"


def test_layout_paper_sizes() -> None:
    assert Layout().paper_size() == (210, 297)
    assert Layout(paper="A5", landscape=True).paper_size() == (210, 148)
    assert Layout(paper="custom", width_mm=100, height_mm=300).paper_size() == (100, 300)
    with pytest.raises(ValueError, match="personalizado"):
        Layout(paper="custom")


def test_commands_structure_and_pressure_taper() -> None:
    layout = Layout(dip_every_chars=1)
    cmds = build_commands(place_text("ab", glyphs, layout), layout)
    ops = [c["op"] for c in cmds]
    assert ops[:3] == ["dip", "move", "down"]
    assert cmds[1]["z"] == "up"
    assert ops.count("down") == ops.count("up") == 4  # 2 caracteres × 2 trazos
    assert ops.count("dip") == 2  # uno por carácter
    first_stroke = cmds[3 : cmds.index({"op": "up"})]
    pressures = [c["pressure"] for c in first_stroke]
    assert pressures[0] < PRESSURE_START and pressures[-1] == pytest.approx(PRESSURE_END, abs=0.01)
    assert pressures == sorted(pressures, reverse=True)


def test_dip_every_n_characters() -> None:
    layout = Layout(dip_every_chars=2, char_size_mm=30)
    cmds = build_commands(place_text("abcd", glyphs, layout), layout)
    assert [c["op"] for c in cmds].count("dip") == 2


def test_stroke_order_is_preserved() -> None:
    layout = Layout(char_size_mm=40)
    strokes = preview_strokes(build_commands(place_text("a", glyphs, layout), layout))
    assert len(strokes) == 2
    assert strokes[0][-1][1] > strokes[1][0][1] + 1  # el trazo en L va antes que la barra media
    assert math.isclose(strokes[1][0][0], strokes[0][0][0], abs_tol=0.01)


def test_estimate_matches_durations() -> None:
    layout = Layout()
    cmds = build_commands(place_text("abc", glyphs, layout), layout)
    assert estimate_seconds(cmds) == pytest.approx(sum(command_durations(cmds)))
    assert estimate_seconds(cmds) > 3 * 4  # al menos los 3 baños de tinta... 2 por 3 caracteres


# --- simulador -------------------------------------------------------------------------------


def _path() -> list[dict[str, object]]:
    layout = Layout()
    return build_commands(place_text("ab", glyphs, layout), layout)


def test_mock_driver_reports_monotonic_progress_to_one() -> None:
    d = MockDriver(time_scale=0)
    seen: list[float] = []
    d.connect()
    d.home()
    d.execute(_path(), seen.append)
    assert seen[0] == 0.0 and seen[-1] == 1.0
    assert seen == sorted(seen)
    assert d.dips >= 1


def test_mock_driver_requires_connection() -> None:
    with pytest.raises(RuntimeError, match="conectado"):
        MockDriver(time_scale=0).execute(_path(), lambda _: None)


def test_mock_driver_stop_raises() -> None:
    d = MockDriver(time_scale=0)
    d.connect()
    d.stop()
    with pytest.raises(RobotStopped):
        d.execute(_path(), lambda _: None)


# --- API -------------------------------------------------------------------------------------


def _request_id(api: TestClient, name: str = "Carlos") -> str:
    return str(api.post("/api/names/convert", json={"name": name}).json()["request_id"])


def _create(api: TestClient, **extra: object) -> dict:  # type: ignore[type-arg]
    body = {"request_id": _request_id(api), "script": "zh", "rank": 1, **extra}
    r = api.post("/api/jobs", json=body)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def test_create_job_computes_path_in_draft(api: TestClient) -> None:
    job = _create(api)
    assert job["status"] == "draft" and job["progress"] == 0.0
    assert job["text"] == "卡洛斯" and job["script"] == "zh"
    assert job["layout"]["paper"] == "A4"
    ops = {c["op"] for c in job["path"]}
    assert {"dip", "move", "down", "line", "up"} <= ops
    assert job["estimated_seconds"] > 0
    xs = [c["x"] for c in job["path"] if "x" in c]
    assert 0 < min(xs) and max(xs) < 210


def test_create_japanese_job(api: TestClient) -> None:
    body = {"request_id": _request_id(api), "script": "ja", "rank": 1}
    r = api.post("/api/jobs", json=body)
    assert r.status_code == 201 and r.json()["text"] == "カルロス"


def test_job_runs_from_draft_to_done_with_mock(api: TestClient, runner: JobRunner) -> None:
    job = _create(api)
    r = api.post(f"/api/jobs/{job['id']}/start")
    assert r.status_code == 200 and r.json()["status"] in {"queued", "running", "done"}
    runner.wait(uuid.UUID(job["id"]))
    done = api.get(f"/api/jobs/{job['id']}").json()
    assert done["status"] == "done" and done["progress"] == 1.0
    assert done["started_at"] and done["finished_at"] and done["error"] is None


def test_start_twice_is_a_conflict(api: TestClient, runner: JobRunner) -> None:
    job = _create(api)
    api.post(f"/api/jobs/{job['id']}/start")
    runner.wait(uuid.UUID(job["id"]))
    r = api.post(f"/api/jobs/{job['id']}/start")
    assert (r.status_code, r.json()["error"]["code"]) == (409, "invalid_state")
    assert api.post(f"/api/jobs/{job['id']}/cancel").json()["error"]["code"] == "invalid_state"


def test_cancel_draft_and_it_cannot_start(api: TestClient) -> None:
    job = _create(api)
    r = api.post(f"/api/jobs/{job['id']}/cancel")
    assert r.json()["status"] == "cancelled" and r.json()["finished_at"]
    assert api.post(f"/api/jobs/{job['id']}/start").status_code == 409


def test_cancel_running_job_stops_the_robot(api: TestClient, engine, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy.orm import sessionmaker

    from app.main import app
    from app.services.jobs import get_runner

    gate = threading.Event()
    started = threading.Event()

    class SlowDriver(MockDriver):
        def execute(self, path, on_progress):  # type: ignore[no-untyped-def]
            started.set()
            if not self._stop.wait(5):
                gate.set()
            raise RobotStopped

    slow = JobRunner(sessionmaker(bind=engine), lambda: SlowDriver(time_scale=0))
    app.dependency_overrides[get_runner] = lambda: slow
    job = _create(api)
    api.post(f"/api/jobs/{job['id']}/start")
    assert started.wait(5)
    assert api.get(f"/api/jobs/{job['id']}").json()["status"] == "running"
    assert api.post(f"/api/jobs/{job['id']}/cancel").json()["status"] == "cancelled"
    slow.wait(uuid.UUID(job["id"]))
    assert not gate.is_set()  # terminó por stop(), no por timeout
    assert api.get(f"/api/jobs/{job['id']}").json()["status"] == "cancelled"


def test_driver_failure_marks_job_failed(api: TestClient, engine) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy.orm import sessionmaker

    from app.main import app
    from app.services.jobs import get_runner
    from app.services.robot.config import RobotConfig
    from app.services.robot.dobot_driver import DobotDriver

    unreachable = RobotConfig(driver="dobot", ip="127.0.0.1")  # nadie escucha en 29999
    failing = JobRunner(sessionmaker(bind=engine), lambda: DobotDriver(unreachable))
    app.dependency_overrides[get_runner] = lambda: failing
    job = _create(api)
    api.post(f"/api/jobs/{job['id']}/start")
    failing.wait(uuid.UUID(job["id"]))
    got = api.get(f"/api/jobs/{job['id']}").json()
    assert got["status"] == "failed" and "No se pudo conectar" in got["error"]


def test_list_jobs_and_get_detail(api: TestClient) -> None:
    job = _create(api)
    listed = api.get("/api/jobs").json()
    assert job["id"] in {j["id"] for j in listed}
    assert "path" not in listed[0]
    assert api.get(f"/api/jobs/{job['id']}").json()["path"]


def test_preview_endpoints(api: TestClient) -> None:
    before = len(api.get("/api/jobs").json())
    job = _create(api, layout={"paper": "A5", "char_size_mm": 30})
    p = api.post(f"/api/jobs/{job['id']}/preview").json()
    assert (p["paper_width_mm"], p["paper_height_mm"]) == (148, 210)
    assert p["char_count"] == 3 and p["stroke_count"] == len(p["strokes"]) > 3
    assert p["estimated_seconds"] > 0
    body = {"request_id": _request_id(api), "script": "ja", "layout": {"orientation": "vertical"}}
    stateless = api.post("/api/jobs/preview", json=body).json()
    assert stateless["text"] == "カルロス" and stateless["layout"]["orientation"] == "vertical"
    assert len(api.get("/api/jobs").json()) == before + 1  # la vista previa no guarda trabajos


def test_job_errors(api: TestClient) -> None:
    rid = _request_id(api)
    before = len(api.get("/api/jobs").json())
    missing = api.get(f"/api/jobs/{uuid.uuid4()}")
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "job_not_found")
    r = api.post("/api/jobs", json={"request_id": str(uuid.uuid4()), "script": "zh"})
    assert r.json()["error"]["code"] == "request_not_found"
    r = api.post("/api/jobs", json={"request_id": rid, "script": "zh", "rank": 3})
    assert (r.status_code, r.json()["error"]["code"]) == (422, "invalid_rank")
    big = {
        "request_id": rid,
        "script": "zh",
        "layout": {"paper": "A5", "char_size_mm": 100, "auto_fit": False},
    }
    r = api.post("/api/jobs", json=big)
    assert (r.status_code, r.json()["error"]["code"]) == (422, "layout_overflow")
    bad = {"request_id": rid, "script": "zh", "layout": {"paper": "custom"}}
    assert api.post("/api/jobs", json=bad).json()["error"]["code"] == "validation_error"
    assert len(api.get("/api/jobs").json()) == before
