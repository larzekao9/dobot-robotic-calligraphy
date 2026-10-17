import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { partialStrokes, strokeLength } from "../lib/strokeProgress";
import { StrokePlayer } from "./StrokePlayer";

// Un nombre de 3 caracteres, un trazo de 50 mm cada uno (150 mm en total → 6 s a 25 mm/s).
const NAME = [
  [[0, 0], [50, 0]],
  [[60, 0], [110, 0]],
  [[120, 0], [170, 0]],
];

const drawn = () => Number(screen.getByRole("img").getAttribute("data-drawn"));
const inkStrokes = () => screen.getByTestId("ink").querySelectorAll("polyline").length;
const advance = (ms: number) => act(() => void vi.advanceTimersByTime(ms));

beforeEach(() =>
  vi.useFakeTimers({
    toFake: ["requestAnimationFrame", "cancelAnimationFrame", "performance", "setTimeout", "clearTimeout", "Date"],
  }),
);
afterEach(() => vi.useRealTimers());

describe("partialStrokes", () => {
  it("dibuja trazos completos y corta el último en la longitud pedida", () => {
    expect(strokeLength(NAME[0])).toBe(50);
    expect(partialStrokes(NAME, 0)).toEqual([]);
    expect(partialStrokes(NAME, 50)).toEqual([NAME[0]]);
    const part = partialStrokes(NAME, 75);
    expect(part).toHaveLength(2);
    expect(part[1]).toEqual([[60, 0], [85, 0]]);
    expect(partialStrokes(NAME, 9999)).toEqual(NAME);
  });

  it("interpola dentro de un segmento de varios puntos", () => {
    const part = partialStrokes([[[0, 0], [10, 0], [10, 10]]], 15);
    expect(part).toEqual([[[0, 0], [10, 0], [10, 5]]]);
  });
});

describe("StrokePlayer", () => {
  it("anima los 3 caracteres en orden hasta terminar", () => {
    render(<StrokePlayer strokes={NAME} width={210} height={297} />);
    expect(drawn()).toBe(0);
    expect(inkStrokes()).toBe(0);

    advance(2000); // ≈ 50 mm: primer carácter
    expect(drawn()).toBeGreaterThan(45);
    expect(drawn()).toBeLessThan(55);
    expect(inkStrokes()).toBeGreaterThanOrEqual(1);

    advance(2000); // ≈ 100 mm: segundo carácter
    expect(inkStrokes()).toBe(2);
    expect(screen.getByRole("status")).toHaveTextContent("Dibujando");

    advance(3000);
    expect(drawn()).toBe(150);
    expect(inkStrokes()).toBe(3);
    expect(screen.getByRole("status")).toHaveTextContent("Terminado · 100%");
    expect(screen.getByRole("button", { name: "Repetir" })).toBeInTheDocument();
  });

  it("muestra la guía completa en gris desde el principio", () => {
    render(<StrokePlayer strokes={NAME} width={210} height={297} />);
    expect(screen.getByTestId("guide").querySelectorAll("polyline")).toHaveLength(3);
  });

  it("se pausa y se reanuda sin perder lo dibujado", () => {
    render(<StrokePlayer strokes={NAME} width={210} height={297} />);
    advance(2000);
    fireEvent.click(screen.getByRole("button", { name: "Pausar" }));
    const frozen = drawn();
    advance(3000);
    expect(drawn()).toBe(frozen);
    expect(screen.getByRole("status")).toHaveTextContent("En pausa");

    fireEvent.click(screen.getByRole("button", { name: "Reproducir" }));
    advance(1000);
    expect(drawn()).toBeGreaterThan(frozen + 20);
  });

  it("reinicia desde cero y vuelve a reproducir", () => {
    render(<StrokePlayer strokes={NAME} width={210} height={297} />);
    advance(7000);
    expect(drawn()).toBe(150);
    fireEvent.click(screen.getByRole("button", { name: "Reiniciar" }));
    expect(drawn()).toBe(0);
    expect(inkStrokes()).toBe(0);
    advance(1000);
    expect(drawn()).toBeGreaterThan(15);
    expect(screen.getByRole("status")).toHaveTextContent("Dibujando");
  });

  it("'Repetir' al terminar vuelve a empezar", () => {
    render(<StrokePlayer strokes={NAME} width={210} height={297} />);
    advance(7000);
    fireEvent.click(screen.getByRole("button", { name: "Repetir" }));
    expect(drawn()).toBe(0);
  });

  it("la velocidad multiplica el avance", () => {
    render(<StrokePlayer strokes={NAME} width={210} height={297} speed={2} />);
    advance(2000);
    expect(drawn()).toBeGreaterThan(90);
    expect(drawn()).toBeLessThan(105);
  });

  it("en bucle no se detiene al terminar", () => {
    render(<StrokePlayer strokes={NAME} width={210} height={297} loop />);
    advance(7000);
    expect(screen.getByRole("status")).toHaveTextContent("Dibujando");
    expect(drawn()).toBeLessThan(150);
  });

  it("reinicia la animación cuando cambian los trazos", () => {
    const { rerender } = render(<StrokePlayer strokes={NAME} width={210} height={297} />);
    advance(3000);
    rerender(<StrokePlayer strokes={[NAME[0]]} width={210} height={297} />);
    expect(drawn()).toBe(0);
    expect(screen.getByTestId("guide").querySelectorAll("polyline")).toHaveLength(1);
  });

  it("no falla sin trazos", () => {
    render(<StrokePlayer strokes={[]} width={210} height={297} />);
    advance(1000);
    expect(drawn()).toBe(0);
  });
});
