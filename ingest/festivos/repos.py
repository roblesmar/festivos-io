"""Repositorio de municipios: carga e índices, con el código INE como clave."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from . import ine
from .modelo import Municipio


class MunicipioRepo:
    """Colección de municipios indexada por INE, provincia y CCAA."""

    def __init__(self, municipios: list[Municipio]):
        self._por_ine: dict[str, Municipio] = {m.ine: m for m in municipios}
        if len(self._por_ine) != len(municipios):
            raise ValueError("códigos INE duplicados en el repositorio")
        self._por_provincia: dict[str, list[Municipio]] = defaultdict(list)
        self._por_ccaa: dict[str, list[Municipio]] = defaultdict(list)
        for m in municipios:
            self._por_provincia[m.province].append(m)
            self._por_ccaa[m.ccaa_iso].append(m)

    @classmethod
    def desde_ine(cls, xlsx_path) -> "MunicipioRepo":
        return cls(ine.leer_municipios(xlsx_path))

    @classmethod
    def desde_json(cls, path) -> "MunicipioRepo":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([Municipio(**m) for m in data["municipalities"]])

    def por_ine(self, codigo: str) -> Municipio | None:
        return self._por_ine.get(codigo)

    def por_provincia(self, cpro: str) -> list[Municipio]:
        return list(self._por_provincia.get(cpro, ()))

    def por_ccaa(self, iso: str) -> list[Municipio]:
        return list(self._por_ccaa.get(iso, ()))

    def __iter__(self):
        return iter(self._por_ine.values())

    def __len__(self) -> int:
        return len(self._por_ine)
