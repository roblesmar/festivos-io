"""Fuente de fiestas locales del Principado de Asturias.

El Principado publica el calendario de festivos en su portal de datos abiertos
(`descargas.asturias.es`) en un único documento con todos los ámbitos
(autonómico y local). Asturias es provincia única (CPRO 33) y el dataset no trae
código INE de municipio, así que nos quedamos con las filas `AMBITO == "LOCAL"`
del año y dejamos el INE sin resolver (lo hará después el Matcher por nombre de
concejo).

Elección de formato — IMPORTANTE: el portal ofrece el mismo dataset en JSON, CSV
y XML. NO son equivalentes:

* El **JSON** (`...festivos.json`) solo trae el año en curso (a fecha de esta
  implementación, únicamente 2026), de modo que pedir 2024/2025 contra el JSON
  devolvía 0 filas. Además trae la `FECHA` en formato estadounidense
  `MM/DD/YYYY`.
* El **CSV** (`...festivos.csv`) es la versión consolidada e histórica: trae
  TODOS los años publicados (2021–2026 a día de hoy), con la `FECHA` en formato
  europeo `DD/MM/YYYY`. Delimitador `§` (U+00A7) y codificación Latin-1.

Por eso esta fuente usa el CSV: es el único recurso accesible con histórico por
año. La caché es del documento completo (común a todos los años), pero antes de
servirlo se valida que el AÑO pedido tiene filas `LOCAL`; si no, se falla limpio
con `ValueError` en vez de devolver vacío o datos de otro año.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Asturias es uniprovincial: todos los concejos comparten el CPRO 33.
_CPRO_ASTURIAS = "33"

# El CSV del Principado usa la sección (§, U+00A7) como delimitador y se sirve
# en Latin-1 (no UTF-8).
_DELIMITADOR = "§"
_ENCODING = "latin-1"


@registrar
class Asturias(FuenteLocal):
    """Fiestas locales del Principado de Asturias desde su CSV de datos abiertos."""
    ccaa_iso = "ES-AS"
    nombre = "Principado de Asturias"

    # URL única del CSV consolidado (TODOS los años y ámbitos). No hay recursos
    # por año: es un único documento que el Principado actualiza in situ y que
    # arrastra el histórico, así que el filtrado por año se hace en `parsear`.
    URL = (
        "https://descargas.asturias.es/asturias/opendata/CulturayOcio/"
        "calendario/dataset_calendario_festivos.csv"
    )

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el CSV consolidado del calendario.

        El recurso es un único documento con TODOS los años publicados; la caché
        es única e independiente del año (es el mismo CSV para todos). El
        filtrado por año se hace en `parsear`.

        Para no devolver datos vacíos de forma silenciosa cuando se pide un año
        que el documento aún no publica (p. ej. 2027), se comprueba que el año
        solicitado tiene filas `LOCAL` y, si no, se lanza `ValueError`. Nunca se
        reutiliza ni se sirve el documento como si fuera de otro año.
        """
        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / "calendario_festivos_asturias.csv"
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

    @classmethod
    def _anyos_disponibles(cls, bruto: bytes) -> set[int]:
        """Años con al menos una fiesta `LOCAL` en el CSV del calendario."""
        anyos: set[int] = set()
        for fila in cls._filas(bruto):
            if (fila.get("AMBITO") or "").strip().upper() != "LOCAL":
                continue
            fecha = cls._fecha_iso((fila.get("FECHA") or "").strip())
            if fecha:
                anyos.add(int(fecha[:4]))
        return anyos

    @classmethod
    def _filas(cls, bruto: bytes) -> Iterable[dict]:
        """Itera el CSV como diccionarios (delimitador `§`, Latin-1)."""
        texto = bruto.decode(_ENCODING)
        return csv.DictReader(io.StringIO(texto), delimiter=_DELIMITADOR)

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el CSV en fiestas locales del año.

        Columnas: ``AMBITO § COMUNIDAD - MUNICIPIO § FECHA § FIESTA - LOCALIDAD``.
        La `FECHA` viene en `DD/MM/YYYY`. Sin INE de municipio.
        """
        for reg in self._filas(bruto):
            if (reg.get("AMBITO") or "").strip().upper() != "LOCAL":
                continue  # solo fiestas locales/municipales

            fecha = self._fecha_iso((reg.get("FECHA") or "").strip())
            municipio = (reg.get("COMUNIDAD - MUNICIPIO") or "").strip()
            if not fecha or not municipio:
                continue  # parseo defensivo: fila incompleta o sin fecha válida
            if int(fecha[:4]) != anyo:
                continue  # el CSV arrastra otros años; solo el pedido

            denominacion = (reg.get("FIESTA - LOCALIDAD") or "").strip() or None

            yield FiestaLocalCruda(
                fecha=fecha,
                municipio_nombre=municipio,
                ine=None,  # la fuente no trae INE; lo resuelve el Matcher por nombre
                provincia=_CPRO_ASTURIAS,
                denominacion=denominacion,
            )

    @staticmethod
    def _fecha_iso(fecha: str) -> str | None:
        """Convierte `DD/MM/YYYY` a ISO `YYYY-MM-DD`.

        Devuelve ``None`` cuando el formato no es el esperado (filas incompletas
        o con cabeceras arrastradas), para que el parseo sea defensivo.
        """
        partes = fecha.split("/")
        if len(partes) != 3:
            return None
        dia, mes, anyo_str = partes
        if not (dia.isdigit() and mes.isdigit() and anyo_str.isdigit()):
            return None
        if len(anyo_str) != 4:
            return None
        if not (1 <= int(mes) <= 12 and 1 <= int(dia) <= 31):
            return None
        return f"{anyo_str}-{mes.zfill(2)}-{dia.zfill(2)}"
