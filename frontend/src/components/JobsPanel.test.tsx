import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Job } from "../api/types";
import { DEFAULT_LAYOUT } from "../lib/layout";
import { apiError, mockApi } from "../test/mockApi";
import { JobsPanel } from "./JobsPanel";

const job = (over: Partial<Job> = {}): Job => ({
  id: "j1",
  request_id: "r1",
  script: "zh",
  text: "卡洛斯",
  status: "draft",
  progress: 0,
  layout: DEFAULT_LAYOUT,
  created_at: "2026-10-16T12:00:00Z",
  started_at: null,
  finished_at: null,
  error: null,
  estimated_seconds: 80,
  ...over,
});

afterEach(() => vi.unstubAllGlobals());

describe("JobsPanel", () => {
  it("lleva un trabajo de borrador a terminado con el progreso visible", async () => {
    // El servidor simulado avanza un paso por cada consulta de la lista.
    const steps = [
      job({ status: "queued" }),
      job({ status: "running", progress: 0.4 }),
      job({ status: "running", progress: 0.8 }),
      job({ status: "done", progress: 1 }),
    ];
    let current = job();
    const api = mockApi({
      "GET /api/jobs": () => {
        const out = [current];
        if (current.status !== "draft" && current.status !== "done") current = steps.shift() ?? current;
        return out;
      },
      "POST /api/jobs/j1/start": () => {
        current = steps.shift()!;
        return current;
      },
    });
    const user = userEvent.setup();
    render(<JobsPanel pollMs={20} />);

    const item = await screen.findByRole("listitem", { name: "Trabajo 卡洛斯" });
    expect(within(item).getByText("Borrador")).toBeInTheDocument();
    expect(within(item).queryByRole("progressbar")).not.toBeInTheDocument();

    await user.click(within(item).getByRole("button", { name: "Iniciar" }));
    expect(api.callsTo("POST /api/jobs/j1/start")).toHaveLength(1);

    const bar = () => screen.getByRole("progressbar", { name: "Progreso de 卡洛斯" });
    await waitFor(() => expect(bar()).toHaveAttribute("aria-valuenow", "40"));
    await waitFor(() => expect(bar()).toHaveAttribute("aria-valuenow", "80"));
    await waitFor(() => expect(within(item).getByText("Terminado")).toBeInTheDocument());
    expect(bar()).toHaveAttribute("aria-valuenow", "100");
    expect(screen.queryByRole("button", { name: "Cancelar" })).not.toBeInTheDocument();
  });

  it("«Probar en el aire» inicia el trabajo en modo de prueba, sin tocar el papel", async () => {
    const api = mockApi({
      "GET /api/jobs": () => [job()],
      "POST /api/jobs/j1/start": () => job({ status: "queued" }),
    });
    const user = userEvent.setup();
    render(<JobsPanel pollMs={20} />);
    await user.click(await screen.findByRole("button", { name: "Probar en el aire" }));
    const call = api.callsTo("POST /api/jobs/j1/start")[0];
    expect(call.search.get("dry_run")).toBe("true");

    await user.click(await screen.findByRole("button", { name: "Cancelar" }));
  });

  it("cancela un trabajo en curso", async () => {
    let current = job({ status: "running", progress: 0.3 });
    const api = mockApi({
      "GET /api/jobs": () => [current],
      "POST /api/jobs/j1/cancel": () => {
        current = job({ status: "cancelled" });
        return current;
      },
    });
    const user = userEvent.setup();
    render(<JobsPanel pollMs={20} />);
    await user.click(await screen.findByRole("button", { name: "Cancelar" }));
    expect(api.callsTo("POST /api/jobs/j1/cancel")).toHaveLength(1);
    expect(await screen.findByText("Cancelado")).toBeInTheDocument();
  });

  it("no consulta en bucle cuando no hay nada activo", async () => {
    const api = mockApi({ "GET /api/jobs": () => [job({ status: "done", progress: 1 })] });
    render(<JobsPanel pollMs={10} />);
    await screen.findByText("Terminado");
    await new Promise((r) => setTimeout(r, 120));
    expect(api.callsTo("GET /api/jobs")).toHaveLength(1);
  });

  it("muestra el error del trabajo fallido y los estados vacío y de error", async () => {
    const api = mockApi({
      "GET /api/jobs": () => [job({ status: "failed", error: "El robot no responde." })],
    });
    const { unmount } = render(<JobsPanel pollMs={20} />);
    expect(await screen.findByText("Fallido")).toBeInTheDocument();
    expect(screen.getByText("El robot no responde.")).toBeInTheDocument();
    unmount();

    api.on("GET /api/jobs", () => []);
    const second = render(<JobsPanel pollMs={20} />);
    expect(await screen.findByText(/No hay trabajos todavía/)).toBeInTheDocument();
    second.unmount();

    api.on("GET /api/jobs", () => apiError("internal_error", "Error interno del servidor.", 500));
    render(<JobsPanel pollMs={20} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Error interno del servidor.");
  });

  it("muestra el error si falla iniciar el trabajo", async () => {
    mockApi({
      "GET /api/jobs": () => [job()],
      "POST /api/jobs/j1/start": () => apiError("invalid_state", "Solo se pueden iniciar borradores.", 409),
    });
    const user = userEvent.setup();
    render(<JobsPanel pollMs={20} />);
    await user.click(await screen.findByRole("button", { name: "Iniciar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Solo se pueden iniciar borradores.");
  });

  it("resalta el trabajo recién creado", async () => {
    mockApi({ "GET /api/jobs": () => [job(), job({ id: "j2", text: "アナ", script: "ja" })] });
    render(<JobsPanel highlight="j2" />);
    const item = await screen.findByRole("listitem", { name: "Trabajo アナ" });
    expect(item.className).toContain("border-indigo-700");
    expect(screen.getByRole("listitem", { name: "Trabajo 卡洛斯" }).className).not.toContain("border-indigo-700");
  });
});
