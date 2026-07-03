"""Registro de atribución legal por fuente — para cumplir CC BY 4.0 y la Ley 37/2007.

El dataset se publica bajo CC BY 4.0 conservando la atribución a las administraciones
de origen. Cada festivo lleva su `source` (ref + url al documento concreto); este
registro aporta el EDITOR oficial y la base legal por nivel/CCAA, que el sitio y los
`.ics` deben mostrar:

- nivel national/regional → clave `BOE`.
- nivel local → clave de la CCAA del municipio (`ES-XX`).
- tabla de municipios → clave `INE`.

Curado a mano (los nombres de editor no se derivan del dato). Base legal por defecto:
Ley 37/2007 (reutilización de información del sector público, con cita de la fuente).
Donde la fuente publica con licencia abierta explícita, se indica en `license`.
"""
from __future__ import annotations

import json
from pathlib import Path

_LEY = "Ley 37/2007 (reutilización de información del sector público; cita la fuente)"

# Editor oficial de las fiestas locales por CCAA (ISO 3166-2:ES).
_EDITOR_CCAA: dict[str, str] = {
    "ES-AN": "Junta de Andalucía",
    "ES-AR": "Gobierno de Aragón — Aragón Open Data",
    "ES-AS": "Gobierno del Principado de Asturias",
    "ES-IB": "Govern de les Illes Balears",
    "ES-CN": "Gobierno de Canarias",
    "ES-CB": "Gobierno de Cantabria",
    "ES-CL": "Junta de Castilla y León",
    "ES-CM": "Junta de Comunidades de Castilla-La Mancha",
    "ES-CT": "Generalitat de Catalunya — Departament d'Empresa i Treball",
    "ES-VC": "Generalitat Valenciana",
    "ES-EX": "Junta de Extremadura",
    "ES-GA": "Xunta de Galicia",
    "ES-MD": "Comunidad de Madrid",
    "ES-MC": "Región de Murcia (CARM)",
    "ES-NC": "Gobierno de Navarra — Nafarroako Gobernua",
    "ES-PV": "Gobierno Vasco — Eusko Jaurlaritza",
    "ES-RI": "Gobierno de La Rioja",
    "ES-CE": "Ciudad Autónoma de Ceuta",
    "ES-ML": "Ciudad Autónoma de Melilla",
}

# Licencia abierta explícita donde la conocemos (lo demás, base legal Ley 37/2007).
_LICENCIA_CCAA: dict[str, str] = {
    "ES-AR": "CC BY 4.0 (Aragón Open Data)",
}

# URL del editor/portal donde está documentada (solo las verificadas en FUENTES.md).
_URL_CCAA: dict[str, str] = {
    "ES-AN": "https://www.juntadeandalucia.es",
    "ES-AR": "https://opendata.aragon.es",
    "ES-CT": "https://analisi.transparenciacatalunya.cat/resource/b4eh-r8up.json",
}


def _entrada(publisher: str, *, legal: str = _LEY, license: str | None = None,
             url: str | None = None) -> dict:
    e = {"publisher": publisher, "citation": f"Fuente: {publisher}", "legal_basis": legal}
    if license:
        e["license"] = license
    if url:
        e["url"] = url
    return e


def registro() -> dict:
    return {
        "schema": "https://festivos.io/v1/schema/attribution.json",
        "version": "1.0.0",
        "note": ("Cada festivo conserva su 'source' (documento concreto). Este registro "
                 "da el editor oficial y la base legal por nivel/CCAA para la atribución."),
        "dataset": {
            "title": "festivos.io",
            "publisher": "festivos.io",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
        },
        # national + regional → BOE
        "national_regional": _entrada(
            "Agencia Estatal Boletín Oficial del Estado (BOE)", url="https://www.boe.es"),
        # tabla de municipios → INE
        "reference": _entrada(
            "Instituto Nacional de Estadística (INE)", url="https://www.ine.es"),
        # local → por CCAA del municipio
        "local_por_ccaa": {
            iso: _entrada(pub, license=_LICENCIA_CCAA.get(iso), url=_URL_CCAA.get(iso))
            for iso, pub in _EDITOR_CCAA.items()
        },
    }


def escribe(destino: Path) -> int:
    destino.write_text(json.dumps(registro(), ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return len(_EDITOR_CCAA)
