import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RobotConfig, RobotStatus } from "../api/types";
import { apiError, mockApi } from "../test/mockApi";
import { RobotPage } from "./RobotPage";

const CONFIG: RobotConfig = {
  driver: "dobot",
  ip: "192.168.1.6",
  user: 0,
  tool: 0,
  speed_factor: 20,
  speed_l: 30,
  accel_l: 30,
  cp: 0,
  lift_mm: 8,
  press_depth_mm: 2,
  r_deg: 0,
  pencil_mode: true,
  dip_clearance_mm: 30,
  dip_depth_mm: 3,
  dip_dwell_s: 1,
  origin: null,
  x_axis: null,
  y_axis: null,
  ink: null,
  calibrated: false,
};

const STATUS: RobotStatus = {
  driver: "dobot",
  reachable: true,
  mode: 5,
  mode_name: "Habilitado y libre",
  enabled: true,
  alarm: false,
  pose: [300, 10.5, 25, 0],
  error: null,
};

let config: RobotConfig;
let api: ReturnType<typeof mockApi>;

beforeEach(() => {
  config = { ...CONFIG };
  api = mockApi({
    "GET /api/robot/config": () => config,
    "GET /api/robot/status": () => STATUS,
    "PUT /api/robot/config": (c) => {
      config = c.body as RobotConfig;
      return config;
    },
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RobotPage", () => {
  it("muestra el estado del robot sin pedir token", async () => {
    render(<RobotPage pollMs={20} />);
    const state = within(await screen.findByRole("region", { name: "Estado" }));
    expect(await state.findByText(/Dobot MG400 \(192\.168\.1\.6\)/)).toBeInTheDocument();
    expect(state.getByText("Habilitado y libre")).toBeInTheDocument();
    expect(state.getByText(/x=300\.0 y=10\.5 z=25\.0/)).toBeInTheDocument();
    expect(api.callsTo("GET /api/robot/status")[0].headers.get("X-Admin-Token")).toBeNull();
  });

  it("refresca el estado y resalta una alarma", async () => {
    render(<RobotPage pollMs={20} />);
    await screen.findByText("Habilitado y libre");
    api.on("GET /api/robot/status", () => ({ ...STATUS, mode: 9, mode_name: "ALARMA", alarm: true }));
    expect(await screen.findByText("ALARMA")).toHaveClass("text-red-800");
  });

  it("explica cuando no hay conexión con el robot", async () => {
    api.on("GET /api/robot/status", () => ({
      driver: "dobot",
      reachable: false,
      error: "No hay conexión con 192.168.1.6: timed out",
    }));
    render(<RobotPage />);
    expect(await screen.findByText(/No hay conexión con 192\.168\.1\.6/)).toBeInTheDocument();
  });

  it("guía la calibración: captura los tres puntos y muestra el tamaño de la cartulina", async () => {
    const poses: Record<string, [number, number, number]> = {
      origin: [300, -100, 20],
      x_axis: [300, 110, 20],
      y_axis: [3, -100, 20],
    };
    api.on("POST /api/robot/capture/origin", () => (config = { ...config, origin: poses.origin }));
    api.on("POST /api/robot/capture/x_axis", () => (config = { ...config, x_axis: poses.x_axis }));
    api.on("POST /api/robot/capture/y_axis", () => (config = { ...config, y_axis: poses.y_axis }));
    const user = userEvent.setup();
    render(<RobotPage />);

    const status = await screen.findByLabelText("Estado de la calibración");
    expect(status).toHaveTextContent("Falta calibrar");
    expect(screen.getByLabelText(/Valor de 1\./)).toHaveTextContent("Sin capturar");

    await user.click(screen.getByRole("button", { name: /Capturar 1\./ }));
    await user.click(screen.getByRole("button", { name: /Capturar 2\./ }));
    expect(screen.getByLabelText(/Valor de 1\./)).toHaveTextContent("x=300 y=-100 z=20");
    expect(status).toHaveTextContent("Falta calibrar");
    await user.click(screen.getByRole("button", { name: /Capturar 3\./ }));

    await waitFor(() => expect(status).toHaveTextContent("210 × 297 mm"));
  });

  it("no deja capturar con el simulador y muestra el error de la captura", async () => {
    config = { ...CONFIG, driver: "mock" };
    api.on("GET /api/robot/status", () => ({ driver: "mock", reachable: true, mode: 5, mode_name: "Simulador" }));
    render(<RobotPage />);
    const capture = await screen.findByRole("button", { name: /Capturar 1\./ });
    expect(capture).toBeDisabled();
    expect(screen.getByText(/Elige el driver «Dobot MG400»/)).toBeInTheDocument();
  });

  it("muestra el error si el robot no responde al capturar", async () => {
    api.on("POST /api/robot/capture/origin", () =>
      apiError("robot_unreachable", "No hay conexión con 192.168.1.6: timed out", 502),
    );
    const user = userEvent.setup();
    render(<RobotPage />);
    await user.click(await screen.findByRole("button", { name: /Capturar 1\./ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No hay conexión");
  });

  it("guarda los ajustes de escritura y de conexión", async () => {
    const user = userEvent.setup();
    render(<RobotPage />);
    const form = within(await screen.findByRole("form", { name: "Ajustes de escritura" }));
    expect(form.getByRole("checkbox")).toBeChecked(); // modo lápiz por defecto

    await user.clear(form.getByLabelText("Velocidad global (%)"));
    await user.type(form.getByLabelText("Velocidad global (%)"), "35");
    await user.click(form.getByRole("checkbox"));
    await user.click(form.getByRole("button", { name: "Guardar ajustes" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Ajustes guardados.");
    const sent = api.callsTo("PUT /api/robot/config")[0].body as RobotConfig;
    expect(sent).toMatchObject({ speed_factor: 35, pencil_mode: false, driver: "dobot", ip: "192.168.1.6" });
  });

  it("cambia de driver y de IP", async () => {
    const user = userEvent.setup();
    render(<RobotPage />);
    const conn = within(await screen.findByRole("region", { name: "Conexión" }));
    await user.selectOptions(conn.getByLabelText("Driver"), "mock");
    await user.clear(conn.getByLabelText("IP del robot"));
    await user.type(conn.getByLabelText("IP del robot"), "192.168.2.6");
    await user.click(screen.getByRole("button", { name: "Guardar ajustes" }));
    await waitFor(() => expect(api.callsTo("PUT /api/robot/config")).toHaveLength(1));
    expect(api.callsTo("PUT /api/robot/config")[0].body).toMatchObject({ driver: "mock", ip: "192.168.2.6" });
  });

  it("recuerda los pasos de seguridad", async () => {
    render(<RobotPage />);
    const safety = within(await screen.findByRole("region", { name: "Seguridad" }));
    expect(safety.getByText(/paro de emergencia físico/)).toBeInTheDocument();
    expect(safety.getByText(/Probar en el aire/)).toBeInTheDocument();
  });
});

describe("RobotPage: habilitar y modo arrastre", () => {
  const confirm = () => vi.spyOn(window, "confirm");

  it("habilita el robot solo tras confirmar", async () => {
    api.on("GET /api/robot/status", () => ({ ...STATUS, mode: 4, mode_name: "Deshabilitado" }));
    api.on("POST /api/robot/enable", () => STATUS);
    const c = confirm().mockReturnValueOnce(false).mockReturnValueOnce(true);
    const user = userEvent.setup();
    render(<RobotPage pollMs={5000} />);
    const button = await screen.findByRole("button", { name: "Habilitar robot" });
    await user.click(button);
    expect(c.mock.calls[0][0]).toMatch(/paro de emergencia/);
    expect(api.callsTo("POST /api/robot/enable")).toHaveLength(0); // canceló: no se envía nada

    await user.click(button);
    expect(await screen.findByText("Robot habilitado.")).toBeInTheDocument();
    expect(api.callsTo("POST /api/robot/enable")).toHaveLength(1);
    expect(api.callsTo("POST /api/robot/enable")[0].headers.get("X-Admin-Token")).toBeNull();
    c.mockRestore();
  });

  it("solo permite habilitar si está deshabilitado y arrastrar si está habilitado", async () => {
    render(<RobotPage pollMs={5000} />); // modo 5: habilitado
    expect(await screen.findByRole("button", { name: "Habilitar robot" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Iniciar modo arrastre" })).toBeEnabled();
  });

  it("avisa que hay que sujetar el brazo y alterna el modo arrastre", async () => {
    let mode = 5;
    api.on("GET /api/robot/status", () => ({ ...STATUS, mode }));
    api.on("POST /api/robot/drag", (c) => {
      mode = (c.body as { on: boolean }).on ? 6 : 5;
      return { ...STATUS, mode };
    });
    const c = confirm().mockReturnValue(true);
    const user = userEvent.setup();
    render(<RobotPage pollMs={20} />);
    await user.click(await screen.findByRole("button", { name: "Iniciar modo arrastre" }));
    expect(c.mock.calls[0][0]).toMatch(/Sujétalo/);
    expect(api.callsTo("POST /api/robot/drag")[0].body).toEqual({ on: true });

    await user.click(await screen.findByRole("button", { name: "Detener modo arrastre" }));
    expect(api.callsTo("POST /api/robot/drag")[1].body).toEqual({ on: false });
    expect(await screen.findByRole("button", { name: "Iniciar modo arrastre" })).toBeInTheDocument();
    c.mockRestore();
  });

  it("muestra el error si el robot rechaza el comando", async () => {
    api.on("GET /api/robot/status", () => ({ ...STATUS, mode: 4, mode_name: "Deshabilitado" }));
    api.on("POST /api/robot/enable", () =>
      apiError("robot_alarm", "El robot tiene una alarma activa. Revísala y límpiala en DobotStudio.", 409),
    );
    const c = confirm().mockReturnValue(true);
    const user = userEvent.setup();
    render(<RobotPage pollMs={5000} />);
    await user.click(await screen.findByRole("button", { name: "Habilitar robot" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("alarma activa");
    c.mockRestore();
  });

  it("no ofrece los botones con el simulador", async () => {
    config = { ...CONFIG, driver: "mock" };
    api.on("GET /api/robot/status", () => ({ driver: "mock", reachable: true, mode: 5, mode_name: "Simulador" }));
    render(<RobotPage pollMs={5000} />);
    await within(await screen.findByRole("region", { name: "Estado" })).findByText("Simulador", { selector: "strong" });
    expect(screen.queryByRole("button", { name: "Habilitar robot" })).not.toBeInTheDocument();
  });
});

describe("RobotPage: driver sin guardar", () => {
  it("no ofrece habilitar, arrastrar ni capturar hasta guardar el driver", async () => {
    config = { ...CONFIG, driver: "mock" };
    api.on("GET /api/robot/status", () => ({ driver: "mock", reachable: true, mode: 5, mode_name: "Simulador" }));
    const user = userEvent.setup();
    render(<RobotPage pollMs={5000} />);
    const conn = within(await screen.findByRole("region", { name: "Conexión" }));
    await user.selectOptions(conn.getByLabelText("Driver"), "dobot");

    expect(screen.getByRole("note")).toHaveTextContent("no lo guardaste");
    expect(screen.queryByRole("button", { name: "Habilitar robot" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Iniciar modo arrastre" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Capturar 1\./ })).toBeDisabled();
    expect(api.callsTo("POST /api/robot/drag")).toHaveLength(0);

    api.on("GET /api/robot/status", () => STATUS); // tras guardar, el servidor ya usa «dobot»
    await user.click(screen.getByRole("button", { name: "Guardar ajustes" }));
    expect(await screen.findByRole("button", { name: "Iniciar modo arrastre" })).toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Capturar 1\./ })).toBeEnabled();
  });
});

describe("RobotPage: pérdida de conexión con el servidor", () => {
  it("avisa cuando falla la consulta de estado y se recupera sola al volver", async () => {
    let online = false;
    api.on("GET /api/robot/status", () => {
      if (!online) throw new TypeError("Failed to fetch");
      return STATUS;
    });
    render(<RobotPage pollMs={20} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar con el servidor");

    online = true;
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(await screen.findByText("Habilitado y libre")).toBeInTheDocument();
  });
});
