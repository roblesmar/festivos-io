"""Fuente de fiestas locales de la Comunidad de Madrid.

La Comunidad de Madrid publica las fiestas locales en su portal de datos
abiertos (CKAN, dataset `festivos_regionales_locales`) como CSV con
delimitador `;`. Cada año vive en un recurso DISTINTO:

* el **año en curso** (2026) está en el dataset «año en curso»
  (`festivos_regionales_locales`), recurso `festivos_locales.csv`, que el
  portal sobrescribe cada año con el año vigente;
* los **años pasados** (2024, 2025, …) están en el dataset «histórico»
  (`festivos_regionales_locales_historico`), recurso
  `festivos_locales_historicos.csv`, que acumula 1998…año anterior.

Por eso resolvemos el recurso correcto de CADA año con un mapa por año; para
un año sin recurso conocido se lanza `ValueError` en vez de reutilizar otro
año (lo que produciría datos falsos). El histórico viene en latin-1 y con el
`entidad_codigo` sin rellenar (`0`,`1`,…), mientras que el año en curso usa
`00`,`01`,…; el parseo normaliza ambos. El código INE del municipio no
aparece literal: se reconstruye como `28` (CPRO de Madrid) + `municipio_codigo`
a 3 dígitos. La codificación se prueba utf-8 y, si falla, latin-1.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Provincia única de la Comunidad de Madrid (CPRO de 2 dígitos).
_CPRO_MADRID = "28"

# Recurso CKAN del año EN CURSO (se sobrescribe cada año con el año vigente).
_URL_ANYO_EN_CURSO = (
    "https://datos.comunidad.madrid/dataset/"
    "f160eb6c-6715-471e-9bc0-38497aae950f/resource/"
    "ba59e7e8-3d8d-4221-a5fa-b5e78b82707f/download/festivos_locales.csv"
)
# Recurso CKAN HISTÓRICO (1998…año anterior); el filtrado por año va en `parsear`.
_URL_HISTORICO = (
    "https://datos.comunidad.madrid/dataset/"
    "02c712b5-5009-4ffb-b388-3cfb4fca207d/resource/"
    "22d7957e-8b3a-4f00-9549-bf501f4ea741/download/festivos_locales_historicos.csv"
)

# Mapa de año -> URL del recurso que CONTIENE ese año. Nunca se reutiliza el
# documento de un año para otro: un año ausente aquí provoca ValueError.
_URLS_POR_ANYO: dict[int, str] = {
    2024: _URL_HISTORICO,
    2025: _URL_HISTORICO,
    2026: _URL_ANYO_EN_CURSO,
}


@registrar
class Madrid(FuenteLocal):
    """Fiestas locales de la Comunidad de Madrid desde el CSV de CKAN."""
    ccaa_iso = "ES-MD"
    nombre = "Comunidad de Madrid"

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el CSV de fiestas locales del año.

        Resuelve el recurso CKAN que realmente contiene `anyo`: el dataset del
        año en curso o el histórico. Si no hay recurso conocido para ese año,
        falla en vez de devolver datos de otro año.
        """
        url = _URLS_POR_ANYO.get(anyo)
        if url is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        # Caché POR AÑO: la clave incluye el año, así dos años que comparten
        # recurso (p. ej. 2024 y 2025 en el histórico) no se pisan entre sí.
        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-MD_{anyo}.csv"
        if cache.exists():
            return cache.read_bytes()

        with urllib.request.urlopen(url) as resp:
            bruto = resp.read()

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el CSV en fiestas locales municipales del año.

        Columnas: año;municipio_codigo;municipio_nombre;entidad_codigo;
        entidad_nombre;fecha_festivo. La fecha ya viene en ISO `YYYY-MM-DD`.
        El INE se construye como `28` + `municipio_codigo` (3 dígitos).
        """
        texto = self._decodificar(bruto)
        lector = csv.DictReader(io.StringIO(texto), delimiter=";")
        objetivo = str(anyo)

        for fila in lector:
            # El primer campo ("año") puede arrastrar BOM en la cabecera.
            anyo_fila = (fila.get("año") or fila.get("﻿año") or "").strip()
            if anyo_fila and anyo_fila != objetivo:
                continue  # pertenece a otro año

            # Solo nivel municipio (entidad 0); descartamos núcleos/pedanías
            # para que cada registro mapee a un único INE municipal. El año en
            # curso rellena el código (`00`) y el histórico no (`0`); por eso
            # comparamos el valor numérico en vez de la cadena literal.
            entidad = (fila.get("entidad_codigo") or "").strip()
            if entidad and entidad.lstrip("0"):
                continue

            codigo = (fila.get("municipio_codigo") or "").strip()
            fecha = (fila.get("fecha_festivo") or "").strip()
            municipio = (fila.get("municipio_nombre") or "").strip()
            if not codigo or not self._es_iso(fecha):
                continue  # parseo defensivo: fila incompleta o fecha inválida

            ine = (_CPRO_MADRID + codigo.zfill(3))[:5]
            yield FiestaLocalCruda(
                fecha=fecha,
                municipio_nombre=municipio or None,
                ine=ine,
                provincia=_CPRO_MADRID,
                denominacion=None,
            )

    @staticmethod
    def _decodificar(bruto: bytes) -> str:
        """Decodifica el CSV probando utf-8 y, si falla, latin-1."""
        try:
            return bruto.decode("utf-8-sig")
        except UnicodeDecodeError:
            return bruto.decode("latin-1")

    @staticmethod
    def _es_iso(fecha: str) -> bool:
        """Comprueba que la fecha tiene forma ISO `YYYY-MM-DD`."""
        return (
            len(fecha) == 10
            and fecha[4] == "-"
            and fecha[7] == "-"
            and fecha[:4].isdigit()
        )
