"""Ensamblado del calendario escolar de un curso desde los datos canónicos.

Lee `data/escolar/{curso}/{ccaa}.json` y emite el resumen por CCAA y el detalle
de cada una bajo `v1/{año}/`. El año de salida es el natural de inicio del curso
(2026 = curso 2026-2027). Falla limpio si no hay datos del curso (nunca inventa).
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import licencia

_DISCLAIMER = (
    "Calendario escolar orientativo basado en la normativa autonómica. Cada centro "
    "puede fijar días no lectivos de libre disposición adicionales; consulta el "
    "calendario de tu centro y el boletín oficial correspondiente."
)


def _escribe(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def construye_escolar(anyo: int, *, root: Path) -> dict:
    """Genera v1/{anyo}/escolar.json y escolar/{ccaa}.json. Devuelve un resumen."""
    curso = f"{anyo}-{anyo + 1}"
    origen = root / "data" / "escolar" / curso
    if not origen.exists():
        raise SystemExit(f"sin datos escolares para el curso {curso} ({origen})")

    base = root / "v1" / str(anyo)
    regiones: list[dict] = []

    for fp in sorted(origen.glob("*.json")):
        c = json.loads(fp.read_text(encoding="utf-8"))
        detalle = {
            "schema": "https://festivos.io/v1/schema/escolar-ccaa.json",
            "version": "1.0.0",
            "country": "ES",
            "calendarType": "escolar",
            "year": anyo,
            "course": curso,
            "ccaa": c["ccaa"],
            "confidence": c.get("confidence"),
            "source": c["source"],
            **licencia.bloque(disclaimer=_DISCLAIMER),
            "terms": c.get("terms", []),
            "breaks": c.get("breaks", []),
            "nonSchoolDays": c.get("nonSchoolDays", []),
        }
        if c.get("notes"):
            detalle["notes"] = c["notes"]
        _escribe(base / "escolar" / f"{c['ccaa']['code']}.json", detalle)

        starts = [t["start"] for t in c.get("terms", []) if t.get("start")]
        ends = [t["end"] for t in c.get("terms", []) if t.get("end")]
        regiones.append({
            "ccaa": c["ccaa"]["code"],
            "name": c["ccaa"]["name"],
            "termStart": min(starts) if starts else None,
            "termEnd": max(ends) if ends else None,
            "confidence": c.get("confidence"),
            "source": {"ref": c["source"].get("ref"), "url": c["source"].get("url")},
        })

    regiones.sort(key=lambda r: r["ccaa"])
    _escribe(base / "escolar.json", {
        "schema": "https://festivos.io/v1/schema/escolar.json",
        "version": "1.0.0",
        "country": "ES",
        "calendarType": "escolar",
        "year": anyo,
        "course": curso,
        "disclaimer": _DISCLAIMER,
        "count": len(regiones),
        "regions": regiones,
    })
    return {"ccaa": len(regiones)}
