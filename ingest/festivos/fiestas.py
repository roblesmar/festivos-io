"""Canonicaliza nombres de fiesta y agrega POR FIESTA (no por municipio).

Une las variantes con que cada boletín escribe el mismo nombre (mayúsculas,
acentos, espacios): «SAN ISIDRO» / «San Isidro» → una sola entidad, para poder
describir una fiesta como «se celebra en estos municipios y estas fechas».

Lee `v1/{año}/municipio/*.json` (salida ya ensamblada) y escribe:
  - `v1/ref/fiestas.json`  — índice canónico (slug, nombre, variantes, nivel,
                             tier, alcance por año).
  - `v1/{año}/fiestas.json` — tabla «dónde» por año de las fiestas LOCALES
                             (slug → municipios con su fecha).

Tier (solo local), según en cuántos municipios se celebra: head ≥5 · mid 2-4 ·
single 1.

Uso: `python -m festivos.fiestas` (o invocado desde el build tras ensamblar).
"""
from __future__ import annotations

import collections
import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ANIOS = ("2024", "2025", "2026")
# nombres genéricos (sin valor propio): no generan fiesta canónica
GENERICOS = {"fiesta local", "festivo local", "festividad local", "fiestas locales", "fiesta patronal"}

# Alias de canonicalización (curado): nombres DISTINTOS de la MISMA fiesta —por
# idioma o por inconsistencia de naming entre años en el boletín—. Mapea la clave
# de cada variante a una clave canónica única; DISPLAY fuerza el nombre mostrado.
# Se amplía por Pull Request. Cuidado: NO fusionar fiestas distintas
# (p. ej. «Lunes de Pascua» = Pascua+1 ≠ «Segona Pasqua» = Pascua+50).
ALIAS = {
    # Dilluns de Pentecosta (CAT): «Segunda Pascua (Pascua Granada)» (2024-25, con
    # override es) ≡ «Segona Pasqua» (2026, sin override). El nombre ca es estable.
    "segunda pascua pascua granada": "segona pasqua",
}
DISPLAY = {
    "segona pasqua": "Segona Pasqua",
}


def _clave(nombre: str) -> str:
    """Clave de agrupación: sin acentos, minúsculas, alfanumérico colapsado."""
    s = unicodedata.normalize("NFKD", nombre)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _slug(nombre: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _clave(nombre)).strip("-")


def _score_display(v: str) -> tuple[bool, bool]:
    """Mejor variante para mostrar: Mixed Case y con acentos (forma del boletín)."""
    mixed = not v.isupper() and not v.islower()
    acentos = any(unicodedata.combining(c) for c in unicodedata.normalize("NFKD", v))
    return (mixed, acentos)


def generar() -> dict:
    grupos: dict[str, dict] = collections.defaultdict(
        lambda: {"var": collections.Counter(), "niv": collections.Counter(),
                 "anios": {a: {} for a in ANIOS}})

    for anio in ANIOS:
        for fichero in (RAIZ / "v1" / anio / "municipio").glob("*.json"):
            try:
                d = json.loads(fichero.read_text(encoding="utf-8"))
            except Exception:
                continue
            m = d.get("municipality", {})
            ine = m.get("ine")
            prov = m.get("province", {}).get("name")
            ccaa = m.get("ccaa", {}).get("name")
            ccode = m.get("ccaa", {}).get("code")
            for h in d.get("holidays", []):
                nm = (h.get("name", {}).get("es") or "").strip()
                k = _clave(nm)
                if not k or k in GENERICOS:
                    continue
                k = ALIAS.get(k, k)
                g = grupos[k]
                g["var"][nm] += 1
                g["niv"][h.get("level")] += 1
                if h.get("level") == "local":
                    g["anios"][anio][ine] = {"ine": ine, "name": m.get("name"), "prov": prov,
                                             "ccaa": ccaa, "ccode": ccode, "date": h.get("date")}

    indice: list[dict] = []
    donde: dict[str, dict] = {a: {} for a in ANIOS}
    enlace: dict[str, str] = {}  # clave de nombre → slug, solo de fiestas con nombre propio
    usados: dict[str, str] = {}
    for k, g in grupos.items():
        nivel = g["niv"].most_common(1)[0][0]
        display = DISPLAY.get(k) or max(g["var"], key=lambda v: (_score_display(v), g["var"][v]))
        slug = _slug(display) or k.replace(" ", "-")
        base, n = slug, 2
        while slug in usados and usados[slug] != k:
            slug = f"{base}-{n}"
            n += 1
        usados[slug] = k
        por_anio = {a: len(g["anios"][a]) for a in ANIOS if g["anios"][a]}
        total = (len({ine for a in ANIOS for ine in g["anios"][a]})
                 if nivel == "local" else g["niv"][nivel])
        tier = (("head" if total >= 5 else "mid" if total >= 2 else "single")
                if nivel == "local" else nivel)
        indice.append({"slug": slug, "name": display, "level": nivel, "tier": tier,
                       "variants": [v for v, _ in g["var"].most_common(6)],
                       "anios": por_anio, "municipios": total if nivel == "local" else None})
        if tier == "head" or nivel in ("national", "regional"):
            enlace[k] = slug
        if nivel == "local":
            for a in ANIOS:
                if g["anios"][a]:
                    donde[a][slug] = sorted(g["anios"][a].values(),
                                            key=lambda x: (x["ccaa"] or "", x["name"] or ""))

    indice.sort(key=lambda x: (-(x["municipios"] or 0), x["name"]))
    (RAIZ / "v1" / "ref").mkdir(parents=True, exist_ok=True)
    (RAIZ / "v1" / "ref" / "fiestas.json").write_text(
        json.dumps({"schema": "https://festivos.io/v1/schema/fiestas.json", "version": "0.1.0",
                    "count": len(indice), "fiestas": indice}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    for a in ANIOS:
        (RAIZ / "v1" / a / "fiestas.json").write_text(
            json.dumps({"year": int(a), "fiestas": donde[a]}, ensure_ascii=False,
                       separators=(",", ":")), encoding="utf-8")
    # mapa compacto nombre→slug para enlazar desde las páginas de municipio (worker)
    (RAIZ / "v1" / "ref" / "fiestas-link.json").write_text(
        json.dumps(enlace, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {"total": len(indice), "indice": indice, "enlaces": len(enlace)}


def main() -> None:
    res = generar()
    idx = res["indice"]
    loc = [x for x in idx if x["level"] == "local"]
    tiers = collections.Counter(x["tier"] for x in loc)
    niveles = collections.Counter(x["level"] for x in idx)
    print(f"fiestas canónicas: {res['total']}  ·  {dict(niveles)}")
    print(f"locales por tier:  {dict(tiers)}  (head = las más extendidas)")


if __name__ == "__main__":
    main()
