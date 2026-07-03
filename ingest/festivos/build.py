"""Generación del dataset completo de un año bajo `v1/`.

Produce, para todos los municipios: el fichero municipio-año (JSON + ICS) y los
índices agregados (regional, por CCAA, inverso por día e índice de municipios).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from . import boe, cobertura, licencia
from .ensamblador import carga_local, festivos_de, municipio_json
from .modelo import Festivo, Nivel
from .repos import MunicipioRepo
from .salidas.ics_writer import escribe_ics


def _escribe_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _nacionales(regional: dict[str, list[Festivo]]) -> list[Festivo]:
    """Festivos nacionales (compartidos por las CCAA), únicos por fecha."""
    vistos: dict[str, Festivo] = {}
    for festivos in regional.values():
        for f in festivos:
            if f.level == Nivel.NACIONAL:
                vistos.setdefault(f.date, f)
    return sorted(vistos.values(), key=lambda f: f.date)


def construye_anyo(anyo: int, *, root: Path, repo: MunicipioRepo) -> dict:
    """Genera todo el dataset del año bajo `v1/{anyo}/` y devuelve un resumen."""
    base = root / "v1" / str(anyo)
    regional = boe.por_ccaa(anyo, root=root)
    local = carga_local(anyo, root)
    dtstamp = f"{anyo:04d}0101T000000Z"
    nombres_ccaa = {m.ccaa_iso: m.ccaa_name for m in repo}

    inverso: dict[str, dict] = defaultdict(
        lambda: {"national": False, "regional": set(), "local": []})
    indice: list[dict] = []

    for muni in repo:
        festivos = festivos_de(muni, regional, local)
        _escribe_json(base / "municipio" / f"{muni.ine}.json",
                      municipio_json(muni, anyo, festivos))
        escribe_ics(base / "municipio" / f"{muni.ine}.ics", festivos,
                    nombre_calendario=f"Festivos {muni.name} {anyo}",
                    uid_scope=muni.ine, dtstamp=dtstamp,
                    fuente_url=f"https://festivos.io/v1/{anyo}/municipio/{muni.ine}.ics")
        indice.append({"ine": muni.ine, "name": muni.name,
                       "province_ine": muni.province, "ccaa": muni.ccaa_iso})
        for f in festivos:
            registro = inverso[f.date[5:]]
            if f.level == Nivel.NACIONAL:
                registro["national"] = True
            elif f.level == Nivel.AUTONOMICO:
                registro["regional"].add(muni.ccaa_iso)
            else:
                registro["local"].append(muni.ine)

    _escribe_json(base / "regional.json", {
        "version": "1.0.0", "year": anyo, **licencia.bloque(),
        "national": [f.to_dict() for f in _nacionales(regional)],
        "regions": {iso: {"name": nombres_ccaa.get(iso, iso),
                          "holidays": [f.to_dict() for f in fs
                                       if f.level == Nivel.AUTONOMICO]}
                    for iso, fs in regional.items()},
    })
    for iso, fs in regional.items():
        _escribe_json(base / "ccaa" / f"{iso}.json", {
            "version": "1.0.0", "year": anyo, "ccaa": iso,
            "name": nombres_ccaa.get(iso, iso), **licencia.bloque(),
            "holidays": [f.to_dict() for f in fs]})

    for md, registro in inverso.items():
        _escribe_json(base / "reverse" / f"{md}.json", {
            "version": "1.0.0", "year": anyo, "date": f"{anyo}-{md}",
            **licencia.bloque(),
            "national": registro["national"],
            "regional": sorted(registro["regional"]),
            "local": {"count": len(registro["local"]),
                      "municipalities": sorted(registro["local"])}})

    _escribe_json(base / "index.json", {
        "version": "1.0.0", "year": anyo, "count": len(indice),
        **licencia.bloque(), "municipalities": indice})

    # Métricas de cobertura (única fuente de verdad): lee lo recién escrito.
    cov = cobertura.escribir(anyo, root / "v1")

    return {"municipios": len(indice), "dias_inverso": len(inverso),
            "ccaa": len(regional), "coverage": str(cov)}
