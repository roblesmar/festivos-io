"""Normalización de nombres de municipio y join nombre→INE.

14 de las 19 fuentes de fiestas locales identifican el municipio por nombre, no por
código INE. Este módulo resuelve ese nombre al código INE contra el MunicipioRepo,
acotando por provincia o CCAA para desambiguar. Primero intenta un match exacto
(tras normalizar) y, si falla, un match difuso conservador (umbral alto + margen).
"""
from __future__ import annotations

import os
import re
import unicodedata
from collections import defaultdict

from .modelo import Municipio
from .repos import MunicipioRepo

try:
    from rapidfuzz import fuzz
    _HAY_FUZZY = True
except ImportError:  # rapidfuzz es opcional; sin él, solo match exacto
    _HAY_FUZZY = False

# Artículos que aparecen pospuestos en los nombres oficiales (es/ca/gl).
_ARTICULOS = {"EL", "LA", "LOS", "LAS", "L'", "ELS", "LES",
              "O", "A", "OS", "AS", "SA", "SES", "S'", "ES"}


def _reordena_articulo(s: str) -> str:
    """Reubica el artículo pospuesto al frente.

    'Alcázares, Los' -> 'Los Alcázares'; 'Acebrón (El)' -> 'El Acebrón'.
    """
    m = re.match(r"^(.*?)[,(]\s*([A-Za-zÀ-ÿ']{1,4})\)?\s*$", s)
    if m:
        base, articulo = m.group(1).strip(), m.group(2)
        if articulo.upper().replace("’", "'").replace("´", "'") in _ARTICULOS:
            return f"{articulo} {base}"
    return s


def normaliza(nombre: str) -> str:
    """Forma canónica para comparar nombres de municipio.

    Mayúsculas, sin diacríticos, artículo pospuesto al frente, bilingües con barra
    unificados ('Donostia / San Sebastián' -> 'DONOSTIA/SAN SEBASTIAN') y guiones
    como espacios ('Torre-Pacheco' == 'Torre Pacheco').
    """
    s = _reordena_articulo(nombre.strip())
    s = unicodedata.normalize("NFD", s.upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("’", "'").replace("´", "'").replace("`", "'")
    s = s.replace("-", " ")
    s = re.sub(r"\s*/\s*", "/", s)
    return " ".join(s.split())


def _claves(nombre: str) -> list[str]:
    """Claves de comparación: la forma completa y, si es bilingüe, cada mitad."""
    claves = [normaliza(nombre)]
    if "/" in nombre:
        for parte in nombre.split("/"):
            clave = normaliza(parte)
            if clave and clave not in claves:
                claves.append(clave)
    return claves


class Matcher:
    """Resuelve un nombre de municipio (con su ámbito) a su Municipio."""

    UMBRAL = 86    # similitud mínima (0-100) para aceptar un match difuso
    MARGEN = 5     # ventaja mínima del mejor candidato sobre el segundo

    def __init__(self, repo: MunicipioRepo, *, fuzzy: bool = True):
        self._repo = repo
        self._fuzzy = fuzzy and _HAY_FUZZY
        self._global: dict[str, list[Municipio]] = defaultdict(list)
        self._por_ccaa: dict[tuple[str, str], list[Municipio]] = defaultdict(list)
        self._por_prov: dict[tuple[str, str], list[Municipio]] = defaultdict(list)
        for m in repo:
            for clave in _claves(m.name):
                self._global[clave].append(m)
                self._por_ccaa[(m.ccaa_iso, clave)].append(m)
                self._por_prov[(m.province, clave)].append(m)
        self.no_resueltos: list[str] = []
        self.resueltos_fuzzy: list[tuple[str, str]] = []  # (nombre_fuente, ine)

    def match(self, nombre: str, *, provincia: str | None = None,
              ccaa: str | None = None) -> Municipio | None:
        """Devuelve el Municipio o None (y lo apunta en `no_resueltos`).

        El join exacto se ACOTA al ámbito dado (provincia o CCAA): si la fuente
        indica su CCAA, NUNCA se cae al índice global, que casaría un homónimo de
        otra comunidad. Caso real: «Cordovilla» (concejo de Navarra sin INE propio)
        casaba con Cordovilla (Salamanca). Un match correcto dentro de la misma CCAA
        ya lo encuentra `_por_ccaa`, así que descartar el global solo elimina los
        falsos positivos entre comunidades. Sin ámbito, sí se usa el global.
        """
        con_ambito = provincia is not None or ccaa is not None
        for clave in _claves(nombre):
            listas = [
                self._por_prov.get((provincia, clave)) if provincia else None,
                self._por_ccaa.get((ccaa, clave)) if ccaa else None,
            ]
            if not con_ambito:
                listas.append(self._global.get(clave))
            for cand in listas:
                if cand and len({c.ine for c in cand}) == 1:
                    return cand[0]
        if self._fuzzy:
            municipio = self._match_fuzzy(nombre, provincia, ccaa)
            if municipio is not None:
                self.resueltos_fuzzy.append((nombre, municipio.ine))
                return municipio
        self.no_resueltos.append(nombre)
        return None

    def _match_fuzzy(self, nombre: str, provincia: str | None,
                     ccaa: str | None) -> Municipio | None:
        """Match difuso conservador dentro del ámbito (provincia o, si no, CCAA)."""
        candidatos = (self._repo.por_provincia(provincia) if provincia
                      else self._repo.por_ccaa(ccaa) if ccaa else [])
        if not candidatos:
            return None
        clave = normaliza(nombre)
        mejor: Municipio | None = None
        alto = segundo = 0.0
        for municipio in candidatos:
            # `ratio` (cadena completa) + prefijo común ≥3: acepta erratas y
            # variantes ('Arenas Iguña'→'Arenas de Iguña') pero rechaza
            # sub-entidades ('Asín de Broto'→'Broto') y municipios distintos de
            # raíz parecida ('Alcoba'→'Arroba de los Montes').
            puntua = 0.0
            for k in _claves(municipio.name):
                if len(os.path.commonprefix([clave, k])) >= 3:
                    puntua = max(puntua, fuzz.ratio(clave, k))
            if puntua > alto:
                segundo, alto, mejor = alto, puntua, municipio
            elif puntua > segundo:
                segundo = puntua
        if mejor is not None and alto >= self.UMBRAL and (alto - segundo) >= self.MARGEN:
            return mejor
        return None
