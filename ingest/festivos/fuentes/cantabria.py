"""Fuente de fiestas locales de Cantabria (Gobierno de Cantabria).

El calendario laboral se publica en el Boletín Oficial de Cantabria (BOC) como
un PDF. El anexo «FIESTAS LOCALES» es una tabla
`AYUNTAMIENTO | FESTIVIDAD | DÍA | MES` con dos filas (dos festivos) por
municipio. El nombre del ayuntamiento aparece centrado verticalmente entre sus
dos festividades, por lo que se asocia cada festividad a su municipio por
proximidad. La fuente no trae código INE, así que se deja `ine=None` y se rellena
`municipio_nombre`; la provincia es siempre Cantabria (CPRO 39).

Requiere una herramienta de extracción de texto de PDF (`pdftotext -layout` o,
en su defecto, `pdfplumber`). Si no hay ninguna disponible, `parsear` no
devuelve registros (estado parcial).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Mes en texto (mayúsculas, sin tildes) -> número de mes.
_MESES: dict[str, str] = {
    "ENERO": "01",
    "FEBRERO": "02",
    "MARZO": "03",
    "ABRIL": "04",
    "MAYO": "05",
    "JUNIO": "06",
    "JULIO": "07",
    "AGOSTO": "08",
    "SEPTIEMBRE": "09",
    "OCTUBRE": "10",
    "NOVIEMBRE": "11",
    "DICIEMBRE": "12",
}

# Fila de festividad: termina en «<DÍA> <MES>» (p. ej. "SAN PEDRO   29   JUNIO").
_FILA_FESTIVIDAD = re.compile(r"^(.*?)\s+(\d{1,2})\s+([A-ZÑÁÉÍÓÚ]+)\s*$")

# Texto de cabecera/pie que nunca es un nombre de ayuntamiento.
_RUIDO = ("AYUNTAMIENTO", "FESTIVIDAD", "FIESTAS LOCALES", "BOLETÍN OFICIAL",
          "BOC NÚM", "CVE-", "PÁG.", "ANEXO", "FIESTAS NACIONALES")


@registrar
class Cantabria(FuenteLocal):
    """Fiestas locales de Cantabria desde el PDF del BOC (calendario laboral)."""
    ccaa_iso = "ES-CB"
    nombre = "Cantabria"

    # Hub estable (no descargable directamente, solo referencia humana):
    # https://dgte.cantabria.es/calendario-laboral
    #
    # Cada año tiene su PROPIA resolución del BOC (un `idAnuBlob` distinto), con
    # el anexo «FIESTAS LOCALES» de ESE año. La resolución de cada año se publica
    # en diciembre del año anterior. NUNCA se reutiliza el documento de otro año:
    # hacerlo produciría datos falsos con el año cambiado. Para un año sin fuente
    # conocida se lanza `ValueError` (ver `descargar`).
    #
    #   2024 -> BOC núm. 234, 7-dic-2023  (Resolución calendario laboral 2024)
    #   2025 -> BOC núm. 234, 3-dic-2024  (Resolución calendario laboral 2025)
    #   2026 -> BOC núm. 238, 11-dic-2025 (Resolución calendario laboral 2026)
    _URLS_POR_ANYO: dict[int, str] = {
        2024: "https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=396704",
        2025: "https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=412944",
        2026: "https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=428192",
    }

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el PDF del BOC con el calendario del año.

        Cada año resuelve su propia resolución del BOC (`idAnuBlob` distinto) a
        través de `_URLS_POR_ANYO`, de modo que la caché es POR AÑO. Para años sin
        fuente conocida se lanza `ValueError` y NUNCA se reutiliza el documento de
        otro año (lo que daría datos falsos con el año cambiado).
        """
        url = self._URLS_POR_ANYO.get(anyo)
        if url is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-CB_{anyo}.pdf"
        if cache.exists():
            return cache.read_bytes()

        peticion = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(peticion) as resp:
            bruto = resp.read()

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Extrae las fiestas locales del anexo «FIESTAS LOCALES» del PDF.

        Cada municipio tiene dos festividades; el nombre del ayuntamiento aparece
        entre ambas. Se recorre la tabla emparejando cada fila de festividad con
        el municipio más cercano.
        """
        texto = self._extraer_texto(bruto)
        if not texto:
            return  # sin herramienta de PDF: estado parcial

        # Nos quedamos solo con el bloque del anexo de fiestas locales.
        inicio = texto.find("FIESTAS LOCALES")
        if inicio != -1:
            texto = texto[inicio:]

        municipio_actual: str | None = None
        festividad_pendiente: tuple[str, str, str] | None = None

        for linea in texto.splitlines():
            crudo = linea.strip()
            if not crudo:
                continue

            casa = _FILA_FESTIVIDAD.match(crudo)
            if casa and casa.group(3).upper() in _MESES:
                # Fila de festividad: <denominación> <día> <mes>.
                denom, dia, mes = casa.group(1).strip(), casa.group(2), casa.group(3)
                if municipio_actual is not None:
                    # La 2ª festividad del municipio en curso.
                    yield self._fiesta(municipio_actual, denom, dia, mes, anyo)
                    municipio_actual = None
                else:
                    # La 1ª festividad: aún no conocemos el municipio.
                    festividad_pendiente = (denom, dia, mes)
                continue

            nombre = self._nombre_municipio(crudo)
            if nombre is None:
                continue

            municipio_actual = nombre
            if festividad_pendiente is not None:
                denom, dia, mes = festividad_pendiente
                yield self._fiesta(nombre, denom, dia, mes, anyo)
                festividad_pendiente = None

    @staticmethod
    def _fiesta(
        municipio: str, denom: str, dia: str, mes: str, anyo: int
    ) -> FiestaLocalCruda:
        """Construye un `FiestaLocalCruda` con la fecha en ISO `YYYY-MM-DD`."""
        fecha = f"{anyo:04d}-{_MESES[mes.upper()]}-{dia.zfill(2)}"
        return FiestaLocalCruda(
            fecha=fecha,
            municipio_nombre=municipio,
            ine=None,  # la fuente no trae INE; se resuelve después por nombre
            provincia="39",  # Cantabria (CPRO 39)
            denominacion=denom or None if denom != "-" else None,
        )

    @staticmethod
    def _nombre_municipio(linea: str) -> str | None:
        """Devuelve el nombre del ayuntamiento si la línea lo es; si no, `None`."""
        mayus = linea.upper()
        if any(r in mayus for r in _RUIDO):
            return None
        # Un nombre de municipio lleva al menos una letra y no es un separador.
        if linea == "-" or not any(c.isalpha() for c in linea):
            return None
        return linea

    @staticmethod
    def _extraer_texto(bruto: bytes) -> str:
        """Extrae el texto del PDF con `pdftotext -layout` o, si no, `pdfplumber`."""
        if shutil.which("pdftotext"):
            try:
                proc = subprocess.run(
                    ["pdftotext", "-layout", "-", "-"],
                    input=bruto,
                    capture_output=True,
                    check=True,
                )
                return proc.stdout.decode("utf-8", errors="replace")
            except (subprocess.SubprocessError, OSError):
                pass

        try:
            import io

            import pdfplumber  # type: ignore

            partes: list[str] = []
            with pdfplumber.open(io.BytesIO(bruto)) as pdf:
                for pagina in pdf.pages:
                    partes.append(pagina.extract_text(layout=True) or "")
            return "\n".join(partes)
        except Exception:
            return ""
