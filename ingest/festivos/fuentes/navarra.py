"""Fuente de fiestas locales de la Comunidad Foral de Navarra (Gobierno de Navarra).

El Gobierno de Navarra publica las fiestas locales en su portal de datos abiertos
(CKAN), como un volcado CSV con BOM (de ahí el `utf-8-sig`). Sigue el modelo
navarro de **una única** fiesta local por localidad. Columnas:
`_id,LOCALIDAD,DIA,MES,NOTAS`, con el mes en texto español. (La columna de notas
viene como `NOTAS` desde 2025 y como `Notas` en 2024; se admiten ambas.)

El dataset CKAN `Calendario de días festivos de la Comunidad Foral de Navarra`
tiene un **recurso (resource_id) distinto por año**, no un único volcado
acumulativo. Por eso `descargar` resuelve el recurso del año pedido a través de
``_RESOURCES`` y la caché es POR AÑO: reutilizar el documento de 2026 para otro
año produciría fechas FALSAS (cada año tiene sus propias fiestas locales).

Las localidades con fiesta móvil traen `DIA = '*'` y la regla en `NOTAS`
(p.ej. "Lunes siguiente al primer domingo de mayo"); no se calcula su fecha
para no inventar el día, así que se descartan en el parseo defensivo.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Mes en texto español -> número de mes.
_MESES: dict[str, int] = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

# Días por mes (año no bisiesto vale para validar el rango; 2026 no lo es).
_DIAS_MES: dict[int, int] = {
    1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
}


@registrar
class Navarra(FuenteLocal):
    """Fiestas locales de Navarra desde el volcado CSV de datos abiertos (CKAN)."""
    ccaa_iso = "ES-NC"
    nombre = "Comunidad Foral de Navarra"

    # Un resource_id (CKAN) distinto por año del dataset CKAN
    # `Calendario de días festivos de la Comunidad Foral de Navarra`
    # (package 0cf3088d-a191-45b4-979a-aa6ec709786a). NO es un volcado
    # acumulativo: cada año tiene su propio recurso, así que se mapea por año
    # y NUNCA se reutiliza el documento de otro año.
    _RESOURCES: dict[int, str] = {
        2024: "7ebfe051-12a8-4e61-bc51-9148e2b965b1",
        2025: "dfdbef41-9e8b-4951-a4f0-15ef16cd886f",
        2026: "f48e36ae-a700-4796-ab37-9ec0a353cfa1",
    }

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el volcado CSV de fiestas locales del año.

        Resuelve el recurso CKAN propio del año a través de ``_RESOURCES``; la
        caché es POR AÑO. Para años sin fuente conocida se lanza ``ValueError``
        en lugar de reutilizar el documento de otro año (que daría fechas
        falsas, ya que cada año tiene sus propias fiestas locales).
        """
        resource_id = self._RESOURCES.get(anyo)
        if resource_id is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-NC_{anyo}.csv"
        if cache.exists():
            return cache.read_bytes()

        url = (
            "https://datosabiertos.navarra.es/es/datastore/dump/"
            f"{resource_id}?format=csv&bom=True"
        )
        with urllib.request.urlopen(url) as resp:
            bruto = resp.read()

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el CSV en fiestas locales del año (una por localidad).

        Columnas: `_id,LOCALIDAD,DIA,MES,NOTAS`. El CSV trae BOM, por eso se
        decodifica con `utf-8-sig`. La columna de notas viene como `NOTAS`
        (2025/2026) o `Notas` (2024); se admiten ambas. Las fiestas móviles
        (`DIA = '*'`) se omiten: su día depende de las notas y no se calcula
        para no inventarlo.
        """
        texto = bruto.decode("utf-8-sig")
        lector = csv.DictReader(io.StringIO(texto))

        for fila in lector:
            municipio = (fila.get("LOCALIDAD") or "").strip()
            dia = (fila.get("DIA") or "").strip()
            mes_txt = (fila.get("MES") or "").strip().lower()
            if not municipio or not dia.isdigit():
                continue  # parseo defensivo: sin localidad o fiesta móvil

            mes = _MESES.get(mes_txt)
            if mes is None:
                continue  # mes no reconocido

            dia_num = int(dia)
            if not 1 <= dia_num <= _DIAS_MES[mes]:
                continue  # día fuera de rango

            fecha = f"{anyo:04d}-{mes:02d}-{dia_num:02d}"
            notas = fila.get("NOTAS")
            if notas is None:
                notas = fila.get("Notas")  # cabecera de 2024
            denominacion = (notas or "").strip()
            if denominacion in ("", "*"):
                denominacion = None

            yield FiestaLocalCruda(
                fecha=fecha,
                municipio_nombre=municipio,
                ine=None,  # se resuelve después con el Matcher (nombre -> INE)
                provincia="31",  # CPRO de Navarra, acota el join nombre->INE
                denominacion=denominacion,
            )
