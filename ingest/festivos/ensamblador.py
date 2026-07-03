"""Ensamblado del fichero municipio-año: nacional + autonómico (BOE) + local.

Combina los festivos nacionales y autonómicos que observa la CCAA del municipio
(del BOE) con sus fiestas locales (del nivel local ya generado en `data/`).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import licencia
from .modelo import Festivo, Fuente, Municipio, Nivel, Tipo
from .repos import MunicipioRepo

_SCHEMA_URL = "https://festivos.io/v1/schema/municipio.json"


def _festivo_desde_dict(d: dict) -> Festivo:
    """Reconstruye un `Festivo` desde su forma serializada (festivos locales)."""
    return Festivo(
        date=d["date"],
        name=d["name"],
        level=Nivel(d["level"]),
        type=Tipo(d["type"]),
        source=Fuente(**d["source"]),
        substitutable=d.get("substitutable"),
        notes=d.get("notes"),
    )


def carga_local(anyo: int, root: Path) -> dict[str, list[Festivo]]:
    """Carga las fiestas locales de todas las CCAA en `{ine: [Festivo, ...]}`."""
    por_ine: dict[str, list[Festivo]] = {}
    base = root / "data" / str(anyo) / "local"
    if not base.exists():
        return por_ine
    for fichero in sorted(base.glob("*.json")):
        data = json.loads(fichero.read_text(encoding="utf-8"))
        for municipio in data["municipios"]:
            por_ine[municipio["ine"]] = [_festivo_desde_dict(h)
                                         for h in municipio["holidays"]]
    return por_ine


def _locales(ine: str, anyo: int, iso: str, root: Path) -> list[Festivo]:
    """Lee las fiestas locales de un municipio desde `data/{anyo}/local/{iso}.json`."""
    fichero = root / "data" / str(anyo) / "local" / f"{iso}.json"
    if not fichero.exists():
        return []
    data = json.loads(fichero.read_text(encoding="utf-8"))
    for municipio in data["municipios"]:
        if municipio["ine"] == ine:
            return [_festivo_desde_dict(h) for h in municipio["holidays"]]
    return []


def festivos_de(municipio: Municipio, regional_por_ccaa: dict[str, list[Festivo]],
                local_por_ine: dict[str, list[Festivo]]) -> list[Festivo]:
    """Fusiona nacional + autonómico + local para un municipio (todo en memoria)."""
    festivos = list(regional_por_ccaa.get(municipio.ccaa_iso, []))
    festivos.extend(local_por_ine.get(municipio.ine, []))
    festivos.sort(key=lambda f: (f.date, f.level.value))
    return festivos


def festivos_municipio(ine: str, anyo: int, *, repo: MunicipioRepo,
                       regional_por_ccaa: dict[str, list[Festivo]],
                       root: Path) -> tuple[Municipio, list[Festivo]]:
    """Devuelve `(municipio, festivos)` con los 3 niveles fusionados y ordenados."""
    municipio = repo.por_ine(ine)
    if municipio is None:
        raise ValueError(f"código INE desconocido: {ine}")
    festivos = list(regional_por_ccaa.get(municipio.ccaa_iso, []))
    festivos.extend(_locales(ine, anyo, municipio.ccaa_iso, root))
    festivos.sort(key=lambda f: (f.date, f.level.value))
    return municipio, festivos


def municipio_json(municipio: Municipio, anyo: int,
                   festivos: list[Festivo]) -> dict:
    """Construye el dict del fichero municipio-año conforme al esquema."""
    return {
        "schema": _SCHEMA_URL,
        "version": "1.0.0",
        "year": anyo,
        **licencia.bloque(),
        "municipality": {
            "ine": municipio.ine,
            "name": municipio.name,
            "province": {"ine": municipio.province, "name": municipio.province_name},
            "ccaa": {"code": municipio.ccaa_iso, "name": municipio.ccaa_name},
        },
        "holidays": [f.to_dict() for f in festivos],
    }
