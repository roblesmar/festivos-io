"""Fuente de fiestas locales de La Rioja (Gobierno de La Rioja).

La Rioja publica el *calendario laboral de fiestas locales* en el Boletín
Oficial de La Rioja (BOR) como un PDF en prosa. Cada municipio aparece en una
línea con el formato ``Municipio: <fecha> [(denominación)] y <fecha> [...]``,
con las fechas escritas en lenguaje natural (``15 de mayo``). El PDF no trae
código INE, así que se emite ``ine=None`` y ``provincia='26'`` (CPRO de La
Rioja) para acotar el posterior join nombre→INE.

Cobertura PARCIAL por diseño de la fuente: una cláusula final
``Restantes municipios de La Rioja: las dos fiestas tradicionales de cada uno
de ellos`` agrupa los municipios pequeños sin indicar fechas concretas, por lo
que esas localidades no pueden resolverse y se omiten (no se inventan fechas).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Nombre de mes (sin tildes) -> número de mes.
_MESES: dict[str, int] = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Texto de cabeceras/pies del BOR y prosa introductoria que NO son municipios.
_RUIDO: tuple[str, ...] = (
    "verificación", "BOLETÍN", "Página", "página", "Núm.", "Martes,",
    "virtud de lo dispuesto", "Dirección General", "consignan", "III.",
)

# Día con mes opcional: "15 de mayo", "25 noviembre" o un día suelto ("24 y 25").
_TOKEN_FECHA = re.compile(r"(\d{1,2})(?:\s+(?:de\s+)?([A-Za-zÁÉÍÓÚáéíóúñ]+))?")

# Denominación entre paréntesis pegada justo detrás de una fecha.
_DENOMINACION = re.compile(r"^\s*\(([^)]+)\)")


def _sin_tildes(texto: str) -> str:
    """Pasa a minúsculas y elimina tildes (para casar nombres de mes)."""
    desc = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in desc if not unicodedata.combining(c)).lower()


# PDF del BOR (visor electrónico del Gobierno de La Rioja) con el calendario
# laboral de fiestas locales de CADA año. Cada resolución se publica en un BOR
# distinto y el visor sirve el documento por su `referencia` única, así que NO
# se puede formar la URL cambiando solo el año: hay que mapear año -> referencia.
# Reutilizar la referencia de otro año devolvería el PDF de ese otro año con las
# fechas falseadas, por eso se mapea explícitamente y los años sin fuente fallan.
#
#   2024 -> BOR nº 250, 18-12-2023 (CSV BOR-A-20231218-III--4351)
#   2025 -> BOR nº 229, 21-11-2024 (CSV BOR-A-20241121-III--4272)
#   2026 -> BOR nº 159, 19-08-2025 (CSV BOR-A-20250819-III--3081)
#
# Buscador del BOR: https://web.larioja.org/bor-portada/bor (título
# 'Calendario laboral de fiestas locales del año <anyo>').
_URLS_POR_ANYO: dict[int, str] = {
    2024: (
        "https://ias1.larioja.org/boletin/Bor_Boletin_visor_Servlet"
        "?referencia=27617184-1-PDF-558324-X"
    ),
    2025: (
        "https://ias1.larioja.org/boletin/Bor_Boletin_visor_Servlet"
        "?referencia=32133760-1-PDF-565674"
    ),
    2026: (
        "https://ias1.larioja.org/boletin/Bor_Boletin_visor_Servlet"
        "?referencia=36153930-1-PDF-571537"
    ),
}


@registrar
class LaRioja(FuenteLocal):
    """Fiestas locales de La Rioja desde el PDF del BOR (prosa por municipio)."""
    ccaa_iso = "ES-RI"
    nombre = "La Rioja"

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el PDF del BOR del año.

        Resuelve el documento CORRECTO de cada año desde ``_URLS_POR_ANYO`` (cada
        año tiene su propia ``referencia`` en el visor del BOR) y la caché se
        indexa por año. Para un año sin fuente conocida lanza ``ValueError`` en
        vez de reutilizar el PDF de otro año (que daría fechas falseadas).
        """
        url = _URLS_POR_ANYO.get(anyo)
        if url is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-RI_{anyo}.pdf"
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
        """Extrae las fiestas locales del PDF (una o dos fechas por municipio).

        Emite ``ine=None`` y ``provincia='26'``; el INE se resuelve después por
        nombre. Los municipios englobados en la cláusula "Restantes municipios"
        no traen fechas y, por tanto, no se emiten.
        """
        texto = self._a_texto(bruto)
        if not texto:
            return  # sin herramienta de PDF disponible: nada que parsear

        for linea in texto.splitlines():
            linea = self._normalizar(linea)
            if ":" not in linea or any(r in linea for r in _RUIDO):
                continue

            nombre, _, resto = linea.partition(":")
            nombre = nombre.strip()
            if not nombre or nombre.startswith("Restantes"):
                continue  # municipios pequeños sin fecha: no se pueden resolver
            if not any(mes in _sin_tildes(resto) for mes in _MESES):
                continue  # la línea no contiene ninguna fecha de festivo

            for fecha, denominacion in self._fechas(resto, anyo):
                yield FiestaLocalCruda(
                    fecha=fecha,
                    municipio_nombre=nombre,
                    ine=None,  # el PDF no trae INE; se resuelve por nombre
                    provincia="26",  # CPRO de La Rioja, para acotar el join
                    denominacion=denominacion,
                )

    @staticmethod
    def _a_texto(bruto: bytes) -> str:
        """Convierte el PDF a texto con ``pdftotext -layout`` (vacío si falta)."""
        ruta = shutil.which("pdftotext")
        if not ruta:
            return ""  # sin herramienta de PDF: la fuente queda 'parcial'
        try:
            salida = subprocess.run(
                [ruta, "-layout", "-", "-"],
                input=bruto, capture_output=True, check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return ""
        return salida.stdout.decode("utf-8", errors="replace")

    @staticmethod
    def _normalizar(linea: str) -> str:
        """Sustituye separadores raros del PDF (NBSP, U+FFFD…) por espacios."""
        for ch in ("�", "￿", "\xa0"):
            linea = linea.replace(ch, " ")
        return " ".join(linea.split()).strip()

    @classmethod
    def _fechas(cls, texto: str, anyo: int) -> list[tuple[str, str | None]]:
        """Devuelve los pares ``(fecha_iso, denominación)`` de la línea.

        Los días sin mes explícito ("24 y 25 de julio") heredan el mes del
        siguiente token que sí lo tenga. La denominación, si existe, es el texto
        entre paréntesis que sigue inmediatamente a la fecha.
        """
        tokens: list[tuple[int, int | None, str | None]] = []
        for emp in _TOKEN_FECHA.finditer(texto):
            dia = int(emp.group(1))
            mes_txt = emp.group(2)
            mes = _MESES.get(_sin_tildes(mes_txt)) if mes_txt else None
            # Una palabra tras el día que no es mes => día suelto (heredará mes).
            denom = cls._denominacion(texto, emp.end())
            tokens.append((dia, mes, denom))

        # Propagar hacia atrás el mes a los días que vienen sin él.
        meses = [m for _, m, _ in tokens]
        for i in range(len(meses) - 1, -1, -1):
            if meses[i] is None:
                for j in range(i + 1, len(meses)):
                    if meses[j] is not None:
                        meses[i] = meses[j]
                        break

        fechas: list[tuple[str, str | None]] = []
        vistas: set[str] = set()
        for (dia, _, denom), mes in zip(tokens, meses):
            if mes is None or not (1 <= dia <= 31 and 1 <= mes <= 12):
                continue
            iso = f"{anyo:04d}-{mes:02d}-{dia:02d}"
            if iso in vistas:
                continue  # evita duplicar la misma fecha dentro de la línea
            vistas.add(iso)
            fechas.append((iso, denom))
        return fechas

    @staticmethod
    def _denominacion(texto: str, desde: int) -> str | None:
        """Extrae la denominación entre paréntesis que sigue a la fecha, si la hay."""
        emp = _DENOMINACION.match(texto[desde:])
        if not emp:
            return None
        denom = emp.group(1).strip()
        return denom or None
