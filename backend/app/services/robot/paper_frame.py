import math
from dataclasses import dataclass

MIN_SIDE_MM = 50.0
MAX_SKEW_DEG = 5.0
BOUNDS_TOLERANCE_MM = 2.0


@dataclass(frozen=True)
class PaperFrame:
    """Marco de la cartulina: milímetros de papel (x→derecha, y→abajo) → coordenadas del robot."""

    ox: float
    oy: float
    ux: tuple[float, float]  # vector unitario del eje x del papel, en el plano del robot
    uy: tuple[float, float]
    width: float  # medido entre las esquinas calibradas
    height: float
    z_paper: float

    @classmethod
    def from_points(
        cls,
        origin: tuple[float, float, float],
        x_axis: tuple[float, float, float],
        y_axis: tuple[float, float, float],
    ) -> "PaperFrame":
        vx = (x_axis[0] - origin[0], x_axis[1] - origin[1])
        vy = (y_axis[0] - origin[0], y_axis[1] - origin[1])
        width, height = math.hypot(*vx), math.hypot(*vy)
        if width < MIN_SIDE_MM or height < MIN_SIDE_MM:
            raise ValueError(
                f"Calibración inválida: la cartulina mide {width:.0f}×{height:.0f} mm "
                f"(mínimo {MIN_SIDE_MM:.0f} mm por lado). Revisa los puntos capturados."
            )
        ux, uy = (vx[0] / width, vx[1] / width), (vy[0] / height, vy[1] / height)
        angle = math.degrees(math.acos(max(-1.0, min(1.0, ux[0] * uy[0] + ux[1] * uy[1]))))
        if abs(angle - 90) > MAX_SKEW_DEG:
            raise ValueError(
                f"Calibración inválida: los ejes forman {angle:.0f}° y deberían ser perpendiculares "
                f"(±{MAX_SKEW_DEG:.0f}°). Vuelve a capturar las esquinas."
            )
        return cls(origin[0], origin[1], ux, uy, width, height, origin[2])

    def to_robot(self, px: float, py: float) -> tuple[float, float]:
        return (
            self.ox + px * self.ux[0] + py * self.uy[0],
            self.oy + px * self.ux[1] + py * self.uy[1],
        )

    def check_inside(self, px: float, py: float) -> None:
        tol = BOUNDS_TOLERANCE_MM
        if not (-tol <= px <= self.width + tol and -tol <= py <= self.height + tol):
            raise ValueError(
                f"El punto ({px:.0f}, {py:.0f}) mm queda fuera de la cartulina calibrada "
                f"({self.width:.0f}×{self.height:.0f} mm). Usa un papel más pequeño en la "
                "disposición o vuelve a calibrar."
            )
