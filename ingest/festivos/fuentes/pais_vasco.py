"""Fuente de fiestas locales del País Vasco (Gobierno Vasco / Eusko Jaurlaritza).

El portal de datos abiertos de Euskadi publica el calendario laboral en un único
CSV (delimitador `;`) con todos los ámbitos: comunes de la CAE (`territory`
== "Todos/denak"), territoriales de cada territorio histórico (Araba, Bizkaia,
Gipuzkoa) y las fiestas locales de cada municipio. Aquí nos quedamos solo con
las LOCALES/municipales del año.

Aviso: el campo `municipalitycode` es el índice de EUSTAT, NO el código INE, así
que no se usa como `ine`; el join nombre→INE se resuelve después con el Matcher.
"""
from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar


@registrar
class PaisVasco(FuenteLocal):
    """Fiestas locales del País Vasco desde el CSV de datos abiertos de Euskadi."""
    ccaa_iso = "ES-PV"
    nombre = "País Vasco"

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el CSV del calendario laboral del año.

        Euskadi publica un CSV por año cuya URL incluye el propio año, así que
        cada año se resuelve a su documento CORRECTO (nunca se reutiliza el de
        otro año). La caché está particionada por año. Si el portal no publica
        ese año (404), se falla limpio con `ValueError` en vez de devolver datos
        de otro año.
        """
        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-PV_{anyo}.csv"
        if cache.exists():
            return cache.read_bytes()

        url = (
            "https://opendata.euskadi.eus/contenidos/ds_eventos/"
            f"calendario_laboral_{anyo}/opendata/calendario_laboral_{anyo}.csv"
        )
        try:
            with urllib.request.urlopen(url) as resp:
                bruto = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ValueError(
                    f"sin fuente de {self.ccaa_iso} para {anyo}"
                ) from exc
            raise

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el CSV en fiestas locales del año (delimitador `;`).

        Columnas: date;descripcionEs;descriptionEu;municipalityEs;MunicipalityEu;
        territory;municipalitycode;latwgs84;lonwgs84
        """
        texto = bruto.decode("utf-8-sig")
        lector = csv.DictReader(io.StringIO(texto), delimiter=";")

        for fila in lector:
            territorio = (fila.get("territory") or "").strip()
            municipio = (fila.get("municipalityEs") or "").strip()

            # Descartar las fiestas comunes de la CAE (no son locales).
            if territorio == "Todos/denak" or municipio == "CAE":
                continue
            # Descartar las territoriales (la fila usa el territorio como
            # municipio, p. ej. "Bizkaia" / "Álava - Araba"): no son locales.
            if not municipio or municipio == territorio:
                continue

            fecha = self._fecha_iso((fila.get("date") or "").strip(), anyo)
            if not fecha:
                continue  # parseo defensivo: fecha ausente o de otro año

            denominacion = (fila.get("descripcionEs") or "").strip() or None

            yield FiestaLocalCruda(
                fecha=fecha,
                municipio_nombre=municipio,
                ine=None,          # municipalitycode es EUSTAT, no INE
                provincia=None,    # no fiable; el join usará scope CCAA
                denominacion=denominacion,
            )

    @staticmethod
    def _fecha_iso(fecha: str, anyo: int) -> str | None:
        """Convierte la fecha del CSV a ISO `YYYY-MM-DD` (solo del año pedido).

        El portal usa dos formatos según el año: `DD/MM/YYYY` (p. ej. 2026) y
        `YYYY/M/D` con día/mes sin ceros (p. ej. 2024 y 2025). Se detecta cuál
        es el año por su longitud (4 dígitos) y se valida que coincide con el
        año pedido; cualquier otra cosa se descarta.
        """
        partes = [p.strip() for p in fecha.split("/")]
        if len(partes) != 3 or not all(p.isdigit() for p in partes):
            return None

        if len(partes[0]) == 4:        # YYYY/M/D
            ann, mes, dia = partes
        elif len(partes[2]) == 4:      # DD/MM/YYYY
            dia, mes, ann = partes
        else:
            return None

        if ann != str(anyo):
            return None  # pertenece a otro año
        return f"{ann}-{mes.zfill(2)}-{dia.zfill(2)}"
