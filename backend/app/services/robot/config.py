"""Configuración del robot guardada en `data/robot_config.json` (editable desde la interfaz).

Los valores por defecto son conservadores: modo lápiz activo (sin tinta ni presión), velocidades
bajas y sin calibración. Nada se mueve hasta que se calibra la cartulina.
"""

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.config import settings

Xyz = Annotated[list[float], Field(min_length=3, max_length=3)]
PointName = Literal["origin", "x_axis", "y_axis", "ink"]


class RobotConfig(BaseModel):
    driver: Literal["mock", "dobot"] = "mock"
    ip: str = Field(default="192.168.1.6", max_length=64)  # LAN1 del MG400 (192.168.1.6)
    user: int = Field(default=0, ge=0, le=9)
    tool: int = Field(default=0, ge=0, le=9)
    # Velocidad: proporciones (1-100) de los máximos configurados en DobotStudio.
    speed_factor: int = Field(default=20, ge=1, le=100)
    speed_l: int = Field(default=30, ge=1, le=100)
    accel_l: int = Field(default=30, ge=1, le=100)
    cp: int = Field(default=0, ge=0, le=100)  # 0 = pasa exacto por cada punto
    # Geometría del pincel (mm)
    lift_mm: float = Field(default=8, ge=2, le=50)  # altura de la pluma arriba sobre el papel
    press_depth_mm: float = Field(default=2, ge=0, le=10)  # bajada extra con presión 1.0
    r_deg: float = Field(default=0, ge=-180, le=180)  # giro fijo del efector
    # Tinta
    pencil_mode: bool = True  # prueba con lápiz: ignora la tinta y no presiona
    dip_clearance_mm: float = Field(default=30, ge=5, le=100)
    dip_depth_mm: float = Field(default=3, ge=0, le=30)  # bajada bajo el punto de tinta capturado
    dip_dwell_s: float = Field(default=1.0, ge=0, le=10)
    # Calibración: pose (x, y, z) del robot con la punta tocando cada punto
    origin: Xyz | None = None  # esquina superior izquierda de la cartulina (z = z del papel)
    x_axis: Xyz | None = None  # esquina superior derecha
    y_axis: Xyz | None = None  # esquina inferior izquierda
    ink: Xyz | None = None  # superficie de la tinta

    @model_validator(mode="after")
    def _ip_not_blank(self) -> "RobotConfig":
        if not self.ip.strip():
            raise ValueError("La IP del robot no puede estar vacía.")
        return self

    @property
    def calibrated(self) -> bool:
        return None not in (self.origin, self.x_axis, self.y_axis)


def config_path() -> Path:
    if settings.robot_config_path:
        return Path(settings.robot_config_path)
    from app.seeds import DATA_DIR

    return DATA_DIR / "robot_config.json"


def load_config() -> RobotConfig:
    path = config_path()
    if path.exists():
        return RobotConfig.model_validate_json(path.read_text(encoding="utf-8"))
    return RobotConfig(driver="dobot" if settings.robot_driver == "dobot" else "mock")


def save_config(cfg: RobotConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg.model_dump(), indent=2), encoding="utf-8")
