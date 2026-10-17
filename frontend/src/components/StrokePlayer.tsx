import { useEffect, useMemo, useRef, useState } from "react";
import { partialStrokes, strokeLength, type Stroke } from "../lib/strokeProgress";

/** Velocidad base de dibujo (mm/s), igual que la que usa el backend para estimar tiempos. */
export const BASE_SPEED_MM_S = 25;

interface Props {
  strokes: Stroke[];
  /** Tamaño del papel en mm: es el `viewBox` del SVG. */
  width: number;
  height: number;
  speed?: number;
  loop?: boolean;
}

const asPoints = (s: Stroke) => s.map(([x, y]) => `${x},${y}`).join(" ");

/** Anima el orden de trazos: dibuja la ruta con la pluma abajo, con pausa y reinicio. */
export function StrokePlayer({ strokes, width, height, speed = 1, loop = false }: Props) {
  const total = useMemo(() => strokes.reduce((sum, s) => sum + strokeLength(s), 0), [strokes]);
  const [drawn, setDrawn] = useState(0);
  const [playing, setPlaying] = useState(true);
  const drawnRef = useRef(0);

  useEffect(() => {
    drawnRef.current = 0;
    setDrawn(0);
    setPlaying(true);
  }, [strokes]);

  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let last: number | null = null;
    const tick = (now: number) => {
      if (last !== null) {
        let next = drawnRef.current + ((now - last) / 1000) * BASE_SPEED_MM_S * speed;
        if (next >= total) {
          if (loop) {
            next = 0;
          } else {
            drawnRef.current = total;
            setDrawn(total);
            setPlaying(false);
            return;
          }
        }
        drawnRef.current = next;
        setDrawn(next);
      }
      last = now;
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, loop, total]);

  function restart() {
    drawnRef.current = 0;
    setDrawn(0);
    setPlaying(true);
  }

  function togglePlay() {
    if (!playing && drawnRef.current >= total) restart();
    else setPlaying((p) => !p);
  }

  const done = partialStrokes(strokes, drawn);
  const lastStroke = done[done.length - 1];
  const tip = lastStroke?.[lastStroke.length - 1];
  const finished = total > 0 && drawn >= total;
  const percent = total > 0 ? Math.round((drawn / total) * 100) : 0;

  return (
    <div className="space-y-3">
      <svg
        role="img"
        aria-label="Vista previa de trazos"
        data-drawn={drawn.toFixed(1)}
        viewBox={`0 0 ${width} ${height}`}
        className="mx-auto max-h-[60vh] w-full rounded-xl border-4 border-slate-900 bg-white"
      >
        <g fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.4}>
          <g stroke="#cbd5e1" data-testid="guide">
            {strokes.map((s, i) => (
              <polyline key={i} points={asPoints(s)} />
            ))}
          </g>
          <g stroke="#0f172a" data-testid="ink">
            {done.map((s, i) => (
              <polyline key={i} points={asPoints(s)} />
            ))}
          </g>
        </g>
        {tip && !finished && <circle cx={tip[0]} cy={tip[1]} r={1.8} fill="#b91c1c" />}
      </svg>
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={togglePlay} className={BTN}>
          {playing ? "Pausar" : finished ? "Repetir" : "Reproducir"}
        </button>
        <button type="button" onClick={restart} className={BTN}>
          Reiniciar
        </button>
        <span className="text-lg" role="status">
          {finished ? "Terminado" : playing ? "Dibujando…" : "En pausa"} · {percent}%
        </span>
      </div>
    </div>
  );
}

const BTN =
  "min-h-14 rounded-xl border-4 border-slate-900 px-5 text-xl font-semibold focus:outline-none focus:ring-4 focus:ring-indigo-400";
