# Plan de implementación: Escritor de nombres en chino y japonés

> Documento pensado para que **Nemotron** (u otro LLM de código) lo implemente por fases.
> Fase 1 = software completo (frontend, backend, base de datos). Fase 2 = conexión con el robot Dobot.

---

## 1. Objetivo

Una persona dice su nombre en español. El sistema:

1. Lo transcribe fonéticamente a **chino (hanzi, mandarín)** y a **japonés (katakana)**.
2. Muestra opciones, pronunciación (pinyin / romaji) y una vista previa animada del trazo.
3. Guarda el resultado y, en la Fase 2, genera la **ruta de trazos** que un robot Dobot ejecuta con un pincel sobre cartulina.

### Alcance de la Fase 1
- Entrada de nombre, conversión, previsualización de trazos, historial, panel de curación.
- Generación de trazos listos para robot (formato intermedio), **sin** hardware real (driver simulado).

### Fuera de alcance por ahora
- Control real del brazo, calibración física, cámara, pagos.

---

## 2. Stack propuesto

| Capa | Tecnología | Motivo |
|---|---|---|
| Backend | Python 3.11 + FastAPI + Pydantic v2 | Simple, tipado, fácil de generar por un LLM |
| ORM / migraciones | SQLAlchemy 2 + Alembic | Estándar |
| Base de datos | SQLite (dev) → PostgreSQL (prod) | Mismo esquema, sin cambios |
| Frontend | React + Vite + TypeScript + Tailwind | Canvas/SVG para animar trazos |
| Pruebas | pytest (back), Vitest (front) | |
| Empaquetado | Docker Compose | Un comando para levantar todo |

---

## 3. Estructura del repositorio

```
nombres-pincel/
├── README.md
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models/            # SQLAlchemy
│   │   ├── schemas/           # Pydantic
│   │   ├── routers/
│   │   │   ├── names.py
│   │   │   ├── glyphs.py
│   │   │   ├── jobs.py
│   │   │   └── admin.py
│   │   ├── services/
│   │   │   ├── normalizer.py        # limpieza de texto español
│   │   │   ├── syllabifier.py       # separación en sílabas
│   │   │   ├── transliterate_zh.py
│   │   │   ├── transliterate_ja.py
│   │   │   ├── strokes.py           # trazos y normalización de coordenadas
│   │   │   └── robot/
│   │   │       ├── base.py          # interfaz RobotDriver
│   │   │       ├── mock_driver.py
│   │   │       └── dobot_driver.py  # Fase 2
│   │   └── seeds/                   # datos iniciales (CSV/JSON)
│   └── tests/
├── frontend/
│   ├── package.json
│   └── src/
│       ├── api/
│       ├── components/
│       ├── pages/
│       └── hooks/
└── data/
    ├── names_seed.csv
    ├── syllables_zh.csv
    ├── syllables_ja.csv
    └── strokes/                     # datos de trazos importados
```

---

## 4. Lógica de conversión (núcleo del sistema)

### 4.1 Principio
Los nombres propios **no se traducen, se transcriben por sonido**. Se usan tres mecanismos, en este orden de prioridad:

1. **Diccionario curado** de nombres comunes (María → 玛丽亚 / マリア). Es lo más fiable.
2. **Algoritmo silábico** para nombres que no estén en el diccionario.
3. **Sugerencia con LLM (opcional)**, siempre validada contra caracteres existentes en la base y marcada como "pendiente de revisión".

### 4.2 Japonés (más sencillo)
Español → sílabas → romaji (Hepburn) → **katakana**.
- Tabla de reglas: `ca→カ, co→コ, cu→ク, que→ケ, qui→キ, gue→ゲ, ll→ジャ/ヤ (configurable), ñ→ニャ/ニ, rr→ル, j→ハ行, h muda`.
- Consonante final: añadir vocal de apoyo (`l→ル, n→ン, s→ス, r→ル, d→ド, z→ス`).
- Grupos consonánticos: insertar vocal epentética (`Pablo → パブロ`, `Cristian → クリスティアン`).
- Vocales largas y `ー` solo cuando aplique.

### 4.3 Chino (mandarín)
Español → sílabas → pinyin aproximado → **hanzi elegido de una lista de caracteres para nombres**.
- Tabla `syllable_zh` con varias opciones por sílaba, cada una con: carácter, pinyin con tono, significado, `connotation` (positiva/neutra/evitar), `gender_hint` (masculino/femenino/neutro), `score`.
- Regla de selección: priorizar caracteres con connotación positiva, evitar los marcados como "evitar" (muerte, enfermedad, mala suerte) y evitar repetir el mismo carácter.
- Devolver **3 alternativas** ordenadas por puntuación, con el significado de cada carácter para que la persona elija.
- Aproximación a sílabas inexistentes en chino (p. ej. `bra`, `tri`): descomponer en sílabas permitidas (`布拉`, `特里`).

### 4.4 Contrato de salida del servicio

```json
{
  "input": "Carlos",
  "normalized": "carlos",
  "syllables": ["car", "los"],
  "zh": [
    {
      "rank": 1,
      "text": "卡洛斯",
      "pinyin": "kǎ luò sī",
      "chars": [
        {"char": "卡", "pinyin": "kǎ", "meaning": "tarjeta"},
        {"char": "洛", "pinyin": "luò", "meaning": "río Luo"},
        {"char": "斯", "pinyin": "sī", "meaning": "este"}
      ],
      "source": "dictionary"
    }
  ],
  "ja": [
    {"rank": 1, "text": "カルロス", "romaji": "karurosu", "source": "algorithm"}
  ]
}
```

---

## 5. Base de datos

### 5.1 Tablas

**`names_dictionary`** – nombres curados
| campo | tipo | nota |
|---|---|---|
| id | PK | |
| name_es | text, único | normalizado en minúsculas, sin tildes |
| display_name | text | con tildes |
| gender | enum(m,f,u) | |
| verified | bool | revisado por humano |

**`name_transliterations`** – resultados curados por nombre
| campo | tipo |
|---|---|
| id | PK |
| name_id | FK → names_dictionary |
| script | enum(zh, ja) |
| text | text |
| reading | text (pinyin o romaji) |
| rank | int |
| verified | bool |

**`syllable_map`** – tabla fonética para el algoritmo
| campo | tipo |
|---|---|
| id | PK |
| script | enum(zh, ja) |
| syllable_es | text |
| output | text (carácter/kana) |
| reading | text |
| meaning | text, nullable |
| connotation | enum(positive, neutral, avoid) |
| gender_hint | enum(m,f,u) |
| score | int |

**`glyphs`** – caracteres con trazos
| campo | tipo |
|---|---|
| id | PK |
| char | text, único por script |
| script | enum(zh, ja_kana, ja_kanji) |
| stroke_count | int |
| strokes_json | JSON: lista de trazos, cada uno es lista de puntos `[x,y]` en caja 1024×1024 |
| source | text (fuente y licencia) |

**`requests`** – cada consulta de un usuario
| campo | tipo |
|---|---|
| id | UUID PK |
| input_name | text |
| created_at | datetime |
| result_json | JSON (contrato de la sección 4.4) |
| locale | text |

**`jobs`** – trabajos de escritura (la tabla puente hacia el robot)
| campo | tipo |
|---|---|
| id | UUID PK |
| request_id | FK → requests |
| script | enum(zh, ja) |
| text | text |
| layout_json | JSON (tamaño de cartulina, márgenes, tamaño de carácter, orientación) |
| path_json | JSON (ruta final en mm con pluma arriba/abajo) |
| status | enum(draft, queued, running, done, failed, cancelled) |
| created_at / started_at / finished_at | datetime |
| error | text, nullable |

**`feedback`** (opcional) – valoración de la persona sobre la transcripción: `request_id`, `chosen_rank`, `comment`.

### 5.2 Índices
- `names_dictionary.name_es` único.
- `syllable_map (script, syllable_es)`.
- `glyphs (script, char)` único.
- `jobs (status, created_at)`.

### 5.3 Datos iniciales (seeds)
- ~300 nombres hispanos frecuentes con transliteración verificada.
- Tabla silábica del español completa (~250 sílabas) para zh y ja.
- Glifos: todos los katakana/hiragana y los hanzi usados en `syllable_map`.

---

## 6. Datos de trazos (para el robot)

Se necesita, por cada carácter, **la lista ordenada de trazos con su línea central** (no el contorno).

Fuentes sugeridas (**verificar licencia antes de redistribuir**):
- **Make Me a Hanzi** (`graphics.txt`): trazos y "medians" (línea central) de hanzi.
- **KanjiVG**: trazos SVG de kana y kanji, con orden de trazos.

Proceso de importación (script `scripts/import_strokes.py`):
1. Leer la fuente.
2. Muestrear cada trazo en 12–30 puntos con una curva suave.
3. Normalizar a una caja 1024×1024 con origen arriba-izquierda.
4. Guardar en `glyphs.strokes_json`.
5. Validar: todos los caracteres de `syllable_map` tienen glifo.

---

## 7. API (FastAPI)

| Método | Ruta | Función |
|---|---|---|
| GET | `/api/health` | Estado |
| POST | `/api/names/convert` | Body `{ "name": "Carlos" }` → contrato 4.4 y guarda `request` |
| GET | `/api/requests/{id}` | Recupera una consulta |
| GET | `/api/requests` | Historial paginado |
| GET | `/api/glyphs/{script}/{char}` | Trazos de un carácter |
| POST | `/api/jobs` | Crea un trabajo `{request_id, script, rank, layout}` y calcula `path_json` |
| GET | `/api/jobs/{id}` | Estado y ruta |
| POST | `/api/jobs/{id}/preview` | Devuelve ruta simplificada para animar |
| POST | `/api/jobs/{id}/start` | Fase 2: envía al robot (en Fase 1 usa `MockDriver`) |
| POST | `/api/jobs/{id}/cancel` | Cancela |
| `/api/admin/*` | CRUD de `names_dictionary`, `syllable_map`, verificación | Protegido con token simple |

Reglas:
- Validar nombre: 1–60 caracteres, letras, espacios, guiones, apóstrofes, tildes y ñ.
- Limitar a 4 palabras (nombre + apellidos). Cada palabra se convierte por separado y se unen con `·` (chino) o `・` (japonés).
- Rate limiting básico por IP.
- Errores en formato `{ "error": { "code": "...", "message": "..." } }`.

---

## 8. Frontend

### Pantallas
1. **Inicio / Conversor**
   - Campo grande para el nombre, botón "Convertir".
   - Dos tarjetas: **Chino** y **Japonés**, con el texto grande, la lectura (pinyin/romaji) y el significado de cada carácter.
   - Selector de alternativas (rank 1–3) para el chino.
   - Botón "Ver trazos" y botón "Preparar para escribir".
2. **Vista previa de trazos**
   - Animación en SVG/Canvas del orden de trazos.
   - Controles: velocidad, repetir, tamaño de carácter, orientación (vertical/horizontal), tamaño de cartulina (A4, A5, personalizado).
   - Indicador de tiempo estimado de escritura.
3. **Cola de trabajos**
   - Lista con estado (borrador, en cola, escribiendo, terminado) y botón cancelar. En Fase 1 funciona con el simulador.
4. **Historial**
5. **Admin** (protegido)
   - Editar el diccionario y la tabla silábica, marcar "verificado", ver conversiones pendientes de revisión.

### Requisitos de UX
- Funciona bien en tablet (se usará junto al robot).
- Letra grande y alto contraste, modo pantalla completa.
- Todo el texto de la interfaz en español.
- Fuentes CJK incluidas (Noto Sans SC / Noto Sans JP) para no depender del dispositivo.

---

## 9. Ruta de trazos y preparación para el robot

### 9.1 Pipeline (`services/strokes.py`)
1. Obtener glifos del texto elegido.
2. Colocarlos en la cartulina según el `layout` (márgenes, tamaño de celda, separación, orientación).
3. Convertir de coordenadas 1024×1024 a **milímetros** sobre la cartulina.
4. Suavizar y reducir puntos (Douglas-Peucker o similar).
5. Emitir una lista de comandos:

```json
[
  {"op": "move",  "x": 40.0, "y": 60.0, "z": "up"},
  {"op": "down"},
  {"op": "line",  "x": 42.5, "y": 61.2, "pressure": 0.6},
  {"op": "up"}
]
```

- `pressure` (0–1) permite variar el grosor del pincel modulando la altura Z. En el pincel real esto afecta mucho el aspecto del trazo: inicio con más presión, final con menos.
- Optimizar el orden de caracteres/trazos **sin romper el orden de trazos de cada carácter** (el orden importa en caligrafía).

### 9.2 Interfaz del robot (`services/robot/base.py`)

```python
class RobotDriver(Protocol):
    def connect(self) -> None: ...
    def home(self) -> None: ...
    def calibrate(self, origin: Point3D, x_axis: Point3D, y_axis: Point3D, z_paper: float) -> None: ...
    def execute(self, path: list[Command], on_progress: Callable[[float], None]) -> None: ...
    def pause(self) -> None: ...
    def stop(self) -> None: ...
    def dip_brush(self) -> None: ...    # mojar el pincel en tinta
    def disconnect(self) -> None: ...
```

- **`MockDriver`**: no mueve nada, simula el tiempo y devuelve progreso. Se usa en Fase 1 y en tests.
- **`DobotDriver`** (Fase 2): implementación real. Hay que confirmar el **modelo exacto** (Magician, MG400, M1 Pro, CR…), porque la API cambia:
  - Magician: librería Python `pydobot` / DobotDLL por USB-serie.
  - MG400 / M1 Pro / CR: API TCP/IP (puertos Dashboard y Move) documentada por Dobot.
  - DobotStudio sirve para calibrar y probar a mano antes de integrar.

---

## 10. Hitos para Nemotron

Entregar **un hito por vez**, con su criterio de aceptación. Cada hito debe terminar con tests pasando.

### Hito 0 – Esqueleto
- Crear estructura, `docker-compose.yml`, FastAPI con `/api/health`, React con una página en blanco, lint y formato.
- **Aceptación:** `docker compose up` levanta ambos servicios y el front muestra "OK" del health.

### Hito 1 – Base de datos
- Modelos SQLAlchemy de la sección 5, migración Alembic inicial, script de seeds.
- **Aceptación:** `alembic upgrade head` y `python -m app.seeds` crean y cargan las tablas; test que verifica los conteos.

### Hito 2 – Normalizador y silabeador del español
- `normalizer.py` (minúsculas, tildes, ñ, limpieza) y `syllabifier.py` (reglas de sílabas del español, diptongos, hiatos, `qu/gu/ll/rr/ch`).
- **Aceptación:** ≥ 50 casos de prueba, incluyendo `María → ma-rí-a`, `Guillermo → gui-ller-mo`, `Cristian → cris-tian`.

### Hito 3 – Transliteración al japonés
- `transliterate_ja.py` con las reglas de 4.2.
- **Aceptación:** tests con 40 nombres de referencia (`Carlos → カルロス`, `Ana → アナ`, `Pablo → パブロ`).

### Hito 4 – Transliteración al chino
- `transliterate_zh.py` con diccionario primero, algoritmo después, 3 alternativas y filtro de connotación.
- **Aceptación:** nombres del diccionario devuelven la versión verificada; nombres no listados devuelven 3 alternativas sin caracteres marcados como `avoid`.

### Hito 5 – Endpoint de conversión
- `POST /api/names/convert`, validaciones, guardado en `requests`, manejo de errores.
- **Aceptación:** tests de integración; respuesta igual al contrato de 4.4.

### Hito 6 – Importación de trazos
- `scripts/import_strokes.py` y `GET /api/glyphs/...`.
- **Aceptación:** todos los caracteres de `syllable_map` tienen trazos; test de integridad.

### Hito 7 – Frontend del conversor
- Pantalla 1 con tarjetas, alternativas, significados y llamada a la API.
- **Aceptación:** flujo completo en el navegador; estados de carga y error cubiertos.

### Hito 8 – Vista previa animada
- Componente `StrokePlayer` (SVG) con orden de trazos, velocidad y tamaño.
- **Aceptación:** anima correctamente un nombre de 3 caracteres, con pausa y reinicio.

### Hito 9 – Pipeline de ruta y trabajos
- `strokes.py` (layout → mm → comandos), `POST /api/jobs`, `MockDriver`, cola de trabajos en el front.
- **Aceptación:** un trabajo pasa de `draft` a `done` con progreso visible usando el simulador.

### Hito 10 – Admin, historial y pulido
- Panel de curación, historial, autenticación simple por token, README completo.
- **Aceptación:** se puede añadir un nombre nuevo desde el panel y aparece verificado en la conversión.

### Hito 11 (Fase 2) – Robot real
- `DobotDriver`, calibración guiada en la interfaz, prueba con lápiz antes de pincel, ajuste de presión y velocidad.

---

## 11. Calidad y criterios generales

- Tipado estricto (mypy en backend, `strict` en TypeScript).
- Cobertura de tests ≥ 80 % en `services/`.
- Sin secretos en el repositorio; configuración por variables de entorno (`.env.example`).
- Logs estructurados en backend.
- Accesibilidad básica en el front (contraste, etiquetas, teclado).
- Documentar en el README cómo ejecutar, probar y añadir nombres.

---

## 12. Riesgos y decisiones abiertas

| Tema | Riesgo | Mitigación |
|---|---|---|
| Calidad cultural del chino | Un carácter fonéticamente correcto puede tener mala connotación | Filtro `avoid`, significados visibles, verificación humana, revisar con un hablante nativo |
| Ambigüedad del japonés | Varias grafías válidas (`ル` vs `ロ` en finales) | Mostrar 1 principal y permitir alternativa en admin |
| Licencias de datos de trazos | Obligaciones de atribución o compartir igual | Registrar `source` por glifo y revisar licencias antes de publicar |
| Trazo con pincel | El pincel real exige presión variable y recargar tinta | Campo `pressure`, `dip_brush()`, pruebas con lápiz primero |
| Modelo de Dobot | La API depende del modelo | Confirmar modelo antes del Hito 11; el resto del sistema es independiente |
| LLM alucinando caracteres | Inventa hanzi o lecturas incorrectas | Validar siempre contra `glyphs` y marcar como "pendiente de revisión" |

**Decisiones que debes confirmar:**
1. Modelo exacto del Dobot.
2. ¿Chino simplificado, tradicional o ambos? (el plan asume simplificado; añadir tradicional implica una columna `variant`).
3. ¿Uso público (con muchos usuarios) o stand/evento con una sola tablet?
4. ¿Se imprime también el pinyin/romaji bajo los caracteres en la cartulina?

---

## 13. Instrucciones para Nemotron

Al iniciar cada hito, pásale este bloque junto con la sección relevante del plan:

```
Contexto: proyecto "nombres-pincel" descrito en plan_implementacion.md.
Tarea: implementar SOLO el Hito N.
Reglas:
- Respeta la estructura de carpetas y los contratos JSON del plan.
- No cambies el esquema de base de datos sin avisar; si hace falta, propón una migración.
- Escribe los tests del hito y asegúrate de que pasan.
- No inventes datos lingüísticos: usa los seeds y marca como "pendiente de revisión" lo que no esté verificado.
- Al terminar, lista los archivos creados/modificados y cómo ejecutar los tests.
```
