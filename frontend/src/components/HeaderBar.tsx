import { useEffect, useState } from "react";
import { getHealth } from "../api/client";

function toggleFullscreen() {
  if (document.fullscreenElement) void document.exitFullscreen();
  else void document.documentElement.requestFullscreen?.();
}

const LINKS = [
  ["#/", "Convertir"],
  ["#/history", "Historial"],
  ["#/jobs", "Cola de trabajos"],
  ["#/admin", "Administración"],
  ["#/robot", "Robot"],
] as const;

export function HeaderBar() {
  const [health, setHealth] = useState("comprobando…");

  useEffect(() => {
    getHealth()
      .then((h) => setHealth(h.status.toUpperCase()))
      .catch(() => setHealth("SIN CONEXIÓN"));
  }, []);

  return (
    <header className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-4xl font-extrabold">Nombres Pincel</h1>
        <div className="flex items-center gap-4 text-lg">
          <span>Servidor: {health}</span>
          <button
            type="button"
            onClick={toggleFullscreen}
            className="min-h-12 rounded-xl border-4 border-slate-900 px-4 text-lg font-semibold focus:outline-none focus:ring-4 focus:ring-indigo-400"
          >
            Pantalla completa
          </button>
        </div>
      </div>
      <nav aria-label="Secciones" className="flex flex-wrap gap-2">
        {LINKS.map(([href, label]) => (
          <a
            key={href}
            href={href}
            className="min-h-12 rounded-xl bg-slate-900 px-4 py-3 text-lg font-semibold text-white focus:outline-none focus:ring-4 focus:ring-indigo-400"
          >
            {label}
          </a>
        ))}
      </nav>
    </header>
  );
}
