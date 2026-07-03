"""Fuente de fiestas locales de Melilla (Ciudad Autónoma de Melilla).

Melilla es un municipio único (INE `52001`), así que no hay calendario que
descargar: las dos fiestas locales se publican en el BOME y se mantienen aquí
de forma fija. `descargar` no toca la red (devuelve `b''`) y `parsear` emite
directamente los dos registros del año.

Las fechas varían CADA año (la primera fiesta local es a menudo una festividad
islámica de fecha móvil), por lo que cada año tiene su propia entrada en
`_FIESTAS_LOCALES` y NUNCA se reutiliza el documento/fechas de otro año. Para un
año sin fuente conocida, `descargar` lanza `ValueError` en lugar de devolver un
marcador vacío que produciría silenciosamente cero registros.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Municipio único de la Ciudad Autónoma de Melilla.
_INE_MELILLA = "52001"
_NOMBRE_MELILLA = "Melilla"

# Fiestas locales por año (fuente: calendario laboral del BOME, melilla.es).
# Solo ámbito municipal/local; las 2 fechas son DISTINTAS cada año.
#   2024: 10/04 (Eid El Fitr) y 17/09 (Día de Melilla).
#   2025: 08/09 (Ntra. Sra. Virgen de la Victoria) y 17/09 (Día de Melilla).
#   2026: 08/09 y 17/09.
_FIESTAS_LOCALES: dict[int, tuple[str, ...]] = {
    2024: ("2024-04-10", "2024-09-17"),
    2025: ("2025-09-08", "2025-09-17"),
    2026: ("2026-09-08", "2026-09-17"),
}


@registrar
class Melilla(FuenteLocal):
    """Fiestas locales de Melilla (municipio único, fechas fijas del BOME)."""
    ccaa_iso = "ES-ML"
    nombre = "Melilla"

    def descargar(self, anyo: int) -> bytes:
        """No hay recurso remoto: cachea/lee un marcador vacío y devuelve `b''`.

        Se conserva el patrón de caché POR AÑO (`<raiz>/.cache/local_ES-ML_{anyo}.txt`)
        por coherencia con el resto de fuentes, pero nunca toca la red. Para un
        año sin fechas conocidas en `_FIESTAS_LOCALES` se lanza `ValueError` en
        vez de fijar un marcador vacío: así no se reutilizan datos de otro año ni
        se devuelven cero registros de forma silenciosa.
        """
        if anyo not in _FIESTAS_LOCALES:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-ML_{anyo}.txt"
        if cache.exists():
            return cache.read_bytes()

        bruto = b""
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Emite las fiestas locales fijas del año para el municipio de Melilla."""
        for fecha in _FIESTAS_LOCALES.get(anyo, ()):
            if len(fecha) != 10 or fecha[4] != "-" or fecha[7] != "-":
                continue  # parseo defensivo: solo ISO YYYY-MM-DD
            yield FiestaLocalCruda(
                fecha=fecha,
                municipio_nombre=_NOMBRE_MELILLA,
                ine=_INE_MELILLA.zfill(5),
                provincia=_INE_MELILLA[:2],
                denominacion=None,
            )
