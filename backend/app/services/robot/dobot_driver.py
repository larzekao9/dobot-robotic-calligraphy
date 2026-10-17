"""Driver del Dobot MG400 por TCP/IP (Fase 2, Hito 11).

Basado en la «TCP/IP Remote Control Interface Guide (4axis)» (abril 2024) y en el cliente oficial
https://github.com/Dobot-Arm/TCP-IP-4Axis-Python (controlador ≥ V1.5.6.0). Es distinto del
protocolo V4 de los robots de 6 ejes (CR/Nova): 4 ejes (x, y, z, r), movimiento por el puerto
30003, sin `RequestControl`/`PowerOn` y sin `ResultID` en las respuestas.

| Puerto | Uso |
|---|---|
| 29999 | Dashboard: `EnableRobot`, `SpeedFactor`, `Pause`, `Continue`, `ResetRobot`… |
| 30003 | Movimiento: `MovL(x,y,z,r)` (cola) y `Sync()` (bloquea hasta vaciar la cola) |
| 30004 | Feedback de 1440 bytes cada 8 ms (modo, pose, alarma) |

Seguridad (nada de esto sustituye al paro de emergencia físico):
- Toda la ruta se valida (dentro de la cartulina calibrada) **antes** del primer movimiento.
- Ante un paro, un error o una alarma: `ResetRobot()` y la pluma sube a la altura segura.
- Nunca se llama a `ClearError()` solo: una alarma la revisa y limpia una persona.
- Al desconectar el brazo queda habilitado (no se deshabilita para que no ceda).
"""

import logging
import re
import socket
import struct
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from app.services.robot.base import Command, Point3D, RobotStopped
from app.services.robot.config import RobotConfig
from app.services.robot.paper_frame import PaperFrame

log = logging.getLogger(__name__)

DASHBOARD_PORT, MOVE_PORT, FEEDBACK_PORT = 29999, 30003, 30004
FEEDBACK_SIZE = 1440
TEST_VALUE = 0x0123456789ABCDEF
_OFF_MODE, _OFF_TEST, _OFF_TCP = 24, 48, 624
_OFF_QUEUED, _OFF_ENABLE, _OFF_ERROR = 1014, 1026, 1029

MODE_DISABLED, MODE_ENABLED, MODE_RUNNING, MODE_ERROR = 4, 5, 7, 9
MODE_NAMES = {
    1: "Iniciando",
    2: "Freno abierto",
    3: "Apagado",
    4: "Deshabilitado",
    5: "Habilitado y libre",
    6: "Modo arrastre",
    7: "En movimiento",
    8: "Grabando trayectoria",
    9: "ALARMA",
    10: "En pausa",
    11: "Jog",
}
_ERRORS = {
    -1: "el robot no pudo recibir o ejecutar el comando",
    -10000: "el comando no existe",
    -20000: "número de parámetros incorrecto",
}
_RESPONSE = re.compile(r"^(-?\d+),\{(.*)\},(\w+)\((.*)\);?$", re.DOTALL)


class DobotError(RuntimeError):
    pass


@dataclass(frozen=True)
class Feedback:
    mode: int
    pose: tuple[float, float, float, float]  # x, y, z, r del TCP
    run_queued: bool
    enabled: bool
    alarm: bool


def parse_feedback(buf: bytes) -> Feedback:
    """Paquete de 1440 bytes (little-endian). Valida el tamaño y el `TestValue`."""
    if len(buf) != FEEDBACK_SIZE:
        raise ValueError(f"paquete de feedback de {len(buf)} bytes (se esperaban {FEEDBACK_SIZE})")
    if struct.unpack_from("<Q", buf, _OFF_TEST)[0] != TEST_VALUE:
        raise ValueError("paquete de feedback desalineado (TestValue incorrecto)")
    x, y, z, _rx, _ry, r = struct.unpack_from("<6d", buf, _OFF_TCP)
    return Feedback(
        mode=struct.unpack_from("<Q", buf, _OFF_MODE)[0],
        pose=(x, y, z, r),
        run_queued=bool(buf[_OFF_QUEUED]),
        enabled=bool(buf[_OFF_ENABLE]),
        alarm=bool(buf[_OFF_ERROR]),
    )


def read_feedback(ip: str, port: int = FEEDBACK_PORT, timeout: float = 2.0) -> Feedback:
    """Lee un paquete de feedback (para estado y captura de puntos, sin tocar el robot)."""
    with socket.create_connection((ip, port), timeout=timeout) as s:
        s.settimeout(timeout)
        buf = b""
        while len(buf) < FEEDBACK_SIZE:
            chunk = s.recv(FEEDBACK_SIZE - len(buf))
            if not chunk:
                raise ConnectionError("el robot cerró la conexión de feedback")
            buf += chunk
    return parse_feedback(buf)


def send_dashboard(
    ip: str, command: str, *, port: int = DASHBOARD_PORT, timeout: float = 3.0
) -> tuple[int, str]:
    """Envía un solo comando al dashboard (p. ej. `EnableRobot()`) y devuelve (ErrorID, valores)."""
    channel = _Channel(ip, port, timeout)
    try:
        return channel.request(command, timeout)
    finally:
        channel.close()


def describe_error(command: str, code: int) -> str:
    return DobotDriver._describe(command, code)


class _Channel:
    """Socket de texto: envía un comando y lee su respuesta `ErrorID,{valores},Comando(...);`."""

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(0.25)
        self._buf = b""

    def request(
        self, text: str, timeout: float = 5.0, abort: Callable[[], None] | None = None
    ) -> tuple[int, str]:
        self.sock.sendall(text.encode("utf-8"))
        deadline = time.monotonic() + timeout
        while b";" not in self._buf:
            if abort:
                abort()  # puede lanzar RobotStopped o DobotError
            if time.monotonic() > deadline:
                raise TimeoutError(f"Sin respuesta del robot a {text}")
            try:
                chunk = self.sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                raise ConnectionError("el robot cerró la conexión")
            self._buf += chunk
        message, _, self._buf = self._buf.partition(b";")
        m = _RESPONSE.match(message.decode("utf-8", "replace") + ";")
        if not m:
            raise DobotError(f"Respuesta inesperada a {text}: {message!r}")
        return int(m.group(1)), m.group(2)

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


@dataclass(frozen=True)
class _Step:
    kind: str  # "move" | "dip"
    xyz: tuple[float, float, float] | None
    op_index: int


class DobotDriver:
    def __init__(
        self,
        cfg: RobotConfig,
        *,
        dashboard_port: int = DASHBOARD_PORT,
        move_port: int = MOVE_PORT,
        feedback_port: int = FEEDBACK_PORT,
        connect_timeout: float = 3.0,
        sync_timeout: float = 120.0,
    ) -> None:
        self.cfg = cfg
        self.frame: PaperFrame | None = None
        self._ports = (dashboard_port, move_port, feedback_port)
        self._connect_timeout = connect_timeout
        self._sync_timeout = sync_timeout
        self._dash: _Channel | None = None
        self._move: _Channel | None = None
        self._fb: Feedback | None = None
        self._fb_lock = threading.Lock()
        self._fb_thread: threading.Thread | None = None
        self._fb_sock: socket.socket | None = None
        self._closing = threading.Event()
        self._stop = threading.Event()
        self._dash_lock = threading.Lock()
        self._xyz: tuple[float, float, float] | None = None  # último destino enviado

    # --- conexión ----------------------------------------------------------------------------

    def connect(self) -> None:
        dash_port, move_port, fb_port = self._ports
        try:
            self._dash = _Channel(self.cfg.ip, dash_port, self._connect_timeout)
            self._move = _Channel(self.cfg.ip, move_port, self._connect_timeout)
            self._fb_sock = socket.create_connection((self.cfg.ip, fb_port), self._connect_timeout)
        except OSError as exc:
            self.disconnect()
            raise DobotError(
                f"No se pudo conectar con el robot en {self.cfg.ip} "
                f"(puertos {dash_port}/{move_port}/{fb_port}): {exc}"
            ) from exc
        self._closing.clear()
        self._fb_thread = threading.Thread(target=self._read_feedback, daemon=True, name="mg400-fb")
        self._fb_thread.start()
        self._wait_feedback()
        fb = self._feedback()
        if fb.alarm or fb.mode == MODE_ERROR:
            raise DobotError(
                "El robot tiene una alarma activa "
                f"(GetErrorID: {self._dashboard('GetErrorID()', check=False)[1]}). "
                "Revísala y límpiala en DobotStudio antes de continuar."
            )

    def _read_feedback(self) -> None:
        sock = self._fb_sock
        assert sock is not None
        sock.settimeout(0.5)
        buf = b""
        while not self._closing.is_set():
            try:
                chunk = sock.recv(FEEDBACK_SIZE - len(buf))
            except TimeoutError:
                continue
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            if len(buf) == FEEDBACK_SIZE:
                try:
                    fb = parse_feedback(buf)
                except ValueError as exc:
                    log.warning("feedback_descartado", extra={"reason": str(exc)})
                else:
                    with self._fb_lock:
                        self._fb = fb
                buf = b""

    def _wait_feedback(self, timeout: float = 3.0) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._fb_lock:
                if self._fb is not None:
                    return
            time.sleep(0.01)
        raise DobotError("El robot no envía feedback por el puerto 30004.")

    def _feedback(self) -> Feedback:
        with self._fb_lock:
            if self._fb is None:
                raise DobotError("Sin feedback del robot.")
            return self._fb

    def disconnect(self) -> None:
        """Cierra los sockets. El brazo queda habilitado (no se deshabilita para que no ceda)."""
        self._closing.set()
        for ch in (self._dash, self._move):
            if ch:
                ch.close()
        if self._fb_sock:
            try:
                self._fb_sock.close()
            except OSError:
                pass
        self._dash = self._move = self._fb_sock = None

    # --- dashboard ---------------------------------------------------------------------------

    def _dashboard(self, text: str, *, check: bool = True) -> tuple[int, str]:
        if self._dash is None:
            raise DobotError("El robot no está conectado.")
        with self._dash_lock:
            code, values = self._dash.request(text)
        if check and code != 0:
            raise DobotError(self._describe(text, code))
        return code, values

    @staticmethod
    def _describe(text: str, code: int) -> str:
        reason = _ERRORS.get(code) or (
            "parámetro con tipo o rango incorrecto" if code <= -30000 else "error del robot"
        )
        return f"{text} → ErrorID {code}: {reason}"

    def home(self) -> None:
        """Habilita el robot y fija velocidades. No mueve el brazo."""
        mode = self._feedback().mode
        if mode == MODE_DISABLED:
            self._dashboard("EnableRobot()")
            self._wait_mode(MODE_ENABLED, 15.0)
        elif mode not in (MODE_ENABLED, MODE_RUNNING):
            raise DobotError(f"Estado del robot inesperado: {MODE_NAMES.get(mode, mode)} ({mode}).")
        c = self.cfg
        for cmd in (
            f"SpeedFactor({c.speed_factor})",
            f"User({c.user})",
            f"Tool({c.tool})",
            f"SpeedL({c.speed_l})",
            f"AccL({c.accel_l})",
            f"CP({c.cp})",
        ):
            self._dashboard(cmd)
        if c.calibrated and self.frame is None:
            assert c.origin and c.x_axis and c.y_axis
            self.calibrate(Point3D(*c.origin), Point3D(*c.x_axis), Point3D(*c.y_axis), c.origin[2])

    def _wait_mode(self, wanted: int, timeout: float) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self._feedback().mode == wanted:
                return
            time.sleep(0.05)
        raise DobotError(f"El robot no llegó al estado «{MODE_NAMES[wanted]}» en {timeout:.0f} s.")

    def calibrate(self, origin: Point3D, x_axis: Point3D, y_axis: Point3D, z_paper: float) -> None:
        try:
            frame = PaperFrame.from_points(
                (origin.x, origin.y, origin.z),
                (x_axis.x, x_axis.y, x_axis.z),
                (y_axis.x, y_axis.y, y_axis.z),
            )
        except ValueError as exc:
            raise DobotError(str(exc)) from exc
        self.frame = replace(frame, z_paper=z_paper)

    def pause(self) -> None:
        self._dashboard("Pause()")

    def resume(self) -> None:
        self._dashboard("Continue()")

    def stop(self) -> None:
        """Detiene el robot y vacía la cola. `execute` lo detecta, sube la pluma y lanza RobotStopped."""
        self._stop.set()
        if self._dash is not None:
            try:
                self._dashboard("ResetRobot()", check=False)
            except (OSError, TimeoutError, DobotError):
                log.exception("reset_failed")

    # --- movimiento --------------------------------------------------------------------------

    def _abort_check(self) -> None:
        if self._stop.is_set():
            raise RobotStopped
        fb = self._feedback()
        if fb.alarm or fb.mode == MODE_ERROR:
            raise DobotError("El robot reportó una alarma durante el movimiento.")

    def _movl(self, x: float, y: float, z: float) -> None:
        if self._move is None:
            raise DobotError("El robot no está conectado.")
        if self._stop.is_set():
            raise RobotStopped
        text = f"MovL({x:.3f},{y:.3f},{z:.3f},{self.cfg.r_deg:.3f})"
        code, _ = self._move.request(text, abort=self._abort_check)
        if code != 0:
            raise DobotError(self._describe(text, code))
        self._xyz = (x, y, z)

    def _sync(self, timeout: float | None = None) -> None:
        assert self._move is not None
        code, _ = self._move.request("Sync()", timeout or self._sync_timeout, self._abort_check)
        if code != 0:
            raise DobotError(self._describe("Sync()", code))

    def _z_up(self) -> float:
        assert self.frame is not None
        return self.frame.z_paper + self.cfg.lift_mm

    def _z_down(self, pressure: float) -> float:
        assert self.frame is not None
        depth = 0.0 if self.cfg.pencil_mode else self.cfg.press_depth_mm
        return self.frame.z_paper - max(0.0, min(1.0, pressure)) * depth

    def _plan(self, path: list[Command]) -> list[_Step]:
        """Traduce la ruta a destinos del robot y la valida entera antes de mover nada."""
        frame = self.frame
        if frame is None:
            raise DobotError("Falta calibrar la cartulina (origen y esquinas) antes de escribir.")
        cfg = self.cfg
        steps: list[_Step] = []
        px = py = 0.0
        for i, c in enumerate(path):
            op = c["op"]
            if op == "dip":
                if cfg.pencil_mode:
                    continue
                if cfg.ink is None:
                    raise DobotError(
                        "Falta capturar la posición del tintero (o activa el modo lápiz)."
                    )
                steps.append(_Step("dip", None, i))
            elif op in ("move", "line"):
                px, py = float(c["x"]), float(c["y"])
                try:
                    frame.check_inside(px, py)
                except ValueError as exc:
                    raise DobotError(str(exc)) from exc
                rx, ry = frame.to_robot(px, py)
                z = self._z_up() if op == "move" else self._z_down(float(c.get("pressure", 0.5)))
                steps.append(_Step("move", (rx, ry, z), i))
            elif op in ("down", "up"):
                rx, ry = frame.to_robot(px, py)
                z = self._z_up()
                if op == "down":
                    nxt = next((n for n in path[i + 1 :] if n["op"] == "line"), None)
                    z = self._z_down(float(nxt.get("pressure", 0.5)) if nxt else 0.5)
                steps.append(_Step("move", (rx, ry, z), i))
        return steps

    def _ensure_up(self) -> None:
        x, y, z, _ = self._feedback().pose
        if z < self._z_up() - 0.5:
            self._movl(x, y, self._z_up())
        else:
            self._xyz = (x, y, z)

    def _dip(self) -> None:
        ink = self.cfg.ink
        assert ink is not None and self._xyz is not None
        z_travel = max(self._z_up(), ink[2] + self.cfg.dip_clearance_mm)
        self._movl(self._xyz[0], self._xyz[1], z_travel)
        self._movl(ink[0], ink[1], z_travel)
        self._movl(ink[0], ink[1], ink[2] - self.cfg.dip_depth_mm)
        self._sync()
        if self._stop.wait(self.cfg.dip_dwell_s):
            raise RobotStopped
        self._movl(ink[0], ink[1], z_travel)

    def dip_brush(self) -> None:
        if self.frame is None:
            raise DobotError("Falta calibrar la cartulina antes de mojar el pincel.")
        if self.cfg.ink is None:
            raise DobotError("Falta capturar la posición del tintero.")
        try:
            self._ensure_up()
            self._dip()
            self._sync()
        except Exception:
            self._after_abort()
            raise

    def execute(self, path: list[Command], on_progress: Callable[[float], None]) -> None:
        steps = self._plan(path)  # lanza antes de mover si algo no cabe o falta calibrar
        self._stop.clear()
        on_progress(0.0)
        try:
            self._ensure_up()
            for step in steps:
                if step.kind == "dip":
                    self._dip()
                else:
                    assert step.xyz is not None
                    self._movl(*step.xyz)
                if path[step.op_index]["op"] == "up" or step.kind == "dip":
                    self._sync()
                    on_progress((step.op_index + 1) / len(path))
            self._sync()
            on_progress(1.0)
        except BaseException:
            self._after_abort()
            raise

    def _after_abort(self) -> None:
        """Tras un paro o un fallo: vaciar la cola y subir la pluma si el robot puede moverse."""
        was_stopped = self._stop.is_set()
        try:
            if not was_stopped:
                self._dashboard("ResetRobot()", check=False)
            self._dashboard("Continue()", check=False)
            move_port = self._ports[1]
            if self._move:
                self._move.close()  # descarta respuestas pendientes (p. ej. de un Sync interrumpido)
            self._move = _Channel(self.cfg.ip, move_port, self._connect_timeout)
            fb = self._feedback()
            if self.frame is None or fb.alarm or fb.mode == MODE_ERROR:
                log.error("no_se_puede_subir_la_pluma", extra={"mode": fb.mode, "alarm": fb.alarm})
                return
            self._stop.clear()
            x, y, z, _ = fb.pose
            if self._xyz is not None:  # el feedback puede ir ~8 ms por detrás de lo ya ordenado
                z = min(z, self._xyz[2])
            if z < self._z_up() - 0.5:
                self._movl(x, y, self._z_up())
                self._sync(20.0)
        except Exception:
            log.exception("lift_after_abort_failed")
