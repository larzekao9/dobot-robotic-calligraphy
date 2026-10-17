import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import require_admin
from app.errors import AppError
from app.schemas.robot import RobotConfigOut, RobotStatus
from app.services.robot.config import PointName, RobotConfig, load_config, save_config
from app.services.robot.dobot_driver import (
    MODE_DISABLED,
    MODE_ENABLED,
    MODE_ERROR,
    MODE_NAMES,
    describe_error,
    read_feedback,
    send_dashboard,
)

router = APIRouter(prefix="/api/robot", tags=["robot"], dependencies=[Depends(require_admin)])


def _out(cfg: RobotConfig) -> RobotConfigOut:
    return RobotConfigOut(**cfg.model_dump(), calibrated=cfg.calibrated)


@router.get("/config")
def get_config() -> RobotConfigOut:
    return _out(load_config())


@router.put("/config")
def put_config(body: RobotConfig) -> RobotConfigOut:
    save_config(body)
    return _out(body)


MODE_DRAG = 6


class DragBody(BaseModel):
    on: bool


def _status_from(cfg: RobotConfig) -> RobotStatus:
    if cfg.driver != "dobot":
        return RobotStatus(driver="mock", reachable=True, mode=5, mode_name="Simulador")
    try:
        fb = read_feedback(cfg.ip)
    except (OSError, ValueError) as exc:
        return RobotStatus(
            driver="dobot", reachable=False, error=f"No hay conexión con {cfg.ip}: {exc}"
        )
    return RobotStatus(
        driver="dobot",
        reachable=True,
        mode=fb.mode,
        mode_name=MODE_NAMES.get(fb.mode, str(fb.mode)),
        enabled=fb.enabled,
        alarm=fb.alarm,
        pose=list(fb.pose),
    )


def _live_status() -> tuple[RobotConfig, RobotStatus]:
    """Config + estado del robot real; falla con un error claro si no es el driver «dobot»."""
    cfg = load_config()
    if cfg.driver != "dobot":
        raise AppError("driver_not_dobot", "Activa el driver «dobot» y guarda los ajustes.", 409)
    st = _status_from(cfg)
    if not st.reachable:
        raise AppError("robot_unreachable", st.error or "El robot no responde.", 502)
    return cfg, st


def _send(cfg: RobotConfig, command: str) -> None:
    try:
        code, _ = send_dashboard(cfg.ip, command)
    except (OSError, ValueError, RuntimeError) as exc:
        raise AppError("robot_unreachable", f"{command}: {exc}", 502) from exc
    if code != 0:
        raise AppError("robot_command_failed", describe_error(command, code), 502)


def _wait_for(cfg: RobotConfig, modes: set[int], timeout: float) -> RobotStatus:
    end = time.monotonic() + timeout
    while True:
        st = _status_from(cfg)
        if (st.reachable and st.mode in modes) or time.monotonic() > end:
            return st
        time.sleep(0.2)


@router.get("/status")
def status() -> RobotStatus:
    """Estado del robot leyendo el puerto de feedback (no envía ningún comando de movimiento)."""
    return _status_from(load_config())


@router.post("/enable")
def enable() -> RobotStatus:
    """Habilita los motores (`EnableRobot()`). No mueve el brazo; no limpia alarmas."""
    cfg, st = _live_status()
    if st.alarm or st.mode == MODE_ERROR:
        raise AppError(
            "robot_alarm",
            "El robot tiene una alarma activa. Revísala y límpiala en DobotStudio.",
            409,
        )
    if st.mode == MODE_DISABLED:
        _send(cfg, "EnableRobot()")
        st = _wait_for(cfg, {MODE_ENABLED}, 10.0)
        if st.mode != MODE_ENABLED:
            raise AppError("robot_not_enabled", "El robot no pasó a «Habilitado» a tiempo.", 502)
    elif st.mode not in (MODE_ENABLED, MODE_DRAG):
        raise AppError("invalid_state", f"No se puede habilitar desde «{st.mode_name}».", 409)
    return st


@router.post("/drag")
def drag(body: DragBody) -> RobotStatus:
    """Inicia o detiene el modo arrastre (`StartDrag()`/`StopDrag()`) para guiar el brazo a mano."""
    cfg, st = _live_status()
    if st.alarm or st.mode == MODE_ERROR:
        raise AppError("robot_alarm", "El robot tiene una alarma activa.", 409)
    if st.mode not in (MODE_ENABLED, MODE_DRAG):
        raise AppError("invalid_state", "Habilita el robot antes de usar el modo arrastre.", 409)
    _send(cfg, "StartDrag()" if body.on else "StopDrag()")
    wanted = MODE_DRAG if body.on else MODE_ENABLED
    st = _wait_for(cfg, {wanted}, 5.0)
    if st.mode != wanted:
        raise AppError("invalid_state", f"El robot sigue en «{st.mode_name}».", 502)
    return st


@router.post("/capture/{point}")
def capture(point: PointName) -> RobotConfigOut:
    """Guarda la pose actual del robot (x, y, z) como punto de calibración.

    Mover el brazo a mano (modo arrastre / DobotStudio) hasta que la punta toque el punto.
    """
    cfg = load_config()
    if cfg.driver != "dobot":
        raise AppError("driver_not_dobot", "Activa el driver «dobot» para capturar puntos.", 409)
    try:
        x, y, z, _ = read_feedback(cfg.ip).pose
    except (OSError, ValueError) as exc:
        raise AppError("robot_unreachable", f"No hay conexión con {cfg.ip}: {exc}", 502) from exc
    setattr(cfg, point, [round(x, 3), round(y, 3), round(z, 3)])
    save_config(cfg)
    return _out(cfg)
