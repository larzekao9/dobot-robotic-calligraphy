import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { mockApi } from "./test/mockApi";

beforeEach(() => {
  mockApi({
    "GET /api/requests": () => ({ items: [], total: 0, page: 1, page_size: 10 }),
    "GET /api/jobs": () => [],
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

describe("App", () => {
  it.each([
    ["", "Tu nombre"],
    ["#/history", "Historial"],
    ["#/jobs", "Cola de trabajos"],
    ["#/admin", "Pendientes de revisión"],
    ["#/preview", "Primero elige un nombre"],
  ])("en %j muestra %s", async (hash, text) => {
    window.location.hash = hash;
    render(<App />);
    expect((await screen.findAllByText(new RegExp(text))).length).toBeGreaterThan(0);
  });

  it("cambia de pantalla cuando cambia el hash, sin recargar", async () => {
    window.location.hash = "";
    render(<App />);
    expect(await screen.findByLabelText("Tu nombre")).toBeInTheDocument();
    act(() => {
      window.location.hash = "#/history";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(await screen.findByLabelText("Buscar por nombre")).toBeInTheDocument();
  });

  it("la barra de navegación enlaza todas las secciones", async () => {
    render(<App />);
    const nav = await screen.findByRole("navigation", { name: "Secciones" });
    const hrefs = Array.from(nav.querySelectorAll("a")).map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(["#/", "#/history", "#/jobs", "#/admin", "#/robot"]);
  });
});
