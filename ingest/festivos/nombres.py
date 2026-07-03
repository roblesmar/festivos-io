"""Nombres curados (verificables) de fiestas locales.

El boletín oficial de varias CCAA publica solo la FECHA del festivo local, no su
nombre. Esta tabla (`data/nombres-locales.json`), curada y con fuente, aporta el
nombre real por municipio (código INE) y día (MM-DD); se aplica sobre el nivel
local en todos los años. Se amplía por Pull Request (cada entrada lleva su fuente).
Las fiestas móviles (cuya fecha cambia cada año) se resuelven por cómputo de Pascua.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _indice() -> dict[tuple[str, str], dict]:
    fichero = _RAIZ / "data" / "nombres-locales.json"
    if not fichero.exists():
        return {}
    data = json.loads(fichero.read_text(encoding="utf-8"))
    idx: dict[tuple[str, str], dict] = {}
    for ine, entradas in data.get("municipios", {}).items():
        for entrada in entradas:
            idx[(ine, entrada["mmdd"])] = entrada
    return idx


def nombre_override(ine: str, fecha_iso: str) -> dict[str, str] | None:
    """Devuelve el nombre i18n curado para (INE, fecha `YYYY-MM-DD`) o None."""
    entrada = _indice().get((ine, fecha_iso[5:]))
    return entrada["name"] if entrada else None


def _domingo_pascua(anyo: int) -> date:
    """Domingo de Pascua (cómputo gregoriano, algoritmo anónimo)."""
    a = anyo % 19
    b, c = divmod(anyo, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    mes = (h + el - 7 * m + 114) // 31
    dia = ((h + el - 7 * m + 114) % 31) + 1
    return date(anyo, mes, dia)


@lru_cache(maxsize=16)
def _segona_pasqua(anyo: int) -> str:
    """Dilluns de Pentecosta (Segona Pasqua / Pasqua Granada): Pascua + 50 días."""
    return (_domingo_pascua(anyo) + timedelta(days=50)).isoformat()


def nombre_movil(iso: str, anyo: int, fecha_iso: str) -> dict[str, str] | None:
    """Nombre de fiestas móviles deducibles por su fecha (relativa a la Pascua).

    De momento la Segona Pasqua en Cataluña, que cae cada año en una fecha distinta.
    """
    if iso == "ES-CT" and fecha_iso == _segona_pasqua(anyo):
        return {"ca": "Segona Pasqua", "es": "Segunda Pascua (Pascua Granada)"}
    return None
