import threading
from collections.abc import Callable

from app.services.robot.base import Command, Point3D, RobotStopped
from app.services.strokes import command_durations


class MockDriver:
    """No mueve nada: simula el tiempo de la ruta (dividido por `time_scale`) e informa progreso."""

    def __init__(self, time_scale: float = 10.0) -> None:
        self.time_scale = time_scale
        self.connected = False
        self.dips = 0
        self.calibration: tuple[Point3D, Point3D, Point3D, float] | None = None
        self._stop = threading.Event()
        self._running = threading.Event()
        self._running.set()

    def connect(self) -> None:
        self.connected = True

    def home(self) -> None:
        self._require_connected()

    def calibrate(self, origin: Point3D, x_axis: Point3D, y_axis: Point3D, z_paper: float) -> None:
        self.calibration = (origin, x_axis, y_axis, z_paper)

    def execute(self, path: list[Command], on_progress: Callable[[float], None]) -> None:
        self._require_connected()
        durations = command_durations(path)
        on_progress(0.0)
        for i, (cmd, seconds) in enumerate(zip(path, durations, strict=True), start=1):
            self._running.wait()
            if self._stop.is_set():
                raise RobotStopped
            if cmd["op"] == "dip":
                self.dip_brush()
            if self.time_scale > 0 and seconds > 0 and self._stop.wait(seconds / self.time_scale):
                raise RobotStopped
            on_progress(i / len(path))

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    def stop(self) -> None:
        self._stop.set()
        self._running.set()  # despierta a un `execute` en pausa para que termine

    def dip_brush(self) -> None:
        self.dips += 1

    def disconnect(self) -> None:
        self.connected = False

    def _require_connected(self) -> None:
        if not self.connected:
            raise RuntimeError("El robot no está conectado.")
