export type Stroke = number[][];

export function strokeLength(stroke: Stroke): number {
  let total = 0;
  for (let i = 1; i < stroke.length; i++) {
    total += Math.hypot(stroke[i][0] - stroke[i - 1][0], stroke[i][1] - stroke[i - 1][1]);
  }
  return total;
}

/** Trazos (o parte de ellos) que ya se dibujaron cuando se llevan `drawn` mm de pluma abajo. */
export function partialStrokes(strokes: Stroke[], drawn: number): Stroke[] {
  const out: Stroke[] = [];
  let left = drawn;
  for (const stroke of strokes) {
    if (left <= 0) break;
    const len = strokeLength(stroke);
    if (left >= len) {
      out.push(stroke);
      left -= len;
      continue;
    }
    const part: Stroke = [stroke[0]];
    for (let i = 1; i < stroke.length && left > 0; i++) {
      const [x0, y0] = stroke[i - 1];
      const [x1, y1] = stroke[i];
      const seg = Math.hypot(x1 - x0, y1 - y0);
      if (seg <= left) {
        part.push(stroke[i]);
        left -= seg;
      } else {
        const f = left / seg;
        part.push([x0 + (x1 - x0) * f, y0 + (y1 - y0) * f]);
        left = 0;
      }
    }
    out.push(part);
    break;
  }
  return out;
}
