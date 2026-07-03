"""Fuente de fiestas locales de Andalucía (Junta de Andalucía).

La Junta publica el calendario laboral completo en su portal de datos abiertos
(`work-calendar`) en un único CSV con TODOS los años y todos los ámbitos
(nacional, autonómico y local). El delimitador es `|`, no la coma. Aquí nos
quedamos con las filas `type == "LOCAL"` del año solicitado.
"""
from __future__ import annotations

import csv
import io
import unicodedata
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Nombre de provincia (normalizado) -> código INE de 2 dígitos (CPRO).
_PROVINCIAS_INE: dict[str, str] = {
    "almeria": "04",
    "cadiz": "11",
    "cordoba": "14",
    "granada": "18",
    "huelva": "21",
    "jaen": "23",
    "malaga": "29",
    "sevilla": "41",
}


def _normalizar(texto: str) -> str:
    """Pasa a minúsculas y elimina tildes para casar nombres de provincia."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_tildes.strip().lower()


@registrar
class Andalucia(FuenteLocal):
    """Fiestas locales de Andalucía desde el CSV de datos abiertos de la Junta."""
    ccaa_iso = "ES-AN"
    nombre = "Andalucía"

    # URL única del calendario laboral completo (TODOS los años y ámbitos).
    URL = "https://datos.juntadeandalucia.es/api/v0/work-calendar/all?format=csv"

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el CSV completo del calendario laboral.

        El recurso de la Junta es un único documento que trae TODOS los años, de
        modo que la caché es única e independiente del año (no se reutiliza el
        documento de otro año: es el mismo para todos). El filtrado por año se
        hace en `parsear`.

        Para no devolver datos vacíos de forma silenciosa cuando se pide un año
        que el documento aún no publica, se comprueba que el año solicitado tiene
        filas `LOCAL` y, si no, se lanza `ValueError`.
        """
        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / "work-calendar_andalucia.csv"
        if cache.exists():
            bruto = cache.read_bytes()
        else:
            with urllib.request.urlopen(self.URL) as resp:
                bruto = resp.read()
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(bruto)

        if anyo not in self._anyos_disponibles(bruto):
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")
        return bruto

    @staticmethod
    def _anyos_disponibles(bruto: bytes) -> set[int]:
        """Años con al menos una fiesta `LOCAL` en el CSV del calendario."""
        texto = bruto.decode("utf-8-sig")
        lector = csv.DictReader(io.StringIO(texto), delimiter="|")
        anyos: set[int] = set()
        for fila in lector:
            if (fila.get("type") or "").strip() != "LOCAL":
                continue
            valor = (fila.get("year") or "").strip()
            if valor.isdigit():
                anyos.add(int(valor))
        return anyos

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el CSV en fiestas locales del año (delimitador `|`).

        Columnas: date|dateformat|description|event|id|municipality|province|type|year
        """
        texto = bruto.decode("utf-8-sig")
        lector = csv.DictReader(io.StringIO(texto), delimiter="|")
        objetivo = str(anyo)

        for fila in lector:
            if (fila.get("type") or "").strip() != "LOCAL":
                continue
            if (fila.get("year") or "").strip() != objetivo:
                continue

            municipio = (fila.get("municipality") or "").strip()
            fecha = self._fecha_iso(
                (fila.get("dateformat") or "").strip(),
                (fila.get("date") or "").strip(),
            )
            if not fecha or not municipio:
                continue  # parseo defensivo: fila incompleta

            provincia_nombre = (fila.get("province") or "").strip()
            provincia = _PROVINCIAS_INE.get(_normalizar(provincia_nombre))

            denominacion = (
                (fila.get("description") or "").strip()
                or (fila.get("event") or "").strip()
                or None
            )

            yield FiestaLocalCruda(
                fecha=fecha,
                municipio_nombre=municipio,
                ine=None,  # se resuelve después con el Matcher (nombre -> INE)
                provincia=provincia,
                denominacion=denominacion,
            )

    @staticmethod
    def _fecha_iso(dateformat: str, date: str) -> str | None:
        """Devuelve la fecha en ISO `YYYY-MM-DD`.

        Usa `dateformat` si ya viene en ISO; si no, convierte `date` (`YYYYMMDD`).
        """
        if len(dateformat) == 10 and dateformat[4] == "-" and dateformat[7] == "-":
            return dateformat
        if len(date) == 8 and date.isdigit():
            return f"{date[:4]}-{date[4:6]}-{date[6:]}"
        return None
