"""Modelos de dominio de festivos."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Nivel(str, Enum):
    """Ámbito de un festivo."""
    NACIONAL = "national"
    AUTONOMICO = "regional"
    LOCAL = "local"


class Tipo(str, Enum):
    """Tipo de festivo según cómo se fija la fecha."""
    FIJO = "fixed"            # fecha fija
    MOVIL = "movable"         # depende de la Pascua
    SUSTITUTORIO = "substitute"  # nacional sustituible o sustituido por la CCAA


@dataclass(frozen=True, slots=True)
class Fuente:
    """Origen oficial de un festivo (referencia legal + URL)."""
    ref: str
    url: str | None = None

    def to_dict(self) -> dict:
        d = {"ref": self.ref}
        if self.url:
            d["url"] = self.url
        return d


@dataclass(frozen=True, slots=True)
class Municipio:
    """Municipio español identificado por su código INE de 5 dígitos."""
    ine: str
    name: str
    province: str
    province_name: str
    ccaa_ine: str
    ccaa_iso: str
    ccaa_name: str
    dc: int | None = None

    def to_dict(self) -> dict:
        return {
            "ine": self.ine,
            "dc": self.dc,
            "name": self.name,
            "province": self.province,
            "province_name": self.province_name,
            "ccaa_ine": self.ccaa_ine,
            "ccaa_iso": self.ccaa_iso,
            "ccaa_name": self.ccaa_name,
        }


@dataclass(slots=True)
class Festivo:
    """Un festivo de un territorio en una fecha concreta."""
    date: str            # ISO-8601 YYYY-MM-DD
    name: dict[str, str]  # i18n por idioma (BCP 47)
    level: Nivel
    type: Tipo
    source: Fuente
    substitutable: bool | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "date": self.date,
            "name": self.name,
            "level": self.level.value,
            "type": self.type.value,
            "source": self.source.to_dict(),
        }
        if self.substitutable is not None:
            d["substitutable"] = self.substitutable
        if self.notes:
            d["notes"] = self.notes
        return d
