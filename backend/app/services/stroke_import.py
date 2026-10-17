"""Importación de trazos (línea central) a una caja de 1024×1024 con origen arriba-izquierda.

Fuentes (verificar licencia antes de redistribuir; ver README):
- Make Me a Hanzi `graphics.txt` → hanzi. Se usan los `medians` (línea central). Sus coordenadas
  tienen el origen abajo y la línea base en y=900, por lo que `y' = 900 - y`.
- KanjiVG → kana. Cada `<path>` ya es la línea central, en una caja de 109×109.

Cada trazo se re-muestrea a 12–30 puntos equiespaciados sobre una curva suave.
"""

import bisect
import gzip
import itertools
import json
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path
from typing import Any

Point = tuple[float, float]
Stroke = list[Point]

BOX = 1024.0
MIN_POINTS = 12
MAX_POINTS = 30
_UNITS_PER_POINT = 30.0  # un punto cada ~30 unidades de una caja de 1024
_MMAH_BASELINE = 900.0
_KANJIVG_BOX = 109.0

ZH_SOURCE = (
    "Make Me a Hanzi graphics.txt (https://github.com/skishore/makemeahanzi), derivado de "
    "Arphic PL KaitiM GB / UKai; Arphic Public License"
)
KANA_SOURCE = "KanjiVG {version} (https://kanjivg.tagaini.net) © Ulrich Apel; CC BY-SA 3.0"

_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "Z": 0}
_CURVE_STEPS = 16


def is_kana(char: str) -> bool:
    return "぀" <= char <= "ヿ"


# --- geometría -------------------------------------------------------------------------------


def _bezier(pts: list[Point], steps: int = _CURVE_STEPS) -> list[Point]:
    """Puntos de una Bézier de grado 2 o 3 (sin incluir el punto inicial)."""
    out: list[Point] = []
    for i in range(1, steps + 1):
        t = i / steps
        level = pts
        while len(level) > 1:
            level = [
                ((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1])
                for a, b in itertools.pairwise(level)
            ]
        out.append(level[0])
    return out


def parse_svg_path(d: str) -> Stroke:
    """Path SVG (M L H V C S Q T Z, absolutos y relativos) → polilínea densa."""
    tokens = _TOKEN.findall(d)
    pts: Stroke = []
    cur: Point = (0.0, 0.0)
    start = cur
    last_ctrl: Point | None = None
    cmd = ""
    i = 0
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                cur = start
                pts.append(cur)
                continue
        up = cmd.upper()
        n = _ARGS[up]
        a = [float(x) for x in tokens[i : i + n]]
        if len(a) < n:
            raise ValueError(f"path truncado: {d!r}")
        i += n
        rel = cmd.islower()
        ox, oy = cur if rel else (0.0, 0.0)
        new_ctrl: Point | None = None
        if up in "ML":
            cur = (a[0] + ox, a[1] + oy)
            pts.append(cur)
            if up == "M":
                start = cur
                cmd = "l" if rel else "L"  # pares siguientes de un M son líneas
        elif up == "H":
            cur = (a[0] + ox, cur[1])
            pts.append(cur)
        elif up == "V":
            cur = (cur[0], a[0] + oy)
            pts.append(cur)
        elif up in "CS":
            if up == "C":
                c1, c2, end = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy), (a[4] + ox, a[5] + oy)
            else:
                c1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_ctrl else cur
                c2, end = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy)
            pts += _bezier([cur, c1, c2, end])
            cur, new_ctrl = end, c2
        else:  # Q, T
            if up == "Q":
                c1, end = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy)
            else:
                c1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_ctrl else cur
                end = (a[0] + ox, a[1] + oy)
            pts += _bezier([cur, c1, end])
            cur, new_ctrl = end, c1
        last_ctrl = new_ctrl
    return pts


def catmull_rom(points: Stroke, steps: int = 8) -> Stroke:
    """Curva suave que pasa por todos los puntos (spline Catmull-Rom uniforme)."""
    if len(points) < 3:
        return list(points)
    out: Stroke = [points[0]]
    for i in range(len(points) - 1):
        p0 = points[max(i - 1, 0)]
        p1, p2 = points[i], points[i + 1]
        p3 = points[min(i + 2, len(points) - 1)]
        for s in range(1, steps + 1):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(
                tuple(  # type: ignore[arg-type]
                    0.5
                    * (
                        2 * p1[k]
                        + (-p0[k] + p2[k]) * t
                        + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                        + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3
                    )
                    for k in (0, 1)
                )
            )
    return out


def resample(points: Stroke) -> Stroke:
    """Re-muestrea a 12–30 puntos equiespaciados (según la longitud) conservando los extremos."""
    cum = [0.0]
    for a, b in itertools.pairwise(points):
        cum.append(cum[-1] + math.dist(a, b))
    total = cum[-1]
    n = max(MIN_POINTS, min(MAX_POINTS, round(total / _UNITS_PER_POINT)))
    if total == 0:
        return [points[0]] * n
    out: Stroke = []
    for i in range(n):
        target = total * i / (n - 1)
        j = min(max(bisect.bisect_right(cum, target) - 1, 0), len(points) - 2)
        seg = cum[j + 1] - cum[j]
        f = 0.0 if seg == 0 else (target - cum[j]) / seg
        a, b = points[j], points[j + 1]
        out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    out[0], out[-1] = points[0], points[-1]
    return out


def _round(stroke: Stroke) -> list[list[float]]:
    return [[round(x, 1), round(y, 1)] for x, y in stroke]


# --- fuentes ---------------------------------------------------------------------------------


def parse_mmah(path: Path, wanted: Iterable[str]) -> dict[str, list[list[list[float]]]]:
    """`graphics.txt` (una línea JSON por carácter) → {carácter: trazos normalizados}."""
    pending = set(wanted)
    found: dict[str, list[list[list[float]]]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not pending:
                break
            ch = line[14:15] if line.startswith('{"character":"') else ""
            if ch not in pending:
                continue
            data = json.loads(line)
            strokes = [
                resample(catmull_rom([(float(x), _MMAH_BASELINE - float(y)) for x, y in m]))
                for m in data["medians"]
            ]
            found[ch] = [_round(s) for s in strokes]
            pending.discard(ch)
    return found


_KANJI_ID = re.compile(r"^kvg:kanji_([0-9a-f]{5})$")
_STROKE_ID = re.compile(r"-s(\d+)$")


def parse_kanjivg(path: Path, wanted: Iterable[str]) -> dict[str, list[list[list[float]]]]:
    """`kanjivg.xml(.gz)` → {carácter: trazos normalizados}, en orden de trazo."""
    pending = set(wanted)
    found: dict[str, list[list[list[float]]]] = {}
    opener: Any = gzip.open if path.suffix == ".gz" else open
    scale = BOX / _KANJIVG_BOX
    with opener(path, "rb") as f:
        for _, elem in ET.iterparse(f, events=("end",)):
            if elem.tag != "kanji":
                continue
            m = _KANJI_ID.match(elem.get("id", ""))
            ch = chr(int(m.group(1), 16)) if m else ""
            if ch in pending:
                paths = [
                    (int(s.group(1)), p.get("d", ""))
                    for p in elem.iter("path")
                    if (s := _STROKE_ID.search(p.get("id", "")))
                ]
                found[ch] = [
                    _round(resample([(x * scale, y * scale) for x, y in parse_svg_path(d)]))
                    for _, d in sorted(paths)
                ]
                pending.discard(ch)
            elem.clear()
            if not pending:
                break
    return found


def build_glyphs(
    zh_chars: Iterable[str],
    kana_chars: Iterable[str],
    graphics_txt: Path,
    kanjivg: Path,
    kanjivg_version: str,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Devuelve (glifos, caracteres sin trazos)."""
    zh, kana = set(zh_chars), set(kana_chars)
    zh_found = parse_mmah(graphics_txt, zh)
    kana_found = parse_kanjivg(kanjivg, kana)
    glyphs: list[dict[str, Any]] = []
    for script, found, source in (
        ("zh", zh_found, ZH_SOURCE),
        ("ja_kana", kana_found, KANA_SOURCE.format(version=kanjivg_version)),
    ):
        for ch in sorted(found):
            glyphs.append(
                {
                    "char": ch,
                    "script": script,
                    "stroke_count": len(found[ch]),
                    "strokes": found[ch],
                    "source": source,
                }
            )
    return glyphs, (zh - set(zh_found)) | (kana - set(kana_found))
