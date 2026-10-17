"""Servidor falso que imita al MG400 (puertos de dashboard, movimiento y feedback) en localhost."""

import re
import socketserver
import struct
import threading
import time

from app.services.robot.dobot_driver import FEEDBACK_SIZE, TEST_VALUE

_CMD = re.compile(rb"(\w+)\(([^)]*)\)")


def build_packet(
    mode: int, pose: tuple[float, float, float, float], *, alarm: bool = False, enabled: bool = True
) -> bytes:
    buf = bytearray(FEEDBACK_SIZE)
    struct.pack_into("<H", buf, 0, FEEDBACK_SIZE)
    struct.pack_into("<Q", buf, 24, mode)
    struct.pack_into("<Q", buf, 48, TEST_VALUE)
    x, y, z, r = pose
    struct.pack_into("<6d", buf, 624, x, y, z, 0.0, 0.0, r)
    buf[1026] = int(enabled)
    buf[1029] = int(alarm)
    return bytes(buf)


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class FakeMG400:
    def __init__(self, *, mode: int = 4, alarm: bool = False, pose=(300.0, 0.0, 50.0, 0.0)) -> None:  # type: ignore[no-untyped-def]
        self.mode, self.alarm, self.pose = mode, alarm, pose
        self.dashboard: list[str] = []
        self.motion: list[str] = []
        self.hold_sync = threading.Event()  # mientras esté activo, Sync() no responde
        self.sync_received = threading.Event()
        self.fail_movl_at: int | None = None  # n-ésimo MovL (desde 1) responde -20000
        self._movl_count = 0
        self._lock = threading.Lock()
        outer = self

        class Dashboard(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                outer._serve(self.request, outer._dashboard)

        class Motion(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                outer._serve(self.request, outer._motion)

        class Feedback(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                try:
                    while True:
                        self.request.sendall(
                            build_packet(outer.mode, outer.pose, alarm=outer.alarm)
                        )
                        time.sleep(0.01)
                except OSError:
                    return

        self._servers = [_Server(("127.0.0.1", 0), h) for h in (Dashboard, Motion, Feedback)]
        self.dashboard_port, self.move_port, self.feedback_port = (
            s.server_address[1] for s in self._servers
        )
        for s in self._servers:
            threading.Thread(target=s.serve_forever, daemon=True).start()

    # --- protocolo ---------------------------------------------------------------------------

    def _serve(self, sock, handler) -> None:  # type: ignore[no-untyped-def]
        buf = b""
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    return
                buf += chunk
                while (m := _CMD.search(buf)) is not None:
                    buf = buf[m.end() :]
                    name, args = m.group(1).decode(), m.group(2).decode()
                    code, value = handler(name, args)
                    sock.sendall(f"{code},{{{value}}},{name}({args});".encode())
        except OSError:
            return

    def _dashboard(self, name: str, args: str) -> tuple[int, str]:
        with self._lock:
            self.dashboard.append(f"{name}({args})")
        if name == "EnableRobot":
            self.mode = 5
        elif name == "RobotMode":
            return 0, str(self.mode)
        elif name == "GetErrorID":
            return 0, "[[1],[],[],[],[],[]]" if self.alarm else "[[],[],[],[],[],[]]"
        elif name == "ResetRobot":
            self.hold_sync.clear()
        return 0, ""

    def _motion(self, name: str, args: str) -> tuple[int, str]:
        with self._lock:
            self.motion.append(f"{name}({args})")
        if name == "MovL":
            self._movl_count += 1
            if self.fail_movl_at == self._movl_count:
                return -20000, ""
            x, y, z, r = (float(v) for v in args.split(","))
            self.pose = (x, y, z, r)
        elif name == "Sync":
            self.sync_received.set()
            while self.hold_sync.is_set():
                time.sleep(0.01)
        return 0, ""

    def movl(self) -> list[str]:
        return [c for c in self.motion if c.startswith("MovL")]

    def close(self) -> None:
        self.hold_sync.clear()
        for s in self._servers:
            s.shutdown()
            s.server_close()
