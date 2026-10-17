import { useCallback, useEffect, useMemo, useState } from "react";
import { robotApi } from "../api/client";
import type { PointName, RobotConfig, RobotStatus, Xyz } from "../api/types";
import { BTN, errorText, FIELD, LABEL, PRIMARY } from "../components/admin/ui";
import { PageShell } from "../components/PageShell";

const STEPS: { point: PointName; title: string; help: string }[] = [
  {
    point: "origin",
    title: "1. Esquina superior izquierda",
    help: "Con el brazo en modo arrastre, lleva la punta del lápiz a tocar esta esquina de la cartulina.",
  },
  {
    point: "x_axis",
    title: "2. Esquina superior derecha",
    help: "Toca la esquina superior derecha: define el ancho de la cartulina.",
  },
  {
    point: "y_axis",
    title: "3. Esquina inferior izquierda",
    help: "Toca la esquina inferior izquierda: define el alto de la cartulina.",
  },
  {
    point: "ink",
    title: "4. Tintero (solo con pincel)",
    help: "Toca con la punta la superficie de la tinta. No hace falta en el modo lápiz.",
  },
];

const num = (v: number | string) => (v === "" ? 0 : Number(v));
const dist = (a: Xyz, b: Xyz) => Math.hypot(a[0] - b[0], a[1] - b[1]);

export function RobotPage({ pollMs = 2000 }: { pollMs?: number }) {
  const api = useMemo(() => robotApi(), []);
  const [cfg, setCfg] = useState<RobotConfig | null>(null);
  const [status, setStatus] = useState<RobotStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [linkError, setLinkError] = useState<string | null>(null); // se limpia solo al reconectar

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await api.status());
      setLinkError(null);
    } catch (e) {
      setLinkError(errorText(e));
    }
  }, [api]);

  useEffect(() => {
    api.getConfig().then(setCfg).catch((e: unknown) => setError(errorText(e)));
  }, [api]);

  useEffect(() => {
    void refreshStatus();
    const id = setInterval(() => void refreshStatus(), pollMs);
    return () => clearInterval(id);
  }, [refreshStatus, pollMs]);

  const set = <K extends keyof RobotConfig>(key: K, value: RobotConfig[K]) =>
    setCfg((c) => (c ? { ...c, [key]: value } : c));

  async function save() {
    if (!cfg) return;
    try {
      setCfg(await api.saveConfig(cfg));
      setError(null);
      setNotice("Ajustes guardados.");
      void refreshStatus();
    } catch (e) {
      setNotice(null);
      setError(errorText(e));
    }
  }

  async function capture(point: PointName) {
    try {
      setCfg(await api.capture(point));
      setError(null);
      setNotice(null);
    } catch (e) {
      setError(errorText(e));
    }
  }

  async function act(action: () => Promise<RobotStatus>, confirmText: string, done: string) {
    if (!window.confirm(confirmText)) return;
    try {
      setStatus(await action());
      setError(null);
      setNotice(done);
    } catch (e) {
      setNotice(null);
      setError(errorText(e));
    }
  }

  const size =
    cfg?.origin && cfg.x_axis && cfg.y_axis
      ? `${dist(cfg.origin, cfg.x_axis).toFixed(0)} × ${dist(cfg.origin, cfg.y_axis).toFixed(0)} mm`
      : null;
  // Los botones dependen del driver GUARDADO en el servidor, no del desplegable sin guardar.
  const live = status?.driver === "dobot";
  const unsaved = cfg !== null && status !== null && cfg.driver !== status.driver;

  return (
    <PageShell>
      <h2 className="text-3xl font-bold">Robot</h2>
      {(linkError ?? error) && (
        <p role="alert" className="rounded-xl border-4 border-red-800 bg-red-50 p-4 text-xl font-semibold text-red-900">
          {linkError ?? error}
        </p>
      )}
      {notice && <p role="status" className="text-lg font-semibold text-emerald-900">{notice}</p>}

      <section aria-label="Estado" className="space-y-2 rounded-2xl border-4 border-slate-900 p-4">
        <h3 className="text-xl font-bold">Estado</h3>
        {status ? (
          status.reachable ? (
            <p className="text-lg">
              {status.driver === "mock" ? (
                <>
                  <strong>Simulador</strong> · el brazo no se mueve
                </>
              ) : (
                <>
                  <strong>Dobot MG400 ({cfg?.ip})</strong>
                  {" · "}
                  <span className={status.alarm ? "font-bold text-red-800" : ""}>{status.mode_name}</span>
                </>
              )}
              {status.pose && <> · pose x={status.pose[0].toFixed(1)} y={status.pose[1].toFixed(1)} z={status.pose[2].toFixed(1)}</>}
            </p>
          ) : (
            <p className="text-lg font-semibold text-red-800">{status.error}</p>
          )
        ) : (
          <p className="text-lg">Consultando…</p>
        )}
        {unsaved && (
          <p role="note" className="text-lg font-semibold text-amber-900">
            Cambiaste el driver pero no lo guardaste: pulsa «Guardar ajustes» para aplicarlo.
          </p>
        )}
        {live && status?.reachable && (
          <div className="flex flex-wrap gap-3 pt-2">
            <button
              type="button"
              className={BTN}
              disabled={status.mode !== 4}
              onClick={() =>
                void act(
                  api.enable,
                  "Se habilitarán los motores del brazo (no se mueve). ¿La zona está despejada y tienes el paro de emergencia al alcance?",
                  "Robot habilitado.",
                )
              }
            >
              Habilitar robot
            </button>
            {status.mode === 6 ? (
              <button
                type="button"
                className={PRIMARY}
                onClick={() => void act(() => api.drag(false), "Se detendrá el modo arrastre: el brazo volverá a sostenerse solo. ¿Continuar?", "Modo arrastre detenido.")}
              >
                Detener modo arrastre
              </button>
            ) : (
              <button
                type="button"
                className={BTN}
                disabled={status.mode !== 5}
                onClick={() =>
                  void act(
                    () => api.drag(true),
                    "El brazo quedará LIBRE para moverlo a mano y puede caer por su peso. Sujétalo con la mano antes de continuar. ¿Iniciar el modo arrastre?",
                    "Modo arrastre activo: guía la punta hasta cada esquina y pulsa «Capturar».",
                  )
                }
              >
                Iniciar modo arrastre
              </button>
            )}
          </div>
        )}
      </section>

      {cfg && (
        <>
          <section aria-label="Conexión" className="space-y-3 rounded-2xl border-4 border-slate-900 p-4">
            <h3 className="text-xl font-bold">Conexión</h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <label className={LABEL}>
                Driver
                <select className={`${FIELD} w-full`} value={cfg.driver} onChange={(e) => set("driver", e.target.value as RobotConfig["driver"])}>
                  <option value="mock">Simulador (no mueve nada)</option>
                  <option value="dobot">Dobot MG400 (TCP/IP)</option>
                </select>
              </label>
              <label className={LABEL}>
                IP del robot
                <input className={`${FIELD} w-full`} value={cfg.ip} onChange={(e) => set("ip", e.target.value)} />
              </label>
              <label className={LABEL}>
                User / Tool
                <span className="flex gap-2">
                  <input aria-label="Sistema de usuario" type="number" min={0} max={9} className={`${FIELD} w-24`} value={cfg.user} onChange={(e) => set("user", num(e.target.value))} />
                  <input aria-label="Sistema de herramienta" type="number" min={0} max={9} className={`${FIELD} w-24`} value={cfg.tool} onChange={(e) => set("tool", num(e.target.value))} />
                </span>
              </label>
            </div>
            <p className="text-base text-slate-700">
              LAN1 del MG400: 192.168.1.6 · LAN2: 192.168.2.6. Tu equipo debe estar en la misma red.
            </p>
          </section>

          <section aria-label="Calibración" className="space-y-3 rounded-2xl border-4 border-slate-900 p-4">
            <h3 className="text-xl font-bold">Calibración de la cartulina</h3>
            {!live && (
              <p className="text-lg text-amber-900">
                Elige el driver «Dobot MG400», pulsa «Guardar ajustes» y luego captura los puntos.
              </p>
            )}
            <ol className="space-y-3">
              {STEPS.map((s) => {
                const value = cfg[s.point];
                return (
                  <li key={s.point} className="flex flex-wrap items-center gap-4 rounded-xl border-2 border-slate-900 p-3">
                    <div className="min-w-64 flex-1">
                      <strong className="text-lg">{s.title}</strong>
                      <p className="text-base text-slate-700">{s.help}</p>
                    </div>
                    <span className="w-72 text-base" aria-label={`Valor de ${s.title}`}>
                      {value ? `x=${value[0]} y=${value[1]} z=${value[2]}` : "Sin capturar"}
                    </span>
                    <button type="button" className={BTN} disabled={!live} onClick={() => void capture(s.point)} aria-label={`Capturar ${s.title}`}>
                      Capturar
                    </button>
                  </li>
                );
              })}
            </ol>
            <p className="text-lg" aria-label="Estado de la calibración">
              {size ? (
                <>Cartulina calibrada: <strong>{size}</strong>. Los trabajos deben caber en ese tamaño.</>
              ) : (
                "Falta calibrar: captura los pasos 1 a 3."
              )}
            </p>
          </section>

          <form
            aria-label="Ajustes de escritura"
            className="space-y-3 rounded-2xl border-4 border-slate-900 p-4"
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            <h3 className="text-xl font-bold">Escritura</h3>
            <label className="flex items-center gap-3 text-lg font-semibold">
              <input type="checkbox" className="h-6 w-6" checked={cfg.pencil_mode} onChange={(e) => set("pencil_mode", e.target.checked)} />
              Modo lápiz (sin tinta y sin presionar): úsalo en la primera prueba
            </label>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {(
                [
                  ["speed_factor", "Velocidad global (%)", 1, 100],
                  ["speed_l", "Velocidad lineal (%)", 1, 100],
                  ["accel_l", "Aceleración (%)", 1, 100],
                  ["cp", "Suavizado CP (%)", 0, 100],
                  ["lift_mm", "Altura de la pluma arriba (mm)", 2, 50],
                  ["press_depth_mm", "Presión máxima: bajada (mm)", 0, 10],
                  ["dip_depth_mm", "Profundidad en la tinta (mm)", 0, 30],
                  ["dip_dwell_s", "Espera en la tinta (s)", 0, 10],
                ] as const
              ).map(([key, label, min, max]) => (
                <label key={key} className={LABEL}>
                  {label}
                  <input type="number" min={min} max={max} step="any" className={`${FIELD} w-full`} value={cfg[key]} onChange={(e) => set(key, num(e.target.value))} />
                </label>
              ))}
            </div>
            <button type="submit" className={PRIMARY}>
              Guardar ajustes
            </button>
          </form>

          <section aria-label="Seguridad" className="space-y-1 rounded-2xl border-4 border-amber-700 bg-amber-50 p-4 text-lg">
            <h3 className="text-xl font-bold">Antes de la primera escritura</h3>
            <ol className="list-decimal space-y-1 pl-6">
              <li>Ten a mano el paro de emergencia físico y despeja la zona de trabajo.</li>
              <li>Calibra la cartulina y empieza con velocidades bajas y el modo lápiz.</li>
              <li>En «Cola de trabajos» usa «Probar en el aire»: recorre todo sin tocar el papel.</li>
              <li>Cuando el recorrido sea correcto, escribe con lápiz; el pincel y la tinta van al final.</li>
            </ol>
            <p>Las alarmas (colisión, etc.) las revisa y limpia una persona en DobotStudio: el sistema no las borra solo.</p>
          </section>
        </>
      )}
    </PageShell>
  );
}
