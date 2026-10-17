from pydantic import BaseModel

from app.services.robot.config import RobotConfig


class RobotConfigOut(RobotConfig):
    calibrated: bool = False  # solo lectura: hay origen y las dos esquinas


class RobotStatus(BaseModel):
    driver: str
    reachable: bool
    mode: int | None = None
    mode_name: str | None = None
    enabled: bool | None = None
    alarm: bool | None = None
    pose: list[float] | None = None  # x, y, z, r
    error: str | None = None
