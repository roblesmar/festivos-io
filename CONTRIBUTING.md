[English](#contributing) · [Español](#contribuir)

# Contributing

The whole point of this project is that **holidays are traceable to an official source**. So the one rule for a data change is: **cite the source.**

## Fixing or adding a holiday

1. Find the file under `data/` for the region and year — e.g. `data/2026/local/ES-CT.json` for Catalonia's local holidays in 2026.
2. Make your change (a corrected date, a missing local holiday, a better name).
3. In the PR description, **link the official source**: the BOE entry, the regional gazette (DOGC, BOJA, DOGV…), or the municipal decree that establishes the date.

A change without a verifiable source can't be merged — not because we don't trust you, but because the next person needs to check it too.

## Improving a parser

Each region is parsed by a module in `ingest/festivos/fuentes/` (one per CCAA). If a regional gazette changes its format, or a source URL moves, that's where to fix it. Run the pipeline locally to check:

```bash
pip install -r ingest/requirements.txt
PYTHONPATH=ingest python3 -m festivos.cli local ES-CT 2026
PYTHONPATH=ingest python3 -m pytest ingest/tests   # if you touched matching logic
```

## Scope

This repo is the **open data core**: the dataset, the pipeline that builds it, the schema, and the MCP server. The hosted service, website and commercial API layer live elsewhere. Issues and PRs here should be about the **data and the tooling**.

---

# Contribuir

Todo el sentido de este proyecto es que **los festivos son trazables a una fuente oficial**. Así que la única regla para un cambio de datos es: **cita la fuente.**

## Corregir o añadir un festivo

1. Localiza el fichero en `data/` de la comunidad y el año — p. ej. `data/2026/local/ES-CT.json` para las fiestas locales de Cataluña en 2026.
2. Haz tu cambio (una fecha corregida, una fiesta local que falta, un nombre mejor).
3. En la descripción del PR, **enlaza la fuente oficial**: la entrada del BOE, el boletín autonómico (DOGC, BOJA, DOGV…) o el bando municipal que fija la fecha.

Un cambio sin fuente verificable no se puede fusionar — no por desconfianza, sino porque la siguiente persona también necesita comprobarlo.

## Mejorar un parser

Cada comunidad se parsea con un módulo en `ingest/festivos/fuentes/` (uno por CCAA). Si un boletín cambia de formato o una URL de origen se mueve, ahí se arregla. Ejecuta el pipeline en local para comprobarlo:

```bash
pip install -r ingest/requirements.txt
PYTHONPATH=ingest python3 -m festivos.cli local ES-CT 2026
PYTHONPATH=ingest python3 -m pytest ingest/tests   # si tocaste la lógica de matching
```

## Alcance

Este repositorio es el **núcleo de datos abierto**: el dataset, el pipeline que lo construye, el esquema y el servidor MCP. El servicio alojado, el sitio web y la capa comercial de la API viven en otro sitio. Las _issues_ y PR aquí deben tratar sobre los **datos y las herramientas**.
