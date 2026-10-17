import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PathPreview } from "../api/types";
import { DEFAULT_LAYOUT } from "../lib/layout";
import { apiError, mockApi } from "../test/mockApi";
import { PreviewPage } from "./PreviewPage";

const PREVIEW: PathPreview = {
  text: "卡洛斯",
  script: "zh",
  layout: DEFAULT_LAYOUT,
  paper_width_mm: 210,
  paper_height_mm: 297,
  char_size_mm: 40,
  strokes: [[[10, 10], [60, 10]], [[70, 10], [120, 10]], [[130, 10], [180, 10]]],
  stroke_count: 3,
  char_count: 3,
  estimated_seconds: 80,
};

const params = (q = "request=r1&script=zh&rank=1") => new URLSearchParams(q);
let api: ReturnType<typeof mockApi>;

beforeEach(() => {
  window.location.hash = "";
  api = mockApi({ "POST /api/jobs/preview": () => PREVIEW });
});
afterEach(() => vi.unstubAllGlobals());

describe("PreviewPage", () => {
  it("muestra el reproductor y el tiempo estimado", async () => {
    render(<PreviewPage params={params()} />);
    expect(await screen.findByRole("img", { name: "Vista previa de trazos" })).toBeInTheDocument();
    expect(screen.getByTestId("estimate")).toHaveTextContent("1 min 20 s");
    expect(screen.getByTestId("estimate")).toHaveTextContent("3 caracteres, 3 trazos");
    expect(api.callsTo("POST /api/jobs/preview")[0].body).toEqual({
      request_id: "r1",
      script: "zh",
      rank: 1,
      layout: DEFAULT_LAYOUT,
    });
  });

  it("recalcula con la orientación, el tamaño y el papel elegidos", async () => {
    const user = userEvent.setup();
    render(<PreviewPage params={params()} />);
    await screen.findByRole("img");

    await user.selectOptions(screen.getByLabelText("Orientación"), "vertical");
    await user.selectOptions(screen.getByLabelText("Papel"), "A5");
    await waitFor(() => {
      const calls = api.callsTo("POST /api/jobs/preview");
      const last = calls[calls.length - 1].body as { layout: typeof DEFAULT_LAYOUT };
      expect(last.layout.orientation).toBe("vertical");
      expect(last.layout.paper).toBe("A5");
    });
  });

  it("permite un papel personalizado", async () => {
    const user = userEvent.setup();
    render(<PreviewPage params={params()} />);
    await screen.findByRole("img");
    await user.selectOptions(screen.getByLabelText("Papel"), "custom");
    expect(screen.getByLabelText("Ancho (mm)")).toHaveValue(200);
    expect(screen.getByLabelText("Alto (mm)")).toHaveValue(300);
    await waitFor(() => {
      const calls = api.callsTo("POST /api/jobs/preview");
      const last = calls[calls.length - 1].body as { layout: typeof DEFAULT_LAYOUT };
      expect([last.layout.paper, last.layout.width_mm, last.layout.height_mm]).toEqual(["custom", 200, 300]);
    });
  });

  it("avisa cuando los caracteres se reducen para caber", async () => {
    api.on("POST /api/jobs/preview", () => ({ ...PREVIEW, char_size_mm: 25 }));
    render(<PreviewPage params={params()} />);
    expect(await screen.findByText(/se reducen a 25 mm/)).toBeInTheDocument();
  });

  it("muestra el error de la API (texto que no cabe)", async () => {
    api.on("POST /api/jobs/preview", () => apiError("layout_overflow", "El texto no cabe en el papel.", 422));
    render(<PreviewPage params={params()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("El texto no cabe en el papel.");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preparar para escribir" })).toBeDisabled();
  });

  it("crea el trabajo con la disposición actual y abre la cola", async () => {
    api.on("POST /api/jobs", () => ({ id: "job-9" }));
    const user = userEvent.setup();
    render(<PreviewPage params={params("request=r1&script=ja&rank=1")} />);
    await screen.findByRole("img");
    await user.selectOptions(screen.getByLabelText("Orientación"), "vertical");
    await screen.findByRole("img");
    await waitFor(() => expect(api.callsTo("POST /api/jobs/preview")).toHaveLength(2));

    await user.click(screen.getByRole("button", { name: "Preparar para escribir" }));
    await waitFor(() => expect(window.location.hash).toBe("#/jobs?highlight=job-9"));
    const body = api.callsTo("POST /api/jobs")[0].body as { script: string; layout: { orientation: string } };
    expect(body.script).toBe("ja");
    expect(body.layout.orientation).toBe("vertical");
  });

  it("pide elegir un nombre si faltan parámetros", () => {
    render(<PreviewPage params={params("")} />);
    expect(screen.getByText(/Primero elige un nombre/)).toBeInTheDocument();
    expect(api.callsTo("POST /api/jobs/preview")).toHaveLength(0);
  });
});
