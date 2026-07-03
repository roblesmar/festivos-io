[English](README.md) · **Español**

# festivos 🇪🇸

**Los festivos de España — nacionales, autonómicos _y locales (por municipio)_ — como dataset abierto, con una fuente oficial detrás de cada festivo.**

[![Código: MIT](https://img.shields.io/badge/código-MIT-blue.svg)](LICENSE)
[![Datos: CC BY 4.0](https://img.shields.io/badge/datos-CC%20BY%204.0-green.svg)](LICENSE-DATA)
[![Cobertura: 2024–2026](https://img.shields.io/badge/cobertura-2024–2026-orange.svg)](#cobertura)
[![Municipios: 8.132](https://img.shields.io/badge/municipios-8.132-lightgrey.svg)](#cobertura)

El calendario laboral español tiene **cuatro niveles**: nacional → autonómico → **local / municipal**. El último es el de mayor volumen y el que de verdad afecta a nóminas, RRHH, logística y cierres reales de negocio: cada uno de los **~8.132 municipios** fija **2 fiestas locales** propias al año (≈16.000 festivos locales/año). Casi todos los datasets se detienen en el nivel autonómico. **Este no.**

| Proyecto | Subdivisiones de España | ¿Festivos locales municipales? |
|---|---|:---:|
| Nager.Date | Solo CCAA | ❌ |
| OpenHolidays API | CCAA + provincias | ❌ |
| date-holidays | CCAA + algunas islas | ❌ |
| python-holidays | Solo CCAA | ❌ |
| **festivos** | **CCAA + provincia + municipio (código INE)** | ✅ |

Cada festivo lleva un **`source`**: los festivos nacionales y autonómicos citan la entrada oficial del BOE (`ref` + `url`); los locales indican su boletín autonómico de origen. Así el calendario es trazable a fuentes oficiales — y corregible por Pull Request.

## Qué incluye

- **8.132 municipios**, años **2024–2026**, las 17 CCAA + Ceuta y Melilla.
- Tres niveles por municipio: `national` · `regional` · `local`.
- **Clave canónica = código INE** — cadena de 5 dígitos, p. ej. `"43148"` (Tarragona).
- Nombres de festivo multilingües (`es`, `ca`, `eu`, `gl`, `ca-valencia`).
- **JSON** y **`.ics`** por municipio (suscribible en Google/Apple Calendar).
- Un `source` en **cada** festivo — con la `url` oficial en los nacionales y autonómicos (BOE).

## Empezar

**1. Descarga los festivos de un municipio** (alojado, gratis):

```bash
# Tarragona (INE 43148), 2026 — JSON
curl https://festivos.io/v1/2026/municipio/43148.json

# lo mismo, como calendario suscribible
curl https://festivos.io/v1/2026/municipio/43148.ics
```

**2. Suscríbete en tu calendario** — añade esta URL como calendario en Google/Apple Calendar:

```
https://festivos.io/v1/2026/municipio/43148.ics
```

**3. Consulta la API:**

```bash
# ¿Es festivo el 2026-08-19 en Tarragona?  → { "holiday": true, "name": "San Magín", ... }
curl "https://api.festivos.io/v1/is-holiday?date=2026-08-19&municipio=43148"

# puentes del año
curl "https://api.festivos.io/v1/puentes?municipio=43148&year=2026"
```

**4. Úsalo desde un agente de IA (MCP)** — un servidor MCP remoto expone todo esto como herramientas para asistentes como Claude:

```
https://mcp.festivos.io
```

…o autoalójalo desde [`mcp/`](mcp/).

## Formato de los datos

`v1/2026/municipio/43148.json` (extracto — datos reales):

```json
{
  "year": 2026,
  "license": "CC-BY-4.0",
  "attribution": "festivos.io — CC BY 4.0",
  "municipality": {
    "ine": "43148", "name": "Tarragona",
    "province": { "ine": "43", "name": "Tarragona" },
    "ccaa": { "code": "ES-CT", "name": "Cataluña" }
  },
  "holidays": [
    { "date": "2026-01-06", "name": { "es": "Epifanía del Señor" },
      "level": "national", "type": "fixed",
      "source": { "ref": "BOE-A-2025-21667", "url": "https://www.boe.es/…" } },

    { "date": "2026-08-19", "name": { "es": "San Magín" },
      "level": "local",
      "source": { "ref": "Generalitat de Catalunya — Calendari de festes locals", "url": "…" } },

    { "date": "2026-09-23", "name": { "es": "Santa Tecla" },
      "level": "local",
      "source": { "ref": "Generalitat de Catalunya — Calendari de festes locals", "url": "…" } }
  ]
}
```

El JSON Schema completo está en [`schema/`](schema/).

## Cobertura

| Nivel | Estado |
|---|---|
| **Nacional** (BOE) | 2024–2026 |
| **Autonómico** — 17 CCAA + Ceuta y Melilla (BOE) | 2024–2026 |
| **Local** (por municipio) | 2024–2026 · **~88% de los municipios con sus fiestas locales en 2026** |
| Formatos | JSON + `.ics` por municipio; paquetes autonómico y nacional |

Los municipios restantes son aquellos cuyo Ayuntamiento no ha publicado (o no en formato reutilizable) sus fiestas; esos huecos se cierran por ingesta y por PR de la comunidad.

## Construirlo tú mismo

El dataset lo genera un pipeline Python pequeño — sin framework, solo `openpyxl` + `rapidfuzz`:

```bash
pip install -r ingest/requirements.txt

# tablas de referencia (municipios INE ↔ provincia ↔ CCAA)
PYTHONPATH=ingest python3 -m festivos.cli ref 2026

# fiestas locales de una CCAA (p. ej. Cataluña)
PYTHONPATH=ingest python3 -m festivos.cli local ES-CT 2026

# un municipio
PYTHONPATH=ingest python3 -m festivos.cli municipio 43148 2026

# el año entero → escribe v1/2026/
PYTHONPATH=ingest python3 -m festivos.cli build 2026
```

Cada CCAA tiene su parser en [`ingest/festivos/fuentes/`](ingest/festivos/fuentes/), que lee el boletín oficial o el portal de datos abiertos. El mapa de las 19 fuentes está en [INGESTA-LOCALES.md](INGESTA-LOCALES.md).

## Estructura del repositorio

```
ingest/     pipeline Python — 19 parsers autonómicos, matching INE, escritores JSON/ICS
schema/     JSON Schema de cada fichero publicado
data/       datos canónicos curados (fiestas autonómicas y locales, calendario escolar y fiscal)
v1/ref/     tablas de referencia (municipios INE, comunidades, atribución)
mcp/        servidor MCP remoto — festivos como herramientas para agentes de IA
examples/   ficheros de ejemplo ya generados (Tarragona 2026, JSON + ICS)
```

> El dataset generado completo (`v1/2026/…`, ~300 MB) **no** se versiona: es reproducible con el pipeline de arriba y se sirve en vivo en `festivos.io/v1/…`.

## Fuentes y atribución

Obra derivada de información del sector público español reutilizable: **BOE** (festivos nacionales y autonómicos), portales de datos abiertos autonómicos (empezando por la Generalitat de Catalunya) e **INE** (referencia de municipios). La atribución por fuente se documenta en [FUENTES.md](FUENTES.md) y se conserva en el campo `source` de cada festivo. Reutilización al amparo de la **Ley 37/2007** y **CC BY 4.0**.

## Licencia

- **Código** (pipeline, parsers, herramientas): **[MIT](LICENSE)**.
- **Datos** (ficheros JSON/ICS generados y tablas de referencia): **[CC BY 4.0](LICENSE-DATA)** — libre uso, incluso comercial, con atribución: _«festivos.io — CC BY 4.0»_.

## Contribuir

¿Fecha incorrecta? ¿Falta una fiesta local? Abre un Pull Request sobre el fichero correspondiente en `data/` **y cita el boletín oficial** — toda corrección es verificable contra su fuente. Ver [CONTRIBUTING.md](CONTRIBUTING.md).

---

Mantenido por **[Danke Global SL](https://festivos.io)**. Una versión alojada y siempre al día vive en **[festivos.io](https://festivos.io)**.
