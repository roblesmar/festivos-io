"""Fuente de fiestas locales de Extremadura (Junta de Extremadura).

La Junta no publica datos abiertos estructurados: el calendario oficial de
fiestas locales aparece como un PDF en el Diario Oficial de Extremadura (DOE).
El anexo lista, por provincia (Badajoz y Cáceres), una línea por municipio con
el patrón ``NOMBRE.- fecha1 y fecha2.`` y las fechas en castellano
(``17 de febrero``). Aquí se extrae el texto del PDF y se parsea ese patrón.

No hay código INE en la fuente, así que se deja ``ine=None`` y se rellena
``municipio_nombre`` y ``provincia`` (CPRO de la cabecera) para acotar el join
nombre→INE posterior. Si no hay ninguna herramienta de extracción de PDF
disponible, ``parsear`` no produce registros (estado parcial).

Cada año tiene su propia Resolución y, por tanto, su propio PDF en el DOE: la
URL NO incluye el año de forma derivable (el identificador del documento es
opaco), así que se mantiene un mapa explícito ``{año: url}``. Reutilizar el PDF
de otro año produciría datos FALSOS (las fechas del documento real con el año
cambiado), de modo que para un año sin fuente conocida se lanza ``ValueError``.
"""
from __future__ import annotations

import re
import subprocess
import unicodedata
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# PDF del DOE con el calendario de fiestas locales, UNO POR AÑO. La Resolución
# que publica las fiestas del año N se dicta en otoño del año N-1, de ahí que la
# ruta del DOE quede bajo el año anterior. El identificador del documento es
# opaco (no se puede derivar del año), así que se enumeran de forma explícita:
#   2024 -> Resolución de 31 de octubre de 2023  (DOE núm. 215, de 09/11/2023)
#   2025 -> Resolución de 18 de octubre de 2024  (DOE núm. 210, de 28/10/2024)
#   2026 -> Resolución de 15 de octubre de 2025  (DOE núm. 204, de 23/10/2025)
_URLS_POR_ANYO: dict[int, str] = {
    2024: "https://doe.juntaex.es/pdfs/doe/2023/2150o/23063794.pdf",
    2025: "https://doe.juntaex.es/pdfs/doe/2024/2100o/24063588.pdf",
    2026: "https://doe.juntaex.es/pdfs/doe/2025/2040o/25063799.pdf",
}

# Nombre de mes (normalizado, sin tildes) -> número de mes.
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
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

# Nombre de provincia (normalizado) -> código INE de 2 dígitos (CPRO).
_PROVINCIAS_INE: dict[str, str] = {
    "badajoz": "06",
    "caceres": "10",
}

# Municipio capital de provincia (normalizado) -> CPRO. El anexo lista cada
# provincia empezando por su capital, así que la aparición de "BADAJOZ." o
# "CÁCERES." fija la provincia en curso. Esto cubre el caso del PDF de 2025,
# donde la cabecera "LA PROVINCIA DE CÁCERES" se pierde en la extracción de
# texto (queda en un salto de página) y, sin este respaldo, los municipios de
# Cáceres heredarían erróneamente la provincia de Badajoz.
_CAPITALES_INE: dict[str, str] = {
    "badajoz": "06",
    "caceres": "10",
}

# "La provincia de Badajoz." (2026) o "LA PROVINCIA DE BADAJOZ" (2024/2025):
# cabecera que cambia la provincia en curso. Tras normalizar (minúsculas, sin
# tildes) ambas casan; el punto final es opcional.
_RE_CABECERA = re.compile(r"^la provincia de\s+(.+?)\.?$")
# Entrada de municipio. El separador entre el nombre y las fechas varía por año:
#   2024/2026: "NOMBRE.-   17 de febrero y 24 de junio."
#   2025:      "NOMBRE.    4 de marzo y 24 de junio."   (sin guion)
# Se admite ".-" o "." seguido de >=2 espacios. Se exige que el nombre no
# contenga dígitos para no confundir el pie de página del DOE ("Lunes 28 de
# octubre de 2024.") con una entrada de municipio.
_RE_ENTRADA = re.compile(r"^([^\d.][^\d]*?)\.(?:-|\s{2,})\s*(.*)$")
# "17 de febrero", "1 de mayo"...
_RE_FECHA = re.compile(r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóúñÑ]+)")


def _normalizar(texto: str) -> str:
    """Pasa a minúsculas y elimina tildes para casar meses y provincias."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_tildes.strip().lower()


def _extraer_texto(pdf: bytes, raiz: Path) -> str:
    """Extrae el texto del PDF probando varias herramientas de forma defensiva.

    Orden de preferencia: ``pdftotext`` (CLI de poppler), ``pypdf`` y
    ``pdfplumber``. Si ninguna está disponible devuelve cadena vacía, lo que
    deja la fuente en estado parcial sin reventar el pipeline.
    """
    # 1) pdftotext (poppler) en modo -layout: mantiene en una misma línea el
    #    nombre del municipio y sus fechas (sin -layout quedan en líneas
    #    distintas), lo que simplifica el parseo posterior.
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", "-", "-"],
            input=pdf,
            capture_output=True,
            check=True,
        )
        texto = proc.stdout.decode("utf-8", "replace")
        if texto.strip():
            return texto
    except (OSError, subprocess.CalledProcessError):
        pass

    # 2) pypdf.
    try:
        import io

        import pypdf

        lector = pypdf.PdfReader(io.BytesIO(pdf))
        texto = "\n".join((p.extract_text() or "") for p in lector.pages)
        if texto.strip():
            return texto
    except Exception:  # noqa: BLE001  (cualquier fallo => probar la siguiente)
        pass

    # 3) pdfplumber.
    try:
        import io

        import pdfplumber

        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            texto = "\n".join((p.extract_text() or "") for p in doc.pages)
        if texto.strip():
            return texto
    except Exception:  # noqa: BLE001
        pass

    return ""


@registrar
class Extremadura(FuenteLocal):
    """Fiestas locales de Extremadura desde el PDF del DOE (sin INE nativo)."""
    ccaa_iso = "ES-EX"
    nombre = "Extremadura"

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el PDF del DOE con las fiestas locales.

        Cada año resuelve SU PDF a través de ``_URLS_POR_ANYO`` y la caché es
        POR AÑO (la clave incluye el año). Para un año sin fuente conocida se
        lanza ``ValueError`` en vez de reutilizar el documento de otro año, lo
        que produciría datos falsos (las fechas reales con el año cambiado).
        """
        url = _URLS_POR_ANYO.get(anyo)
        if url is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-EX_{anyo}.pdf"
        if cache.exists():
            return cache.read_bytes()

        with urllib.request.urlopen(url) as resp:
            bruto = resp.read()

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el texto del PDF en fiestas locales del año.

        Recorre el anexo línea a línea: las cabeceras "La provincia de X."
        fijan la provincia (CPRO) y cada entrada "NOMBRE.- fecha1 y fecha2."
        produce una `FiestaLocalCruda` por cada fecha (normalmente dos). El
        municipio en curso se arrastra para tolerar extracciones de PDF que
        dejen el nombre y las fechas en líneas distintas. Si la cabecera de
        provincia se pierde en la extracción (caso 2025), la capital de cada
        provincia (`_CAPITALES_INE`) actúa de respaldo para fijarla.
        """
        raiz = Path(__file__).resolve().parents[3]
        texto = _extraer_texto(bruto, raiz)

        provincia: str | None = None
        municipio: str | None = None  # entrada en curso (se arrastra)
        for linea in texto.splitlines():
            linea = linea.strip()
            if not linea:
                continue

            cabecera = _RE_CABECERA.match(_normalizar(linea))
            if cabecera:
                provincia = _PROVINCIAS_INE.get(cabecera.group(1).strip())
                municipio = None
                continue

            entrada = _RE_ENTRADA.match(linea)
            if entrada:
                municipio = entrada.group(1).strip() or None
                resto = entrada.group(2)
                # La capital fija la provincia aunque su cabecera no se haya
                # extraído (respaldo para el PDF de 2025, sin "LA PROVINCIA DE
                # CÁCERES" en el texto).
                capital = _CAPITALES_INE.get(_normalizar(municipio or ""))
                if capital is not None:
                    provincia = capital
            elif municipio is not None:
                resto = linea  # continuación con las fechas del municipio
            else:
                continue  # ruido antes de la primera entrada

            emitida = False
            for dia, mes_txt in _RE_FECHA.findall(resto):
                mes = _MESES.get(_normalizar(mes_txt))
                if not mes:
                    continue  # token "de algo" que no es un mes válido
                emitida = True
                fecha = f"{anyo:04d}-{mes:02d}-{int(dia):02d}"
                yield FiestaLocalCruda(
                    fecha=fecha,
                    municipio_nombre=municipio,
                    ine=None,  # la fuente no trae INE; se resuelve por nombre
                    provincia=provincia,
                    denominacion=None,
                )

            # Una vez emitidas las fechas del municipio se cierra la entrada: así
            # el pie de página del DOE ("Jueves 23 de octubre de 2025") que sigue
            # a la última entrada de cada página no se arrastra como una fecha más.
            if emitida:
                municipio = None
