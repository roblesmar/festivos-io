"""Fuente de fiestas locales de Ceuta (Ciudad Autónoma de Ceuta).

Ceuta es una ciudad autónoma con un único municipio (INE 51001), por lo que sus
fiestas locales se publican directamente en el Boletín Oficial de la Ciudad de
Ceuta (BOCCE) como fechas concretas, sin un dataset estructurado descargable.
Por eso `descargar` no accede a la red: resuelve, A PARTIR DEL AÑO PEDIDO, las
DOS fiestas locales documentadas en el propio módulo (fin del Ramadán / Eidul
Fitr y San Antonio) y las serializa para que `parsear` las consuma.

Cada año tiene SU propia entrada en `_FIESTAS_LOCALES` (la fecha del Eidul Fitr
es móvil y San Antonio es fija el 13 de junio). Para un año sin fuente conocida
se lanza ``ValueError`` y NUNCA se reutiliza el documento/las fechas de otro año.
"""
from __future__ import annotations

import json
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Código INE del municipio único de Ceuta (CPRO 51, CMUN 001).
_INE_CEUTA = "51001"

# Fiestas LOCALES de Ceuta por año (fuente: BOCCE / Resolución de la Delegación
# del Gobierno en Ceuta que publica la relación de fiestas locales).
# Son dos por año: el fin del Ramadán (Eidul Fitr, fecha móvil) y San Antonio
# (13 de junio, fija). Mapeo año -> lista de (fecha ISO, denominación).
#  - 2024: BOCCE Extraordinario nº67, 20/10/2023 (Decreto 15/09/2023).
#  - 2025: BOCCE 25/10/2024 (Decreto 19/09/2024).
#  - 2026: BOCCE, calendario laboral 2026.
_FIESTAS_LOCALES: dict[int, list[tuple[str, str | None]]] = {
    2024: [
        ("2024-04-10", "Eidul Fitr (Fiesta de Culminación del Ramadán)"),
        ("2024-06-13", "San Antonio"),
    ],
    2025: [
        ("2025-03-31", "Eidul Fitr (Fiesta de Culminación del Ramadán)"),
        ("2025-06-13", "San Antonio"),
    ],
    2026: [
        ("2026-03-20", "Eidul Fitr (Fiesta de Culminación del Ramadán)"),
        ("2026-06-13", "San Antonio"),
    ],
}


@registrar
class Ceuta(FuenteLocal):
    """Fiestas locales de Ceuta (municipio único, fechas del BOCCE por año)."""
    ccaa_iso = "ES-CE"
    nombre = "Ceuta"

    def descargar(self, anyo: int) -> bytes:
        """Resuelve las DOS fiestas locales del año pedido (sin red).

        No hay recurso remoto: las fechas viven como constantes del módulo, una
        entrada POR AÑO. Se serializa SOLO la entrada del año solicitado, de modo
        que nunca se devuelven las fechas de otro año. Para un año sin fuente
        conocida se lanza ``ValueError`` en vez de reutilizar otro documento.
        """
        fiestas = _FIESTAS_LOCALES.get(anyo)
        if not fiestas:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")
        return json.dumps(fiestas).encode("utf-8")

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Devuelve las fiestas locales del municipio único de Ceuta."""
        for fecha, denominacion in json.loads(bruto):
            if not fecha.startswith(f"{anyo}-"):
                continue  # defensivo: no mezclar fechas de otro año
            yield FiestaLocalCruda(
                fecha=fecha,
                municipio_nombre="Ceuta",
                ine=_INE_CEUTA.zfill(5),
                provincia=_INE_CEUTA[:2],
                denominacion=denominacion,
            )
