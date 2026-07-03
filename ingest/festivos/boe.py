"""Festivos nacionales y autonómicos desde el BOE.

El BOE publica cada año la «relación de fiestas laborales» con una tabla girada
(`tabla_girada_condensada`): filas = fechas (precedidas por una fila de mes),
columnas = las 19 CCAA. Cada celda marcada indica un festivo:
  `*`   nacional no sustituible
  `**`  nacional sustituible
  `***` autonómico
Devolvemos, por CCAA (ISO 3166-2), la lista de `Festivo` (nacionales + autonómicos)
que observa esa comunidad.
"""
from __future__ import annotations

import html
import re
import unicodedata
import urllib.request
from pathlib import Path

from .modelo import Festivo, Fuente, Nivel, Tipo

# Identificador del documento BOE por año.
_BOE_ID: dict[int, str] = {
    2023: "BOE-A-2022-16755",
    2024: "BOE-A-2023-22014",
    2025: "BOE-A-2024-21316",
    2026: "BOE-A-2025-21667",
}

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}

# Festivos móviles (dependientes de la Pascua).
_MOVILES = {
    "jueves santo", "viernes santo", "lunes de pascua florida",
    "lunes de pascua", "corpus christi",
}


def _normaliza(texto: str) -> str:
    """Minúsculas, sin tildes y sin paréntesis (notas al pie)."""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"\(.*?\)", "", t)
    return " ".join(t.replace(".", " ").split())


# Cabecera de columna (texto normalizado, sin prefijos) -> ISO 3166-2.
_NOMBRE_ISO = {
    "andalucia": "ES-AN", "aragon": "ES-AR", "asturias": "ES-AS",
    "balears": "ES-IB", "baleares": "ES-IB", "canarias": "ES-CN",
    "cantabria": "ES-CB", "castilla y leon": "ES-CL",
    "castilla-la mancha": "ES-CM", "castilla la mancha": "ES-CM",
    "cataluna": "ES-CT", "valenciana": "ES-VC", "extremadura": "ES-EX",
    "galicia": "ES-GA", "madrid": "ES-MD", "murcia": "ES-MC",
    "navarra": "ES-NC", "pais vasco": "ES-PV", "rioja": "ES-RI",
    "la rioja": "ES-RI", "ceuta": "ES-CE", "melilla": "ES-ML",
}

_PREFIJOS = ("comunidad foral de ", "comunidad de ", "comunitat ",
             "principado de ", "region de ", "islas ", "illes ")


def _resuelve_iso(cabecera: str) -> str:
    """Resuelve el nombre de una columna de CCAA del BOE a su código ISO."""
    t = _normaliza(cabecera)
    for pref in _PREFIJOS:
        if t.startswith(pref):
            t = t[len(pref):]
    t = t.strip()
    if t in _NOMBRE_ISO:
        return _NOMBRE_ISO[t]
    for nombre, iso in _NOMBRE_ISO.items():
        if nombre in t:
            return iso
    raise ValueError(f"CCAA no reconocida en la cabecera del BOE: {cabecera!r}")


def _descarga(anyo: int, root: Path) -> str:
    """Descarga (o lee de caché) el XML del documento BOE del año."""
    if anyo not in _BOE_ID:
        raise ValueError(f"sin identificador BOE configurado para {anyo}")
    boe_id = _BOE_ID[anyo]
    cache = root / ".cache" / f"boe_{boe_id}.xml"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    url = f"https://www.boe.es/diario_boe/xml.php?id={boe_id}"
    with urllib.request.urlopen(url) as resp:
        bruto = resp.read().decode("utf-8", "replace")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(bruto, encoding="utf-8")
    return bruto


def _texto(celda_html: str) -> str:
    """Quita el marcado y desescapa las entidades de una celda."""
    return html.unescape(re.sub(r"<[^>]+>", "", celda_html)).strip()


def por_ccaa(anyo: int, *, root: Path) -> dict[str, list[Festivo]]:
    """Devuelve `{iso: [Festivo, ...]}` con los nacionales y autonómicos del año."""
    xml = _descarga(anyo, root)
    tabla = xml[xml.find('class="tabla_girada_condensada"'):]
    thead = tabla[tabla.find("<thead"):tabla.find("</thead>")]
    cabeceras = re.findall(r'<th[^>]*axis="comunidad"[^>]*>(.*?)</th>', thead, re.S)
    col_iso = [_resuelve_iso(_texto(c)) for c in cabeceras]

    src = Fuente(ref=_BOE_ID[anyo],
                 url=f"https://www.boe.es/diario_boe/txt.php?id={_BOE_ID[anyo]}")
    resultado: dict[str, list[Festivo]] = {iso: [] for iso in col_iso}

    tbody = tabla[tabla.find("<tbody>"):tabla.find("</tbody>")]
    mes: int | None = None
    for fila in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.S):
        celdas = [_texto(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", fila, re.S)]
        if not celdas:
            continue
        etiqueta = celdas[0]
        clave = _normaliza(etiqueta)
        if clave in _MESES:
            mes = _MESES[clave]
            continue
        m = re.match(r"^\s*(\d{1,2})\s+(.*)", etiqueta)
        if not m or mes is None:
            continue
        fecha = f"{anyo:04d}-{mes:02d}-{int(m.group(1)):02d}"
        nombre = m.group(2).strip().rstrip(".").strip()
        tipo = Tipo.MOVIL if _normaliza(nombre) in _MOVILES else Tipo.FIJO
        for idx, iso in enumerate(col_iso, start=1):
            marca = celdas[idx] if idx < len(celdas) else ""
            if not marca:
                continue
            if marca == "***":
                nivel, sustituible = Nivel.AUTONOMICO, None
            else:  # "*" o "**"
                nivel, sustituible = Nivel.NACIONAL, (marca == "**")
            resultado[iso].append(Festivo(
                date=fecha, name={"es": nombre}, level=nivel, type=tipo,
                source=src, substitutable=sustituible,
            ))

    for festivos in resultado.values():
        festivos.sort(key=lambda f: f.date)
    return resultado
