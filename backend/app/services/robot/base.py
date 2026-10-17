from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

Command = dict[str, Any]


@dataclass(frozen=True)
class Point3D:
    x: float
    y: float
    z: float


class RobotStopped(Exception):
    """El trabajo se detuvo con `stop()` antes de terminar."""


class RobotDriver(Protocol):
    def connect(self) -> None: ...
    def home(self) -> None: ...
    def calibrate(
        self, origin: Point3D, x_axis: Point3D, y_axis: Point3D, z_paper: float
    ) -> None: ...
    def execute(self, path: list[Command], on_progress: Callable[[float], None]) -> None:
        """Ejecuta la ruta informando el progreso (0–1). Lanza `RobotStopped` si se detiene."""
        ...

    def pause(self) -> None: ...
    def resume(self) -> None: ...  # añadido al plan: sin él `pause` no tendría vuelta atrás
    def stop(self) -> None: ...
    def dip_brush(self) -> None: ...
    def disconnect(self) -> None: ...
