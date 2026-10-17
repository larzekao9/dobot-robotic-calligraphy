"""Texto elegido → ruta de trazos para el robot (pipeline de la sección 9.1 del plan).

Glifos (caja 1024) → colocación en la cartulina según el `Layout` → milímetros →
simplificación (Douglas-Peucker) → lista de comandos con pluma arriba/abajo y presión.

Los caracteres se escriben en orden de lectura y los trazos de cada carácter conservan su
orden original; no se reordena nada (en una línea el recorrido ya es mínimo).
"""

import itertools
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.errors import AppError
from app.schemas.jobs import Layout

GLYPH_BOX = 1024.0
SIMPLIFY_EPSILON_MM = 0.15
PRESSURE_START = 0.8  # más presión al empezar el trazo…
PRESSURE_END = 0.3  # …y menos al terminar
DRAW_SPEED_MM_S = 25.0
TRAVEL_SPEED_MM_S = 120.0
PEN_MOVE_S = 0.25
DIP_S = 4.0

Point = tuple[float, float]
Command = dict[str, Any]
GlyphLookup = Callable[[str], list[list[list[float]]]]
_SEPARATORS = re.compile(r"[·・\s]+")


@dataclass(frozen=True)
class PlacedChar:
    char: str
    strokes: list[list[Point]]  # milímetros sobre la cartulina


def split_words(text: str) -> list[str]:
    return [w for w in _SEPARATORS.split(text) if w]


def _extent(n: int, size: float, gap: float) -> float:
    return n * size + (n - 1) * gap


MIN_CHAR_SIZE_MM = 10.0


def fit_char_size(words: list[str], layout: Layout) -> float:
    """Tamaño de carácter con el que el texto cabe en el papel (el pedido, o menor con `auto_fit`)."""
    width, height = layout.paper_size()
    m, s, g = layout.margin_mm, layout.char_size_mm, layout.spacing_mm
    longest, n_words = max(len(w) for w in words), len(words)
    horizontal = layout.orientation == "horizontal"
    along, across = (longest, n_words) if horizontal else (n_words, longest)
    avail_w, avail_h = width - 2 * m, height - 2 * m
    need_w, need_h = _extent(along, s, g), _extent(across, s, g)
    if need_w <= avail_w + 1e-6 and need_h <= avail_h + 1e-6:
        return s
    fitted = min((avail_w - (along - 1) * g) / along, (avail_h - (across - 1) * g) / across)
    if layout.auto_fit and fitted >= MIN_CHAR_SIZE_MM:
        return round(fitted - 0.005, 2)
    raise AppError(
        "layout_overflow",
        f"El texto no cabe en el papel: necesita {need_w:.0f}×{need_h:.0f} mm y hay "
        f"{avail_w:.0f}×{avail_h:.0f} mm disponibles. Reduce el tamaño de los caracteres "
        "o usa un papel más grande.",
        422,
    )


def place_text(text: str, glyphs: GlyphLookup, layout: Layout) -> list[PlacedChar]:
    """Coloca cada palabra en su línea (horizontal) o columna (vertical, de derecha a izquierda)."""
    words = split_words(text)
    if not words:
        raise AppError("empty_text", "No hay caracteres para escribir.", 422)
    width, height = layout.paper_size()
    s, g = fit_char_size(words, layout), layout.spacing_mm
    horizontal = layout.orientation == "horizontal"
    scale = s / GLYPH_BOX
    placed: list[PlacedChar] = []
    for i, word in enumerate(words):
        for j, ch in enumerate(word):
            if horizontal:
                x = (width - _extent(len(word), s, g)) / 2 + j * (s + g)
                y = (height - _extent(len(words), s, g)) / 2 + i * (s + g)
            else:
                x = (width - _extent(len(words), s, g)) / 2 + (len(words) - 1 - i) * (s + g)
                y = (height - _extent(len(word), s, g)) / 2 + j * (s + g)
            strokes = [[(x + px * scale, y + py * scale) for px, py in st] for st in glyphs(ch)]
            placed.append(PlacedChar(ch, strokes))
    return placed


def _dist_to_segment(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def simplify(points: list[Point], epsilon: float = SIMPLIFY_EPSILON_MM) -> list[Point]:
    """Douglas-Peucker iterativo; conserva siempre el primer y el último punto."""
    n = len(points)
    if n < 3:
        return list(points)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        far, far_d = -1, epsilon
        for i in range(a + 1, b):
            d = _dist_to_segment(points[i], points[a], points[b])
            if d > far_d:
                far, far_d = i, d
        if far >= 0:
            keep[far] = True
            stack += [(a, far), (far, b)]
    return [p for p, k in zip(points, keep, strict=True) if k]


def build_commands(placed: list[PlacedChar], layout: Layout) -> list[Command]:
    cmds: list[Command] = []
    for idx, char in enumerate(placed):
        for k, stroke in enumerate(char.strokes):
            pts = simplify(stroke)
            if k == 0 and idx % layout.dip_every_chars == 0:
                cmds.append({"op": "dip"})
            cmds.append(
                {"op": "move", "x": round(pts[0][0], 2), "y": round(pts[0][1], 2), "z": "up"}
            )
            cmds.append({"op": "down"})
            total = sum(math.dist(a, b) for a, b in itertools.pairwise(pts))
            run = 0.0
            for a, b in itertools.pairwise(pts):
                run += math.dist(a, b)
                frac = run / total if total else 1.0
                pressure = PRESSURE_START + (PRESSURE_END - PRESSURE_START) * frac
                cmds.append(
                    {
                        "op": "line",
                        "x": round(b[0], 2),
                        "y": round(b[1], 2),
                        "pressure": round(pressure, 2),
                    }
                )
            cmds.append({"op": "up"})
    return cmds


def command_durations(cmds: list[Command]) -> list[float]:
    """Segundos que tarda cada comando (el robot parte desde el origen del papel)."""
    pos: Point = (0.0, 0.0)
    out: list[float] = []
    for c in cmds:
        op = c["op"]
        if op in ("move", "line"):
            target = (float(c["x"]), float(c["y"]))
            speed = TRAVEL_SPEED_MM_S if op == "move" else DRAW_SPEED_MM_S
            out.append(math.dist(pos, target) / speed)
            pos = target
        elif op == "dip":
            out.append(DIP_S)
        else:  # up / down
            out.append(PEN_MOVE_S)
    return out


def estimate_seconds(cmds: list[Command]) -> float:
    return sum(command_durations(cmds))


def air_path(cmds: list[Command]) -> list[Command]:
    """Misma ruta con la pluma siempre arriba: para comprobar alcance y disposición sin tocar el papel."""
    return [
        {"op": "move", "x": c["x"], "y": c["y"], "z": "up"} if c["op"] == "line" else c
        for c in cmds
        if c["op"] in ("move", "line")
    ]


def preview_strokes(cmds: list[Command]) -> list[list[list[float]]]:
    """Polilíneas con la pluma abajo, en el orden en que se escriben."""
    strokes: list[list[list[float]]] = []
    pos: list[float] = [0.0, 0.0]
    current: list[list[float]] | None = None
    for c in cmds:
        op = c["op"]
        if op == "move":
            pos = [c["x"], c["y"]]
        elif op == "down":
            current = [list(pos)]
        elif op == "line" and current is not None:
            pos = [c["x"], c["y"]]
            current.append(list(pos))
        elif op == "up" and current is not None:
            strokes.append(current)
            current = None
    return strokes
