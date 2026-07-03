"""Línea de comandos del pipeline de ingesta.

Uso:
    PYTHONPATH=ingest python3 -m festivos.cli ref [AÑO]
    PYTHONPATH=ingest python3 -m festivos.cli local ES-CT [AÑO]
    PYTHONPATH=ingest python3 -m festivos.cli municipio 43148 [AÑO]
    PYTHONPATH=ingest python3 -m festivos.cli build [AÑO]
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from . import atribucion, boe
from .build import construye_anyo
from .ensamblador import festivos_municipio, municipio_json
from .escolar.construye import construye_escolar
from .fiscal.construye import construye_fiscal
from .local import construye
from .matching import Matcher
from .repos import MunicipioRepo
from .salidas.ics_writer import escribe_ics
from .salidas.json_writer import escribe_coleccion

ROOT = Path(__file__).resolve().parents[2]
_REF = ROOT / "v1" / "ref" / "municipios.json"


def _descarga_si_falta(url: str, destino: Path) -> Path:
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        print(f"Descargando {url} ...")
        urllib.request.urlretrieve(url, destino)
    return destino


def escribe_ref_ccaa(ref_municipios: Path, destino: Path) -> int:
    """Deriva v1/ref/ccaa.json de municipios.json: tabla CCAA (ISO↔CODAUTO) con sus
    provincias y recuentos. Misma fuente de verdad que municipios.json (INE)."""
    muni = json.loads(ref_municipios.read_text(encoding="utf-8"))["municipalities"]
    ccaa: dict[str, dict] = {}
    for m in muni:
        c = ccaa.setdefault(m["ccaa_iso"], {
            "iso": m["ccaa_iso"], "ine": m["ccaa_ine"], "name": m["ccaa_name"],
            "_prov": {}, "municipios": 0})
        c["municipios"] += 1
        c["_prov"].setdefault(m["province"], m["province_name"])
    lista = []
    for c in sorted(ccaa.values(), key=lambda x: x["ine"]):
        provincias = [{"ine": p, "name": n} for p, n in sorted(c.pop("_prov").items())]
        lista.append({**c, "provinces": provincias})
    destino.write_text(json.dumps({
        "schema": "https://festivos.io/v1/schema/ccaa.json",
        "version": "1.0.0",
        "source": "derivado de v1/ref/municipios.json (INE)",
        "count": len(lista),
        "ccaa": lista,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(lista)


def escribe_ref_search(ref_municipios: Path, destino: Path) -> int:
    """Índice de búsqueda ligero para el autocompletado del sitio: solo los campos
    de visualización/enlace (ine, nombre, provincia, CCAA). Derivado de municipios.json."""
    muni = json.loads(ref_municipios.read_text(encoding="utf-8"))["municipalities"]
    items = [{"ine": m["ine"], "name": m["name"],
              "province": m["province_name"], "ccaa": m["ccaa_iso"]} for m in muni]
    destino.write_text(json.dumps({
        "schema": "https://festivos.io/v1/schema/search.json",
        "version": "1.0.0",
        "source": "derivado de v1/ref/municipios.json (INE)",
        "count": len(items),
        "municipalities": items,
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return len(items)


def cmd_ref(anyo: int) -> None:
    """Genera v1/ref/{municipios,ccaa,search}.json desde el diccionario del INE."""
    yy = f"{anyo % 100:02d}"
    url = f"https://www.ine.es/daco/daco42/codmun/diccionario{yy}.xlsx"
    cache = _descarga_si_falta(url, ROOT / ".cache" / f"diccionario{yy}.xlsx")
    repo = MunicipioRepo.desde_ine(cache)
    meta = {
        "version": "1.0.0",
        "source": ("INE — Relación de municipios y sus códigos por provincias "
                   f"(diccionario{yy}.xlsx, ref. {anyo}-01-01)"),
        "source_url": url,
        "count": len(repo),
    }
    items = sorted((m.to_dict() for m in repo), key=lambda m: m["ine"])
    escribe_coleccion(_REF, meta, items, "municipalities")
    print(f"Escrito {_REF.relative_to(ROOT)} con {len(items)} municipios.")
    ccaa_dest = ROOT / "v1" / "ref" / "ccaa.json"
    n = escribe_ref_ccaa(_REF, ccaa_dest)
    print(f"Escrito {ccaa_dest.relative_to(ROOT)} con {n} CCAA.")
    search_dest = ROOT / "v1" / "ref" / "search.json"
    s = escribe_ref_search(_REF, search_dest)
    print(f"Escrito {search_dest.relative_to(ROOT)} con {s} municipios (índice ligero).")
    attr_dest = ROOT / "v1" / "ref" / "attribution.json"
    a = atribucion.escribe(attr_dest)
    print(f"Escrito {attr_dest.relative_to(ROOT)} con {a} CCAA + BOE/INE.")


def cmd_local(iso: str, anyo: int) -> None:
    """Genera data/{anyo}/local/{iso}.json con las fiestas locales de una CCAA."""
    repo = MunicipioRepo.desde_json(_REF)
    matcher = Matcher(repo)
    por_ine, no_resueltos = construye(iso, anyo, repo=repo, matcher=matcher)

    items = sorted(
        ({"ine": ine,
          "name": repo.por_ine(ine).name,
          "holidays": [f.to_dict() for f in festivos]}
         for ine, festivos in por_ine.items()),
        key=lambda x: x["ine"],
    )
    meta = {
        "version": "1.0.0",
        "year": anyo,
        "ccaa": iso,
        "count_municipios": len(items),
        "count_festivos": sum(len(x["holidays"]) for x in items),
    }
    salida = ROOT / "data" / str(anyo) / "local" / f"{iso}.json"
    escribe_coleccion(salida, meta, items, "municipios")
    print(f"Escrito {salida.relative_to(ROOT)}: "
          f"{meta['count_municipios']} municipios, {meta['count_festivos']} festivos.")
    if no_resueltos:
        unicos = sorted(set(no_resueltos))
        print(f"  Sin resolver nombre→INE: {len(no_resueltos)} "
              f"({len(unicos)} únicos). Ejemplos: {unicos[:8]}")
    if matcher.resueltos_fuzzy:
        pares = sorted({(n, repo.por_ine(i).name) for n, i in matcher.resueltos_fuzzy})
        print(f"  Resueltos por fuzzy (revisar): {len(pares)} → {pares[:5]}")


def cmd_municipio(ine: str, anyo: int) -> None:
    """Genera v1/{anyo}/municipio/{ine}.json y .ics (nacional+autonómico+local)."""
    repo = MunicipioRepo.desde_json(_REF)
    regional = boe.por_ccaa(anyo, root=ROOT)
    municipio, festivos = festivos_municipio(
        ine, anyo, repo=repo, regional_por_ccaa=regional, root=ROOT)

    destino = ROOT / "v1" / str(anyo) / "municipio"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"{ine}.json").write_text(
        json.dumps(municipio_json(municipio, anyo, festivos), ensure_ascii=False,
                   indent=2) + "\n",
        encoding="utf-8")
    escribe_ics(
        destino / f"{ine}.ics", festivos,
        nombre_calendario=f"Festivos {municipio.name} {anyo}",
        uid_scope=ine, dtstamp=f"{anyo:04d}0101T000000Z",
        fuente_url=f"https://festivos.io/v1/{anyo}/municipio/{ine}.ics")
    print(f"Escrito v1/{anyo}/municipio/{ine}.json y {ine}.ics "
          f"({len(festivos)} festivos: {municipio.name}, {municipio.ccaa_name}).")


def cmd_build(anyo: int) -> None:
    """Genera el dataset completo del año bajo v1/{anyo}/."""
    repo = MunicipioRepo.desde_json(_REF)
    resumen = construye_anyo(anyo, root=ROOT, repo=repo)
    print(f"Generado v1/{anyo}/: {resumen['municipios']} municipios (JSON+ICS), "
          f"regional.json + {resumen['ccaa']} ccaa/ + "
          f"{resumen['dias_inverso']} reverse/ + index.json + coverage.json.")


def cmd_fiscal(anyo: int) -> None:
    """Genera v1/{anyo}/fiscal.json y fiscal/{perfil}.json desde los feeds AEAT."""
    resumen = construye_fiscal(anyo, root=ROOT)
    pp = ", ".join(f"{p}={n}" for p, n in resumen["por_perfil"].items())
    print(f"Generado v1/{anyo}/fiscal.json: {resumen['deadlines']} plazos ({pp}).")


def cmd_escolar(anyo: int) -> None:
    """Genera v1/{anyo}/escolar.json y escolar/{ccaa}.json (curso anyo/anyo+1)."""
    resumen = construye_escolar(anyo, root=ROOT)
    print(f"Generado v1/{anyo}/escolar.json: {resumen['ccaa']} CCAA "
          f"(curso {anyo}-{anyo + 1}).")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="festivos", description="Pipeline de ingesta de festivos")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ref = sub.add_parser("ref", help="genera la referencia de municipios INE")
    p_ref.add_argument("anyo", nargs="?", type=int, default=2026)

    p_local = sub.add_parser("local", help="genera las fiestas locales de una CCAA")
    p_local.add_argument("ccaa", help="código ISO 3166-2, p. ej. ES-CT")
    p_local.add_argument("anyo", nargs="?", type=int, default=2026)

    p_muni = sub.add_parser("municipio", help="genera el fichero de un municipio")
    p_muni.add_argument("ine", help="código INE de 5 dígitos")
    p_muni.add_argument("anyo", nargs="?", type=int, default=2026)

    p_build = sub.add_parser("build", help="genera el dataset completo del año")
    p_build.add_argument("anyo", nargs="?", type=int, default=2026)

    p_fiscal = sub.add_parser("fiscal", help="genera el calendario fiscal (AEAT) del año")
    p_fiscal.add_argument("anyo", nargs="?", type=int, default=2026)

    p_escolar = sub.add_parser("escolar", help="genera el calendario escolar (CCAA) del curso")
    p_escolar.add_argument("anyo", nargs="?", type=int, default=2026)

    args = parser.parse_args(argv)
    if args.cmd == "ref":
        cmd_ref(args.anyo)
    elif args.cmd == "local":
        cmd_local(args.ccaa, args.anyo)
    elif args.cmd == "municipio":
        cmd_municipio(args.ine, args.anyo)
    elif args.cmd == "build":
        cmd_build(args.anyo)
    elif args.cmd == "fiscal":
        cmd_fiscal(args.anyo)
    elif args.cmd == "escolar":
        cmd_escolar(args.anyo)


if __name__ == "__main__":
    main()
