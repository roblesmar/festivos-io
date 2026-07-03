"""Construcción del calendario fiscal de un año desde los feeds iCal de la AEAT.

Estrategia: las fechas las da la AEAT (ya ajustadas a día hábil) en sus feeds
iCalendar; este módulo las filtra por año, extrae los modelos de la DESCRIPTION y
asigna perfiles con el catálogo. Cada plazo conserva su `source` (incluido el .ics).
Genera `v1/{año}/fiscal.json` y `v1/{año}/fiscal/{perfil}.json`.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from . import feeds
from .. import licencia

PERFILES: tuple[str, ...] = ("particular", "autonomo", "empresa")

_CAL_URL = ("https://sede.agenciatributaria.gob.es/Sede/ayuda/"
            "calendario-contribuyente/calendario-contribuyente-{anyo}.html")
_DISCLAIMER = (
    "Calendario orientativo basado en el Calendario del contribuyente de la AEAT. "
    "No sustituye a la fuente oficial ni constituye asesoramiento fiscal; comprueba "
    "siempre los plazos en sede.agenciatributaria.gob.es."
)
_MODELO = re.compile(r"\b(\d{3})\b")


def _descarga(url: str, cache: Path) -> str:
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "festivos.io/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            cache.write_bytes(r.read())
    return cache.read_text(encoding="utf-8", errors="replace")


def _unfold(texto: str) -> str:
    """Desdobla líneas plegadas (RFC 5545: continuación con espacio/tab)."""
    return re.sub(r"\r?\n[ \t]", "", texto)


def _vevents(texto: str):
    for blq in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", _unfold(texto), re.S):
        ev: dict[str, str] = {}
        for ln in blq.strip().split("\n"):
            if ":" in ln:
                clave, valor = ln.split(":", 1)
                ev[clave.split(";")[0]] = valor.strip()
        yield ev


def _limpia(desc: str) -> str:
    desc = re.sub(r"<[^>]+>", " ", desc)
    desc = desc.replace("\\,", ",").replace("\\;", ";")
    desc = re.sub(r"\\[nN]", " · ", desc)
    return re.sub(r"\s+", " ", desc).strip()


def _modelos(desc: str) -> list[str]:
    """Códigos de modelo (3 dígitos) citados en la descripción, en orden y únicos."""
    out: list[str] = []
    for m in _MODELO.findall(desc):
        if m not in out:
            out.append(m)
    return out


def _catalogo(root: Path) -> dict[str, dict]:
    data = json.loads((root / "data" / "fiscal" / "catalogo.json").read_text("utf-8"))
    return {o["model"]: o for o in data["obligations"]}


def _envelope(anyo: int, deadlines: list[dict], *, profile: str | None = None) -> dict:
    env: dict = {
        "schema": "https://festivos.io/v1/schema/fiscal.json",
        "version": "1.0.0",
        "country": "ES",
        "calendarType": "fiscal",
        "year": anyo,
    }
    if profile:
        env["profile"] = profile
    env["source"] = {"ref": f"AEAT — Calendario del contribuyente {anyo}",
                     "url": _CAL_URL.format(anyo=anyo)}
    env.update(licencia.bloque(disclaimer=_DISCLAIMER))
    env["count"] = len(deadlines)
    env["deadlines"] = deadlines
    return env


def _escribe(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def construye_fiscal(anyo: int, *, root: Path) -> dict:
    """Genera el calendario fiscal del año y devuelve un resumen."""
    cat = _catalogo(root)
    cache = root / ".cache" / "fiscal"
    deadlines: list[dict] = []
    vistos: set[tuple] = set()

    for i, url in enumerate(feeds.FEEDS):
        try:
            texto = _descarga(url, cache / f"feed_{i:02d}.ics")
        except Exception as exc:  # feed caído: se omite, nunca datos falsos
            print(f"  feed {i:02d}: sin datos ({exc})")
            continue
        for ev in _vevents(texto):
            dt = ev.get("DTSTART", "")
            if len(dt) < 8 or not dt[:4].isdigit() or int(dt[:4]) != anyo:
                continue
            fecha = f"{dt[0:4]}-{dt[4:6]}-{dt[6:8]}"
            figura = ev.get("SUMMARY", "").strip()
            desc = _limpia(ev.get("DESCRIPTION", ""))
            modelos = _modelos(desc)
            clave = (fecha, figura, desc[:80])
            if clave in vistos:
                continue
            vistos.add(clave)
            perfiles: set[str] = set()
            for m in modelos:
                if m in cat:
                    perfiles.update(cat[m]["profiles"])
            if not perfiles:  # sin modelo reconocido → obligación de empresa/autónomo
                perfiles = {"autonomo", "empresa"}
            deadlines.append({
                "date": fecha,
                "figure": figura,
                "category": feeds.categoria(figura),
                "models": modelos,
                "profiles": [p for p in PERFILES if p in perfiles],
                "name": {"es": desc[:400]},
                "source": {
                    "ref": f"AEAT — Calendario del contribuyente {anyo}",
                    "url": _CAL_URL.format(anyo=anyo),
                    "ical": url,
                },
            })

    deadlines.sort(key=lambda d: (d["date"], d["figure"]))
    base = root / "v1" / str(anyo)
    _escribe(base / "fiscal.json", _envelope(anyo, deadlines))
    por_perfil: dict[str, int] = {}
    for p in PERFILES:
        fp = [d for d in deadlines if p in d["profiles"]]
        por_perfil[p] = len(fp)
        _escribe(base / "fiscal" / f"{p}.json", _envelope(anyo, fp, profile=p))

    return {"deadlines": len(deadlines), "por_perfil": por_perfil}
