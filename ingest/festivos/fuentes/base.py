"""Interfaz común de las fuentes de fiestas locales (una por CCAA).

Cada comunidad publica sus fiestas locales en un formato distinto (CSV/JSON/HTML/PDF).
Una subclase de `FuenteLocal` encapsula esa heterogeneidad y devuelve siempre
`FiestaLocalCruda`, que el pipeline normaliza (join nombre→INE) y ensambla.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class FiestaLocalCruda:
    """Registro de fiesta local sin normalizar, tal como sale de la fuente."""
    fecha: str                       # ISO YYYY-MM-DD
    municipio_nombre: str | None = None
    ine: str | None = None           # si la fuente ya lo trae (5 dígitos)
    provincia: str | None = None     # CPRO, para acotar el join nombre→INE
    denominacion: str | None = None  # nombre de la festividad, si se conoce


class FuenteLocal(ABC):
    """Fuente oficial de fiestas locales de una comunidad autónoma."""
    ccaa_iso: str = ""
    nombre: str = ""

    @abstractmethod
    def descargar(self, anyo: int) -> bytes:
        """Descarga el recurso bruto del año (cacheable)."""

    @abstractmethod
    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el bruto en registros `FiestaLocalCruda`."""


REGISTRO: dict[str, type[FuenteLocal]] = {}


def registrar(cls: type[FuenteLocal]) -> type[FuenteLocal]:
    """Decorador que registra una fuente por su código ISO de CCAA."""
    if not cls.ccaa_iso:
        raise ValueError(f"{cls.__name__} no define ccaa_iso")
    REGISTRO[cls.ccaa_iso] = cls
    return cls
