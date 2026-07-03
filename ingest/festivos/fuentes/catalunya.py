"""Fuente de fiestas locales de Cataluña (Generalitat de Catalunya).

La Generalitat publica las *festes locals* en el portal de datos abiertos
(Socrata/SODA), dataset `b4eh-r8up`. Cada registro incluye municipio, núcleo
(pedanía) y la fecha del festivo local del calendario laboral.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar


@registrar
class Catalunya(FuenteLocal):
    """Fiestas locales de Cataluña desde el dataset SODA de la Generalitat."""
    ccaa_iso = "ES-CT"
    nombre = "Cataluña"

    # Rango histórico publicado en el dataset SODA (any_calendari).
    # El propio SODA filtra por año, así que NO hay un documento fijo que
    # reutilizar: cada año resuelve su propio recurso. Fuera de este rango
    # (p. ej. 2027, aún sin publicar) se falla limpio en vez de devolver vacío.
    ANYO_MIN = 2010
    ANYO_MAX = 2026

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el JSON de festes locals del año.

        El dataset SODA `b4eh-r8up` se filtra por `any_calendari`, de modo que
        cada año resuelve su documento correcto y la caché es POR AÑO. Para años
        sin datos publicados se lanza ``ValueError`` y nunca se reutiliza ni se
        cachea el documento de otro año.
        """
        if not (self.ANYO_MIN <= anyo <= self.ANYO_MAX):
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-CT_{anyo}.json"
        if cache.exists():
            return cache.read_bytes()

        url = (
            "https://analisi.transparenciacatalunya.cat/resource/b4eh-r8up.json"
            f"?$where=any_calendari='{anyo}'&$limit=20000"
        )
        with urllib.request.urlopen(url) as resp:
            bruto = resp.read()

        # El SODA siempre responde 200 con `[]` si el año no existe: validamos
        # que hay registros antes de cachear, para no fijar un documento vacío.
        if not json.loads(bruto):
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el JSON en registros a nivel municipio (pedania == '000')."""
        for reg in json.loads(bruto):
            if reg.get("pedania") != "000":
                continue  # solo nivel municipio, no núcleos/pedanías

            data = reg.get("data")
            ine = reg.get("codi_municipi_ine")
            if not data or not ine:
                continue  # registro incompleto
            if reg.get("any_calendari") not in (None, str(anyo)):
                continue  # pertenece a otro año

            ine = str(ine).zfill(5)
            yield FiestaLocalCruda(
                fecha=data[:10],
                ine=ine,
                municipio_nombre=reg.get("ajuntament_o_nucli_municipal"),
                provincia=ine[:2],
                denominacion=reg.get("festiu") or None,
            )
