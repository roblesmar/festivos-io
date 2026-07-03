"""Fuente de fiestas locales de Castilla y León (Junta de Castilla y León).

La Junta publica el calendario de fiestas de carácter local en su portal de
datos abiertos (Opendatasoft). El mismo dataset contiene varios años; se
descarga vía la Explore API v2.1 un CSV (delimitador `;`) filtrando el año
por rango de `fecha_fiesta`. Cada registro ya trae el código INE de municipio
(5 dígitos) y la fecha en ISO.

La URL ya incluye el año (en el filtro `where`), así que no hay un documento
"fijo": cada año resuelve su propio recurso. Solo se aceptan los años que la
JCyL tiene publicados (`_ANYOS_PUBLICADOS`); para el resto se lanza
`ValueError` en vez de reutilizar el documento de otro año.
"""
from __future__ import annotations

import csv
import io
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar


@registrar
class CastillaLeon(FuenteLocal):
    """Fiestas locales de Castilla y León desde el CSV de datos abiertos JCyL."""
    ccaa_iso = "ES-CL"
    nombre = "Castilla y León"

    # Años con datos publicados en el dataset Opendatasoft de la JCyL.
    # Verificado por descarga real: 2024/2025/2026 devuelven registros
    # distintos y plausibles (~5000-5600 fiestas locales, ~2248 municipios).
    # 2027 aún no está publicado (la API responde solo cabecera, 0 filas).
    _ANYOS_PUBLICADOS = frozenset({2024, 2025, 2026})

    def _url(self, anyo: int) -> str:
        """URL de exportación CSV del año (el año va embebido en el filtro)."""
        where = (
            f"fecha_fiesta>='{anyo}-01-01' and fecha_fiesta<='{anyo}-12-31'"
        )
        return (
            "https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/"
            "datasets/fiestas-locales-calendario-de-fiestas-de-caracter-local/"
            "exports/csv?" + urllib.parse.urlencode({"where": where})
        )

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el CSV de fiestas locales del año.

        La caché se indexa por año (`local_ES-CL_{anyo}.csv`), de modo que un
        año nunca puede servir el documento de otro. Para años sin fuente
        conocida se lanza `ValueError` sin tocar la red ni la caché.
        """
        if anyo not in self._ANYOS_PUBLICADOS:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-CL_{anyo}.csv"
        if cache.exists():
            return cache.read_bytes()

        url = self._url(anyo)
        with urllib.request.urlopen(url) as resp:
            bruto = resp.read()

        # Salvaguarda: el dataset es multi-año, pero si por cualquier motivo la
        # respuesta no trae ninguna fila del año pedido, no cacheamos un CSV
        # vacío/erróneo: fallamos limpio en vez de producir datos falsos.
        if not self._tiene_filas_del_anyo(bruto, anyo):
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    @staticmethod
    def _tiene_filas_del_anyo(bruto: bytes, anyo: int) -> bool:
        """True si el CSV trae al menos una fila con `fecha_fiesta` del año."""
        texto = bruto.decode("utf-8-sig")
        lector = csv.DictReader(io.StringIO(texto), delimiter=";")
        objetivo = str(anyo)
        for fila in lector:
            if (fila.get("fecha_fiesta") or "").strip().startswith(objetivo):
                return True
        return False

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el CSV en fiestas locales del año (delimitador `;`).

        Columnas: provincia;municipio;fecha_fiesta;nombre_fiesta;ine
        """
        texto = bruto.decode("utf-8-sig")
        lector = csv.DictReader(io.StringIO(texto), delimiter=";")
        objetivo = str(anyo)

        for fila in lector:
            fecha = (fila.get("fecha_fiesta") or "").strip()[:10]
            if not fecha.startswith(objetivo):
                continue  # parseo defensivo: pertenece a otro año
            if len(fecha) != 10 or fecha[4] != "-" or fecha[7] != "-":
                continue  # fecha mal formada

            ine = (fila.get("ine") or "").strip()
            ine = ine.zfill(5) if ine else None
            municipio = (fila.get("municipio") or "").strip() or None
            if not ine and not municipio:
                continue  # sin INE ni nombre no se puede casar el municipio

            yield FiestaLocalCruda(
                fecha=fecha,
                municipio_nombre=municipio,
                ine=ine,
                provincia=ine[:2] if ine else None,
                denominacion=(fila.get("nombre_fiesta") or "").strip() or None,
            )
