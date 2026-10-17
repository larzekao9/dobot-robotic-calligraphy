import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Conversion } from "../api/types";
import { ConverterPage } from "./ConverterPage";

const CARLOS: Conversion = {
  request_id: "00000000-0000-0000-0000-000000000001",
  input: "Carlos",
  normalized: "carlos",
  syllables: ["car", "los"],
  zh: [
    {
      rank: 1,
      text: "卡洛斯",
      pinyin: "kǎ luò sī",
      chars: [
        { char: "卡", pinyin: "kǎ", meaning: "tarjeta" },
        { char: "洛", pinyin: "luò", meaning: "río Luo" },
        { char: "斯", pinyin: "sī", meaning: null },
      ],
      source: "dictionary",
      verified: true,
    },
    {
      rank: 2,
      text: "嘉洛斯",
      pinyin: "jiā luò sī",
      chars: [{ char: "嘉", pinyin: "jiā", meaning: "excelente" }],
      source: "algorithm",
      verified: false,
    },
  ],
  ja: [
    { rank: 1, text: "カルロス", romaji: "karurosu", source: "dictionary", verified: false },
  ],
};

type Handler = () => Promise<Response>;
let convertHandler: Handler;
let jobHandler: (body: unknown) => Promise<Response>;
const fetchMock = vi.fn();

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

beforeEach(() => {
  convertHandler = () => Promise.resolve(json(CARLOS));
  fetchMock.mockReset();
  jobHandler = () => Promise.resolve(json({ id: "job-1" }, 201));
  window.location.hash = "";
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    if (url.endsWith("/api/health")) return Promise.resolve(json({ status: "ok" }));
    if (url.endsWith("/api/jobs")) return jobHandler(JSON.parse(String(init?.body)));
    return convertHandler();
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const convertCalls = () => fetchMock.mock.calls.filter(([u]) => String(u).includes("/convert"));

async function convert(name: string) {
  const user = userEvent.setup();
  render(<ConverterPage />);
  await user.type(screen.getByLabelText("Tu nombre"), name);
  await user.click(screen.getByRole("button", { name: "Convertir" }));
  return user;
}

describe("ConverterPage", () => {
  it("convierte un nombre y muestra chino y japonés con lecturas y significados", async () => {
    await convert("Carlos");

    expect(await screen.findByLabelText("Nombre en chino")).toHaveTextContent("卡洛斯");
    expect(screen.getByText("kǎ luò sī", { selector: "p" })).toBeInTheDocument();
    const chars = within(screen.getByRole("list", { name: "Significado de cada carácter" }));
    expect(chars.getByText("tarjeta")).toBeInTheDocument();
    expect(chars.getByText("río Luo")).toBeInTheDocument();
    expect(chars.getByText("Sin significado registrado")).toBeInTheDocument();

    expect(screen.getByLabelText("Nombre en japonés")).toHaveTextContent("カルロス");
    expect(screen.getByText("karurosu")).toBeInTheDocument();
    expect(screen.getByText(/car-los/)).toBeInTheDocument();
    expect(JSON.parse(String(convertCalls()[0][1].body))).toEqual({ name: "Carlos" });
  });

  it("usa fuentes CJK y marca el idioma de los caracteres", async () => {
    await convert("Carlos");
    expect(await screen.findByLabelText("Nombre en chino")).toHaveAttribute("lang", "zh-Hans");
    expect(screen.getByLabelText("Nombre en chino")).toHaveClass("font-sc");
    expect(screen.getByLabelText("Nombre en japonés")).toHaveAttribute("lang", "ja");
    expect(screen.getByLabelText("Nombre en japonés")).toHaveClass("font-jp");
  });

  it("permite elegir entre las alternativas del chino", async () => {
    const user = await convert("Carlos");
    await screen.findByLabelText("Nombre en chino");
    const group = screen.getByRole("radiogroup", { name: "Alternativas en chino" });
    expect(within(group).getByRole("radio", { name: "Opción 1" })).toBeChecked();

    await user.click(within(group).getByRole("radio", { name: "Opción 2" }));

    expect(screen.getByLabelText("Nombre en chino")).toHaveTextContent("嘉洛斯");
    expect(within(group).getByRole("radio", { name: "Opción 2" })).toBeChecked();
    expect(screen.getByText(/pendiente de revisión/)).toBeInTheDocument();
  });

  it("muestra el estado de carga y desactiva el botón mientras espera", async () => {
    let resolve!: (r: Response) => void;
    convertHandler = () => new Promise<Response>((r) => (resolve = r));
    await convert("Carlos");

    expect(await screen.findByText("Convirtiendo tu nombre…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Convirtiendo…" })).toBeDisabled();

    resolve(json(CARLOS));
    expect(await screen.findByLabelText("Nombre en chino")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Convertir" })).toBeEnabled();
  });

  it("muestra el mensaje de error que devuelve la API", async () => {
    convertHandler = () =>
      Promise.resolve(
        json({ error: { code: "rate_limited", message: "Demasiadas solicitudes." } }, 429),
      );
    await convert("Carlos");
    expect(await screen.findByRole("alert")).toHaveTextContent("Demasiadas solicitudes.");
    expect(screen.queryByLabelText("Nombre en chino")).not.toBeInTheDocument();
  });

  it("muestra un error claro si no hay conexión y permite reintentar", async () => {
    convertHandler = () => Promise.reject(new TypeError("Failed to fetch"));
    const user = await convert("Carlos");
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar");

    convertHandler = () => Promise.resolve(json(CARLOS));
    await user.click(screen.getByRole("button", { name: "Convertir" }));
    expect(await screen.findByLabelText("Nombre en chino")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("usa un mensaje genérico si el error no es JSON", async () => {
    convertHandler = () => Promise.resolve(new Response("boom", { status: 500 }));
    await convert("Carlos");
    expect(await screen.findByRole("alert")).toHaveTextContent("Error del servidor (500)");
  });

  it("avisa cuando no hay caracteres para el chino", async () => {
    convertHandler = () => Promise.resolve(json({ ...CARLOS, zh: [] }));
    await convert("Carlos");
    expect(await screen.findByText(/pendiente de revisión/)).toBeInTheDocument();
    expect(screen.getByLabelText("Nombre en japonés")).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });

  it.each([
    ["", "Escribe un nombre."],
    ["Ana123", "Solo se permiten letras"],
    ["a b c d e", "máximo 4 palabras"],
    ["x".repeat(61), "60 caracteres"],
  ])("valida %j en el cliente sin llamar a la API", async (name, message) => {
    const user = userEvent.setup();
    render(<ConverterPage />);
    if (name) {
      await user.click(screen.getByLabelText("Tu nombre"));
      await user.paste(name);
    }
    await user.click(screen.getByRole("button", { name: "Convertir" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByLabelText("Tu nombre")).toHaveAttribute("aria-invalid", "true");
    expect(convertCalls()).toHaveLength(0);
  });

  it("envía el formulario con Enter y recorta espacios", async () => {
    const user = userEvent.setup();
    render(<ConverterPage />);
    await user.type(screen.getByLabelText("Tu nombre"), "  Carlos  {Enter}");
    expect(await screen.findByLabelText("Nombre en chino")).toBeInTheDocument();
    expect(JSON.parse(String(convertCalls()[0][1].body))).toEqual({ name: "Carlos" });
  });

  it("'Ver trazos' abre la vista previa con la opción de chino elegida", async () => {
    const user = await convert("Carlos");
    await screen.findByLabelText("Nombre en chino");
    const zh = within(screen.getByRole("region", { name: "Chino (mandarín)" }));
    await user.click(zh.getByRole("radio", { name: "Opción 2" }));
    await user.click(zh.getByRole("button", { name: "Ver trazos" }));
    expect(window.location.hash).toBe(`#/preview?request=${CARLOS.request_id}&script=zh&rank=2`);

    const ja = within(screen.getByRole("region", { name: "Japonés (katakana)" }));
    await user.click(ja.getByRole("button", { name: "Ver trazos" }));
    expect(window.location.hash).toBe(`#/preview?request=${CARLOS.request_id}&script=ja&rank=1`);
  });

  it("'Preparar para escribir' crea el trabajo y abre la cola", async () => {
    let body: unknown;
    jobHandler = (b) => {
      body = b;
      return Promise.resolve(json({ id: "job-1" }, 201));
    };
    const user = await convert("Carlos");
    await screen.findByLabelText("Nombre en chino");
    const ja = within(screen.getByRole("region", { name: "Japonés (katakana)" }));
    await user.click(ja.getByRole("button", { name: "Preparar para escribir" }));

    await waitFor(() => expect(window.location.hash).toBe("#/jobs?highlight=job-1"));
    expect(body).toMatchObject({ request_id: CARLOS.request_id, script: "ja", rank: 1 });
  });

  it("muestra el error si no se puede preparar el trabajo", async () => {
    jobHandler = () =>
      Promise.resolve(json({ error: { code: "layout_overflow", message: "No cabe." } }, 422));
    const user = await convert("Carlos");
    await screen.findByLabelText("Nombre en chino");
    const zh = within(screen.getByRole("region", { name: "Chino (mandarín)" }));
    await user.click(zh.getByRole("button", { name: "Preparar para escribir" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No cabe.");
    expect(zh.getByRole("button", { name: "Preparar para escribir" })).toBeEnabled();
  });

  it("indica si el resultado está verificado", async () => {
    await convert("Carlos");
    await screen.findByLabelText("Nombre en chino");
    expect(screen.getByText("Verificado")).toBeInTheDocument(); // opción 1 del chino
    expect(screen.getByText("Diccionario")).toBeInTheDocument(); // japonés sin verificar
  });

  it("muestra el estado del servidor", async () => {
    render(<ConverterPage />);
    expect(await screen.findByText("Servidor: OK")).toBeInTheDocument();
  });
});
