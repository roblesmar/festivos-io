"""Métricas de cobertura — única fuente de verdad de los porcentajes.

Lee el dataset YA GENERADO (`v1/{año}/municipio/*.json`, la verdad combinada
nacional+autonómico+local) y clasifica cada municipio según su fiesta LOCAL:

- ``con_nombre_propio``: tiene ≥1 festivo local con nombre real (Santa Tecla, San
  Isidro, Segona Pasqua…).
- ``generico_solo``: tiene festivo(s) local(es) pero TODOS con nombre genérico
  («Festivo local» / «Festa local» / «Fiestas locales»…): dato presente pero sin
  denominación.
- ``sin_local``: no hay ningún festivo local en el dato.

«con_local» = con_nombre_propio + generico_solo.

Salida:
- ``v1/{año}/coverage.json`` (nacional + desglose por CCAA). Es la fuente de verdad
  de los porcentajes; léelo, no lo recalcules a mano.
- ``v1/{año}/indexable.json`` — lista de INE de los municipios ``con_nombre_propio``
  (los que aportan una denominación local propia).

Uso:
    PYTHONPATH=ingest python -m festivos.cobertura 2026 2025 2024
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Formas genéricas (placeholder) en es/ca/gl/eu: «Festivo local», «Festa local»,
# «Fiestas locales», «Festiu local», «Tokiko jaia»… NO casa nombres reales como
# «Festa Major» (major ≠ local) ni advocaciones de santos.
GENERICO_RE = re.compile(
    r"^(festivo|festa|festiu|fiesta|festes|fiestas|festius|festividad|"
    r"dia festivo|día festivo)\s+(local|locals|locales)$"
    r"|^(tokiko|udal|herriko)\s+jaiak?$",
)


def _es_generico(valor: str) -> bool:
    return bool(GENERICO_RE.search(valor.strip().lower()))


def _tiene_nombre_propio(festivo: dict) -> bool:
    """Un festivo local está «nombrado» si alguna de sus lenguas no es genérica."""
    nombres = festivo.get("name") or {}
    vals = [v for v in nombres.values() if v and v.strip()]
    if not vals:
        return False
    return any(not _es_generico(v) for v in vals)


def _clasificar(holidays: list[dict]) -> str:
    locales = [h for h in holidays if h.get("level") == "local"]
    if not locales:
        return "sin_local"
    if any(_tiene_nombre_propio(h) for h in locales):
        return "con_nombre_propio"
    return "generico_solo"


def _pct(n: int, total: int) -> float:
    return round(100 * n / total, 1) if total else 0.0


def calcular(anio: int, v1_dir: str | Path = "v1") -> dict:
    base = Path(v1_dir) / str(anio) / "municipio"
    ficheros = sorted(base.glob("*.json"))
    if not ficheros:
        raise FileNotFoundError(f"No hay municipios generados en {base} (¿ejecutaste `build {anio}`?)")

    CLASES = ("con_nombre_propio", "generico_solo", "sin_local")
    nacional = {c: 0 for c in CLASES}
    por_ccaa: dict[str, dict] = {}

    for f in ficheros:
        d = json.loads(f.read_text(encoding="utf-8"))
        clase = _clasificar(d.get("holidays", []))
        nacional[clase] += 1

        ccaa = (d.get("municipality", {}).get("ccaa", {}) or {})
        code = ccaa.get("code", "??")
        c = por_ccaa.setdefault(code, {"ccaa": code, "name": ccaa.get("name", ""), "total": 0, **{k: 0 for k in CLASES}})
        c["total"] += 1
        c[clase] += 1

    total = len(ficheros)

    def bloque(d: dict, tot: int) -> dict:
        con_local = d["con_nombre_propio"] + d["generico_solo"]
        return {
            "total": tot,
            "con_local": {"n": con_local, "pct": _pct(con_local, tot)},
            "con_nombre_propio": {"n": d["con_nombre_propio"], "pct": _pct(d["con_nombre_propio"], tot)},
            "generico_solo": {"n": d["generico_solo"], "pct": _pct(d["generico_solo"], tot)},
            "sin_local": {"n": d["sin_local"], "pct": _pct(d["sin_local"], tot)},
        }

    return {
        "schema": "https://festivos.io/v1/schema/coverage.json",
        "year": anio,
        "source": f"v1/{anio}/municipio/*.json",
        "definicion": {
            "con_nombre_propio": "≥1 festivo local con nombre real",
            "generico_solo": "festivo(s) local(es) pero todos con nombre genérico",
            "sin_local": "sin festivo local en el dato",
            "generico_regex": GENERICO_RE.pattern,
        },
        "total_municipios": total,
        "nacional": bloque(nacional, total),
        "por_ccaa": [
            bloque({k: c[k] for k in CLASES}, c["total"]) | {"ccaa": c["ccaa"], "name": c["name"]}
            for c in sorted(por_ccaa.values(), key=lambda x: x["ccaa"])
        ],
    }


def escribir(anio: int, v1_dir: str | Path = "v1") -> Path:
    cov = calcular(anio, v1_dir)
    destino = Path(v1_dir) / str(anio) / "coverage.json"
    destino.write_text(json.dumps(cov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destino


def indexables(anio: int, v1_dir: str | Path = "v1") -> list[str]:
    """INE (ordenados) de los municipios ``con_nombre_propio`` del año dado."""
    base = Path(v1_dir) / str(anio) / "municipio"
    out: list[str] = []
    for f in sorted(base.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if _clasificar(d.get("holidays", [])) == "con_nombre_propio":
            out.append((d.get("municipality", {}) or {}).get("ine") or f.stem)
    return sorted(out)


def escribir_indexable(anio: int, v1_dir: str | Path = "v1") -> Path:
    ines = indexables(anio, v1_dir)
    destino = Path(v1_dir) / str(anio) / "indexable.json"
    destino.write_text(
        json.dumps(
            {
                "schema": "https://festivos.io/v1/schema/indexable.json",
                "year": anio,
                "source": f"v1/{anio}/municipio/*.json",
                "definicion": "INE de municipios con ≥1 festivo local con nombre propio.",
                "count": len(ines),
                "ines": ines,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destino


def _main(argv: list[str]) -> int:
    anios = [int(a) for a in argv] or [2026]
    for anio in anios:
        cov = calcular(anio)
        destino = escribir(anio)
        idx = escribir_indexable(anio)
        n = cov["nacional"]
        print(f"\n{anio}  ({cov['total_municipios']} municipios)  → {destino}")
        for k in ("con_local", "con_nombre_propio", "generico_solo", "sin_local"):
            b = n[k]
            print(f"  {k:18s} {b['n']:6d}  {b['pct']:5.1f}%")
        print(f"  {'indexable (sitemap)':18s} {json.loads(idx.read_text())['count']:6d}         → {idx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
