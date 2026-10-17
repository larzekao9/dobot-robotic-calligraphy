import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { NameOut, SyllableOut } from "../api/types";
import { apiError, mockApi } from "../test/mockApi";
import { AdminPage } from "./AdminPage";

const name = (over: Partial<NameOut> = {}): NameOut => ({
  id: 1,
  name_es: "carlos",
  display_name: "Carlos",
  gender: "m",
  verified: false,
  missing_glyphs: [],
  transliterations: [
    { id: 1, script: "zh", text: "卡洛斯", reading: "kǎ luò sī", rank: 1, verified: false },
    { id: 2, script: "ja", text: "カルロス", reading: "karurosu", rank: 1, verified: false },
  ],
  ...over,
});

const syllable = (over: Partial<SyllableOut> = {}): SyllableOut => ({
  id: 7,
  script: "zh",
  syllable_es: "si",
  output: "死",
  reading: "sǐ",
  meaning: "muerte",
  connotation: "neutral",
  gender_hint: "u",
  score: 99,
  ...over,
});

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 10 });

async function open() {
  const user = userEvent.setup();
  render(<AdminPage />);
  return user;
}

afterEach(() => vi.unstubAllGlobals());

describe("AdminPage", () => {
  it("entra directo, sin pedir token ni enviar la cabecera", async () => {
    const api = mockApi({ "GET /api/admin/names": () => page([name()]) });
    await open();
    expect(await screen.findByText("Carlos")).toBeInTheDocument();
    expect(screen.queryByLabelText("Token de administrador")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cerrar sesión" })).not.toBeInTheDocument();
    expect(api.callsTo("GET /api/admin/names")[0].headers.get("X-Admin-Token")).toBeNull();
  });

  it("muestra el error si el servidor exige un token (ADMIN_TOKEN configurado)", async () => {
    mockApi({
      "GET /api/admin/names": () => apiError("unauthorized", "Token de administrador inválido o ausente.", 401),
    });
    await open();
    expect(await screen.findByRole("alert")).toHaveTextContent("Token de administrador inválido");
  });

  it("añade un nombre nuevo como verificado y refresca la lista", async () => {
    let names = [name({ verified: true })];
    const api = mockApi({
      "GET /api/admin/names": () => page(names),
      "POST /api/admin/names": (c) => {
        const b = c.body as { display_name: string };
        const created = name({ id: 2, display_name: b.display_name, name_es: "zacarias", verified: true });
        names = [...names, created];
        return created;
      },
    });
    const user = await open();
    await screen.findByText("Carlos");

    const form = within(screen.getByRole("form", { name: "Formulario de nombre" }));
    await user.type(form.getByLabelText("Nombre"), "Zacarías");
    await user.type(form.getByLabelText("Chino (hanzi)"), "安娜");
    await user.type(form.getByLabelText("Pinyin"), "ān nà");
    await user.type(form.getByLabelText("Japonés (katakana)"), "サカリアス");
    await user.type(form.getByLabelText("Romaji"), "sakariasu");
    await user.click(form.getByRole("button", { name: "Guardar (verificado)" }));

    expect(await screen.findByText("«Zacarías» guardado y verificado.")).toBeInTheDocument();
    expect(api.callsTo("POST /api/admin/names")[0].body).toEqual({
      display_name: "Zacarías",
      gender: "u",
      verified: true,
      transliterations: [
        { script: "zh", text: "安娜", reading: "ān nà", rank: 1 },
        { script: "ja", text: "サカリアス", reading: "sakariasu", rank: 1 },
      ],
    });
    expect(await screen.findByText("Zacarías")).toBeInTheDocument();
    expect(form.getByLabelText("Nombre")).toHaveValue(""); // el formulario se limpia
  });

  it("valida en el cliente: nombre y al menos una transliteración", async () => {
    const api = mockApi({ "GET /api/admin/names": () => page([]) });
    const user = await open();
    await screen.findByText("No hay nombres que coincidan.");
    const form = within(screen.getByRole("form", { name: "Formulario de nombre" }));

    await user.click(form.getByRole("button", { name: "Guardar (verificado)" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Escribe el nombre.");
    await user.type(form.getByLabelText("Nombre"), "Raro");
    await user.click(form.getByRole("button", { name: "Guardar (verificado)" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("al menos una transliteración");
    expect(api.callsTo("POST /api/admin/names")).toHaveLength(0);
  });

  it("avisa de los caracteres sin trazos y de los duplicados", async () => {
    let fail = false;
    mockApi({
      "GET /api/admin/names": () => page([]),
      "POST /api/admin/names": () =>
        fail
          ? apiError("name_exists", "«Raro» ya está en el diccionario.", 409)
          : name({ display_name: "Raro", missing_glyphs: ["龘"] }),
    });
    const user = await open();
    await screen.findByText("No hay nombres que coincidan.");
    const form = within(screen.getByRole("form", { name: "Formulario de nombre" }));
    const fill = async () => {
      await user.type(form.getByLabelText("Nombre"), "Raro");
      await user.type(form.getByLabelText("Chino (hanzi)"), "龘");
      await user.type(form.getByLabelText("Pinyin"), "dá");
      await user.click(form.getByRole("button", { name: "Guardar (verificado)" }));
    };
    await fill();
    expect(await screen.findByRole("status")).toHaveTextContent("el robot aún no puede escribir: 龘");

    fail = true;
    await fill();
    expect(await screen.findByRole("alert")).toHaveTextContent("ya está en el diccionario");
  });

  it("verifica, filtra los no verificados y elimina con confirmación", async () => {
    let current = name();
    const api = mockApi({
      "GET /api/admin/names": () => page([current]),
      "POST /api/admin/names/1/verify": (c) => {
        current = name({ verified: (c.body as { verified: boolean }).verified });
        return current;
      },
      "DELETE /api/admin/names/1": () => new Response(null, { status: 204 }),
    });
    const user = await open();
    expect(await screen.findByText("Sin verificar")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Verificar" }));
    expect(await screen.findByText("Verificado")).toBeInTheDocument();
    expect(api.callsTo("POST /api/admin/names/1/verify")[0].body).toEqual({ verified: true });

    await user.click(screen.getByLabelText("Solo sin verificar"));
    await waitFor(() => {
      const calls = api.callsTo("GET /api/admin/names");
      expect(calls[calls.length - 1].search.get("verified")).toBe("false");
    });

    const confirm = vi.spyOn(window, "confirm");
    confirm.mockReturnValueOnce(false);
    await user.click(screen.getByRole("button", { name: "Eliminar" }));
    expect(api.callsTo("DELETE /api/admin/names/1")).toHaveLength(0);
    confirm.mockReturnValueOnce(true);
    await user.click(screen.getByRole("button", { name: "Eliminar" }));
    await waitFor(() => expect(api.callsTo("DELETE /api/admin/names/1")).toHaveLength(1));
    confirm.mockRestore();
  });

  it("edita un nombre existente con PUT", async () => {
    const api = mockApi({
      "GET /api/admin/names": () => page([name()]),
      "PUT /api/admin/names/1": () => name({ verified: true }),
    });
    const user = await open();
    await user.click(await screen.findByRole("button", { name: "Editar" }));
    const form = within(screen.getByRole("form", { name: "Formulario de nombre" }));
    expect(form.getByLabelText("Nombre")).toHaveValue("Carlos");
    expect(form.getByLabelText("Chino (hanzi)")).toHaveValue("卡洛斯");
    await user.clear(form.getByLabelText("Pinyin"));
    await user.type(form.getByLabelText("Pinyin"), "kǎ luò sī!");
    await user.click(form.getByRole("button", { name: "Guardar (verificado)" }));
    await waitFor(() => expect(api.callsTo("PUT /api/admin/names/1")).toHaveLength(1));
    expect((api.callsTo("PUT /api/admin/names/1")[0].body as { verified: boolean }).verified).toBe(true);
  });

  it("promueve una conversión pendiente al diccionario con el formulario prellenado", async () => {
    mockApi({
      "GET /api/admin/names": () => page([]),
      "GET /api/admin/pending": () => [
        {
          request_id: "r1",
          input_name: "Marta",
          created_at: "2026-10-16T12:00:00Z",
          zh: { text: "马尔塔", pinyin: "mǎ ěr tǎ" },
          ja: { text: "マルタ", romaji: "maruta" },
        },
        {
          request_id: "r2",
          input_name: "Ana Pia",
          created_at: "2026-10-16T12:00:00Z",
          zh: { text: "安娜·皮亚", pinyin: "ān nà · pí yà" },
          ja: null,
        },
      ],
    });
    const user = await open();
    await user.click(screen.getByRole("tab", { name: "Pendientes de revisión" }));
    const list = within(await screen.findByRole("list", { name: "Pendientes" }));
    await user.click(list.getAllByRole("button", { name: "Añadir al diccionario" })[0]);

    const form = within(await screen.findByRole("form", { name: "Formulario de nombre" }));
    expect(form.getByLabelText("Nombre")).toHaveValue("Marta");
    expect(form.getByLabelText("Chino (hanzi)")).toHaveValue("马尔塔");
    expect(form.getByLabelText("Romaji")).toHaveValue("maruta");

    // un nombre de varias palabras solo precarga el nombre: el diccionario es por palabra
    await user.click(screen.getByRole("tab", { name: "Pendientes de revisión" }));
    await user.click((await screen.findAllByRole("button", { name: "Añadir al diccionario" }))[1]);
    const second = within(await screen.findByRole("form", { name: "Formulario de nombre" }));
    expect(second.getByLabelText("Nombre")).toHaveValue("Ana Pia");
    expect(second.getByLabelText("Chino (hanzi)")).toHaveValue("");
  });

  it("indica cuando no hay pendientes", async () => {
    mockApi({ "GET /api/admin/names": () => page([]), "GET /api/admin/pending": () => [] });
    const user = await open();
    await user.click(screen.getByRole("tab", { name: "Pendientes de revisión" }));
    expect(await screen.findByText(/No hay conversiones pendientes/)).toBeInTheDocument();
  });

  it("cambia la connotación de una sílaba a «Evitar»", async () => {
    let s = syllable();
    const api = mockApi({
      "GET /api/admin/syllables": () => page([s]),
      "PUT /api/admin/syllables/7": (c) => {
        s = syllable({ connotation: (c.body as { connotation: "avoid" }).connotation });
        return s;
      },
    });
    const user = await open();
    await user.click(screen.getByRole("tab", { name: "Sílabas" }));
    await user.selectOptions(await screen.findByLabelText("Connotación de 死"), "avoid");
    await waitFor(() => expect(api.callsTo("PUT /api/admin/syllables/7")).toHaveLength(1));
    expect(api.callsTo("PUT /api/admin/syllables/7")[0].body).toMatchObject({
      output: "死",
      connotation: "avoid",
      score: 99,
    });
    expect(api.callsTo("PUT /api/admin/syllables/7")[0].body).not.toHaveProperty("id");
    await waitFor(() => expect(screen.getByLabelText("Connotación de 死")).toHaveValue("avoid"));
  });

  it("añade una sílaba nueva, filtra por escritura y muestra el error de duplicado", async () => {
    let dup = false;
    const api = mockApi({
      "GET /api/admin/syllables": () => page([]),
      "POST /api/admin/syllables": () =>
        dup ? apiError("syllable_exists", "Esa combinación ya existe.", 409) : syllable({ id: 8 }),
    });
    const user = await open();
    await user.click(screen.getByRole("tab", { name: "Sílabas" }));
    await screen.findByText("No hay sílabas que coincidan.");

    const filter = screen.getAllByLabelText("Escritura")[1]; // el 0 es el del formulario
    await user.selectOptions(filter, "ja");
    await waitFor(() => {
      const calls = api.callsTo("GET /api/admin/syllables");
      expect(calls[calls.length - 1].search.get("script")).toBe("ja");
    });
    const form = within(screen.getByRole("form", { name: "Formulario de sílaba" }));
    await user.type(form.getByLabelText("Sílaba (español)"), "zu");
    await user.type(form.getByLabelText("Carácter"), "祖");
    await user.type(form.getByLabelText("Lectura"), "zǔ");
    await user.click(form.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.callsTo("POST /api/admin/syllables")).toHaveLength(1));
    expect(api.callsTo("POST /api/admin/syllables")[0].body).toMatchObject({
      script: "zh",
      syllable_es: "zu",
      output: "祖",
      meaning: null,
      connotation: "neutral",
      score: 50,
    });

    dup = true;
    await user.type(form.getByLabelText("Sílaba (español)"), "zu");
    await user.type(form.getByLabelText("Carácter"), "祖");
    await user.type(form.getByLabelText("Lectura"), "zǔ");
    await user.click(form.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Esa combinación ya existe.");
  });
});
