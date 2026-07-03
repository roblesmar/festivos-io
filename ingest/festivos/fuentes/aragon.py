"""Fuente de fiestas locales de Aragón (Aragón Open Data).

El Gobierno de Aragón publica el calendario de festivos en su portal de datos
abiertos. El recurso `festivos_aragon_<anyo>_completo.csv` (delimitador `;`)
contiene EXCLUSIVAMENTE las fiestas LOCALES (municipales): cada municipio trae
sus dos festivos propios y no aparece ninguna fecha autonómica/nacional común a
toda la comunidad (la fecha más repetida del CSV 2026 sale en 74 de 567
municipios, nunca en todos). Por eso no hace falta restar el CSV `_ccaa`: basta
con tomar todas las filas del `completo`.

Columnas: `Provincia;CodigoINE;Municipio;Fecha;NombreFestivo`, con la fecha en
`DD-MM-AAAA`. El código INE municipal (5 dígitos) viene de forma NATIVA en la
mayoría de filas; algunas entidades sub-municipales (núcleos/pedanías/EMD) lo
traen vacío, en cuyo caso se deja `ine=None` y se acota el join por la provincia
(CPRO) deducida del nombre.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Nombre de provincia -> código INE de 2 dígitos (CPRO), para las filas sin INE.
_PROVINCIAS_INE: dict[str, str] = {
    "Huesca": "22",
    "Teruel": "44",
    "Zaragoza": "50",
}

# URL del recurso CSV `festivos_aragon_<anyo>_completo.csv` por año. El UUID del
# recurso es DISTINTO en cada año, así que NO se puede formar la URL cambiando
# solo el año del nombre del fichero: el portal sirve el blob por UUID e ignora
# el nombre, por lo que reutilizar el UUID de 2026 con el nombre de otro año
# devuelve los datos de 2026 con la fecha falseada. Por eso se mapea año->URL.
#
# Importante: el CSV `_completo` (esquema `Provincia;CodigoINE;Municipio;Fecha;
# NombreFestivo`, único que parsea esta fuente) SOLO se publica para 2026. Los
# datasets oficiales de 2024 y 2025 (`calendario-de-festivos-en-comunidad-de-
# aragon-<anyo>`) solo ofrecen XLS por provincia e ICS, sin el CSV con INE
# nativo, así que esos años no tienen fuente soportada y fallan limpio.
_URLS_POR_ANYO: dict[int, str] = {
    2026: (
        "https://opendata.aragon.es/datos/catalogo/dataset/"
        "f861c5f7-5424-4b3c-90bf-a6d2c2f5b0bd/recurso/"
        "5ff8c1f8-fb7e-4343-abba-eb7dbd796dbc/descarga/"
        "festivos_aragon_2026_completo.csv"
    ),
}


@registrar
class Aragon(FuenteLocal):
    """Fiestas locales de Aragón desde el CSV de festivos de Aragón Open Data."""
    ccaa_iso = "ES-AR"
    nombre = "Aragón"

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el CSV `completo` de festivos del año.

        Resuelve el recurso CORRECTO del año desde `_URLS_POR_ANYO` (cada año
        tiene su propio UUID). La caché se indexa por año. Para un año sin
        fuente conocida lanza `ValueError` en vez de reutilizar otro año.
        """
        url = _URLS_POR_ANYO.get(anyo)
        if url is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-AR_{anyo}.csv"
        if cache.exists():
            return cache.read_bytes()

        with urllib.request.urlopen(url) as resp:
            bruto = resp.read()

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el CSV en fiestas locales del año (delimitador `;`).

        Todas las filas del CSV son locales; se filtra por el año (sufijo de la
        fecha `DD-MM-AAAA`) por robustez ante un recurso con datos mezclados.
        """
        texto = bruto.decode("utf-8-sig")
        lector = csv.DictReader(io.StringIO(texto), delimiter=";")
        objetivo = str(anyo)

        for fila in lector:
            fecha = self._fecha_iso((fila.get("Fecha") or "").strip())
            if not fecha or not fecha.startswith(objetivo):
                continue  # parseo defensivo: fecha ausente o de otro año

            municipio = (fila.get("Municipio") or "").strip() or None

            ine_bruto = (fila.get("CodigoINE") or "").strip()
            if ine_bruto.isdigit():
                ine: str | None = ine_bruto.zfill(5)
                provincia: str | None = ine[:2]
            else:
                # Entidad sub-municipal sin INE propio: se acota por provincia.
                ine = None
                provincia = _PROVINCIAS_INE.get((fila.get("Provincia") or "").strip())

            if not ine and not municipio:
                continue  # sin INE ni nombre no es resoluble

            yield FiestaLocalCruda(
                fecha=fecha,
                municipio_nombre=municipio,
                ine=ine,
                provincia=provincia,
                denominacion=(fila.get("NombreFestivo") or "").strip() or None,
            )

    @staticmethod
    def _fecha_iso(fecha: str) -> str | None:
        """Convierte una fecha `DD-MM-AAAA` en ISO `YYYY-MM-DD`."""
        partes = fecha.split("-")
        if len(partes) != 3:
            return None
        dia, mes, anyo = partes
        if not (dia.isdigit() and mes.isdigit() and anyo.isdigit()):
            return None
        if len(anyo) != 4:
            return None
        return f"{anyo}-{mes.zfill(2)}-{dia.zfill(2)}"
