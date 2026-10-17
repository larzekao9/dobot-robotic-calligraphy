# Nombres Pincel

Convierte nombres en español a chino (hanzi) y japonés (katakana) y prepara los trazos para un robot Dobot. Ver `../plan_implementacion.md`.

## Ejecutar
```
cp .env.example .env
docker compose up --build
```
Backend: http://localhost:8000/api/health · Frontend: http://localhost:5173

## Sin Docker
```
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest
cd frontend && npm install && npm run dev
```

## Trazos y licencias
`data/strokes/glyphs.json` contiene la línea central de cada carácter que el sistema puede emitir (caja 1024×1024, 12–30 puntos por trazo). Se regenera con:
```
cd backend && python -m scripts.import_strokes --download   # requiere la base migrada y con seeds
python -m app.seeds                                          # carga glyphs.json en la tabla glyphs
```
- **Hanzi**: [Make Me a Hanzi](https://github.com/skishore/makemeahanzi) `graphics.txt`, derivado de Arphic PL KaitiM GB / UKai, bajo la *Arphic Public License*.
- **Kana**: [KanjiVG](https://kanjivg.tagaini.net) © Ulrich Apel, bajo *CC BY-SA 3.0* (atribución y compartir igual).
- Cada glifo guarda su fuente y licencia en `glyphs.source`. Las fuentes originales (`data/strokes/raw/`) no se versionan.

## Uso (Fase 1)
| Pantalla | Ruta | Qué hace |
|---|---|---|
| Convertir | `#/` | Nombre → chino y japonés, con alternativas, lecturas y significados |
| Vista previa | `#/preview` | Animación del orden de trazos; papel (A4/A5/personalizado), tamaño, orientación, velocidad y tiempo estimado |
| Cola de trabajos | `#/jobs` | Iniciar/cancelar trabajos y ver el progreso (los ejecuta el simulador `MockDriver`) |
| Historial | `#/history` | Consultas anteriores, con búsqueda y paginación |
| Administración | `#/admin` | Diccionario, tabla silábica (connotación `avoid`) y conversiones pendientes de revisión |

**Añadir un nombre:** Administración → *Diccionario* → completa nombre, hanzi/pinyin y katakana/romaji → *Guardar (verificado)*. La próxima conversión de ese nombre sale del diccionario con la marca «Verificado». También puedes promover un nombre desde *Pendientes de revisión*.

**Administración y Robot:** sin contraseña por defecto (`ADMIN_TOKEN` vacío en `.env`). Docker publica los puertos solo en `127.0.0.1`, es decir, solo se usa desde este equipo. Si quieres proteger la API, pon un valor en `ADMIN_TOKEN` (se exige en la cabecera `X-Admin-Token`; la interfaz no lo envía, así que sirve para integraciones, no para la pantalla). Para abrirla a otros equipos de la red, cambia los puertos de `docker-compose.yml` y define un token.

**Variables de entorno:** `DATABASE_URL`, `ADMIN_TOKEN` (opcional), `RATE_LIMIT_PER_MINUTE` (30), `ROBOT_DRIVER` (`mock`), `MOCK_TIME_SCALE` (10: el simulador va 10× más rápido que un robot real).

**Pruebas:** `cd backend && pytest` · `cd frontend && npm test`. Calidad: `ruff check . && mypy app tests scripts` y `npm run lint`.


## Fase 2: Dobot MG400 por TCP/IP (Hito 11)
Driver en `backend/app/services/robot/dobot_driver.py`, basado en la *TCP/IP Remote Control Interface Guide (4axis)* de Dobot (controlador ≥ 1.5.6.0) y su cliente oficial `Dobot-Arm/TCP-IP-4Axis-Python`. **Es distinto del protocolo V4 de los CR/Nova:** 4 ejes `(x, y, z, r)`, movimiento por el puerto 30003, sin `PowerOn`, y sin `ResultID` (el fin de movimiento se espera con `Sync()`).

| Puerto | Uso |
|---|---|
| 29999 | Dashboard: `EnableRobot`, `SpeedFactor`, `Pause`, `Continue`, `ResetRobot` |
| 30003 | Movimiento: `MovL(x,y,z,r)` y `Sync()` |
| 30004 | Feedback de 1440 bytes: modo, pose, alarma |

**Puesta en marcha** (pantalla **Robot**):
1. Conecta el PC al robot por cable. IP por defecto: LAN1 `192.168.1.6` (LAN2 `192.168.2.6`); pon tu PC en el mismo segmento y comprueba el `ping`.
2. *Conexión*: driver «Dobot MG400» + IP → *Guardar ajustes*. El estado debe mostrar el modo del robot.
3. *Calibración*: con el brazo en modo arrastre, toca con la punta las esquinas de la cartulina y pulsa *Capturar* (origen, esquina superior derecha, esquina inferior izquierda; el tintero solo con pincel). El tamaño medido de la cartulina es el límite de los trabajos.
4. Deja el **modo lápiz** activo y en *Cola de trabajos* usa **Probar en el aire** (recorre toda la ruta con la pluma arriba).
5. Escribe con lápiz. Solo después desactiva el modo lápiz, captura el tintero y sube velocidad y presión poco a poco.

**Seguridad:** toda la ruta se valida (dentro de la cartulina calibrada) antes de mover nada; ante un paro, un error o una alarma se hace `ResetRobot()` y la pluma sube; las alarmas nunca se limpian solas (se revisan en DobotStudio); al desconectar el brazo queda habilitado. Nada sustituye al paro de emergencia físico.

**Estado de la verificación:** el driver está probado contra un MG400 simulado que habla el protocolo real (`backend/tests/fake_mg400.py`); **no se ha probado todavía con el robot físico.** Puntos a confirmar en la primera sesión: que las poses de `feedback` y de `MovL` estén en el mismo sistema de coordenadas (User/Tool configurados), y cómo reacciona `Sync()` ante una alarma.
