import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Page, RequestItem } from "../api/types";
import { mockApi } from "../test/mockApi";
import { HistoryPage } from "./HistoryPage";

const item = (id: string, name: string, zh: string | null, ja: string | null): RequestItem => ({
  id,
  input_name: name,
  created_at: "2026-10-16T12:00:00Z",
  locale: "es",
  zh_text: zh,
  ja_text: ja,
});

const page = (items: RequestItem[], p = 1, total = items.length): Page<RequestItem> => ({
  items,
  total,
  page: p,
  page_size: 10,
});

beforeEach(() => {
  window.location.hash = "";
});
afterEach(() => vi.unstubAllGlobals());

describe("HistoryPage", () => {
  it("lista las consultas y abre la vista previa del chino o del japonés", async () => {
    mockApi({ "GET /api/requests": () => page([item("r1", "Carlos", "卡洛斯", "カルロス")]) });
    const user = userEvent.setup();
    render(<HistoryPage />);

    expect(await screen.findByText("Carlos")).toBeInTheDocument();
    expect(screen.getByText("卡洛斯")).toBeInTheDocument();
    expect(screen.getByText("カルロス")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Ver chino" }));
    expect(window.location.hash).toBe("#/preview?request=r1&script=zh&rank=1");
    await user.click(screen.getByRole("button", { name: "Ver japonés" }));
    expect(window.location.hash).toBe("#/preview?request=r1&script=ja&rank=1");
  });

  it("oculta los botones de lo que no se pudo convertir", async () => {
    mockApi({ "GET /api/requests": () => page([item("r2", "Xyz", null, "クスイズ")]) });
    render(<HistoryPage />);
    await screen.findByText("Xyz");
    expect(screen.queryByRole("button", { name: "Ver chino" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ver japonés" })).toBeInTheDocument();
  });

  it("busca por nombre y vuelve a la primera página", async () => {
    const api = mockApi({ "GET /api/requests": () => page([]) });
    const user = userEvent.setup();
    render(<HistoryPage />);
    expect(await screen.findByText("No hay consultas todavía.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Buscar por nombre"), "mar");
    await waitFor(() => {
      const calls = api.callsTo("GET /api/requests");
      expect(calls[calls.length - 1].search.get("q")).toBe("mar");
    });
  });

  it("pagina con Anterior y Siguiente", async () => {
    const api = mockApi({
      "GET /api/requests": (c) =>
        c.search.get("page") === "2"
          ? page([item("r11", "Segunda", "二", "ニ")], 2, 11)
          : page([item("r1", "Primera", "一", "イチ")], 1, 11),
    });
    const user = userEvent.setup();
    render(<HistoryPage />);
    await screen.findByText("Primera");
    expect(screen.getByText("Página 1 de 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Segunda")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
    expect(api.callsTo("GET /api/requests").some((c) => c.search.get("page") === "2")).toBe(true);
  });

  it("muestra el error de carga", async () => {
    mockApi({ "GET /api/requests": () => Promise.reject(new TypeError("offline")) });
    render(<HistoryPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar");
  });
});
