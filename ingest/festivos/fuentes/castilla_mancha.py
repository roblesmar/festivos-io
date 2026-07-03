"""Fuente de fiestas locales de Castilla-La Mancha (Junta de Comunidades).

La Junta publica la relación de fiestas locales como cinco bloques tabulares,
uno por provincia. Cada bloque empieza por una fila de título («Relación de
Fiestas Locales de <Provincia>»), una fila de cabecera (Municipio | Fiestas) y
luego una fila por municipio con sus dos festivos locales escritos en castellano
(«8 de mayo y 29 de septiembre»).

El recurso CAMBIA de formato según el año y NO hay una URL única: cada año tiene
su propio documento, resuelto en `_FUENTES_POR_ANYO`. En unos años el documento
es el HTML del Diario Oficial de Castilla-La Mancha (DOCM) con cinco `<table>`;
en otros es el XLSX de fiestas locales del portal de datos abiertos. Ambos
formatos comparten la MISMA estructura lógica (título de provincia, cabecera y
filas «Municipio | Fiestas»), de modo que se normalizan a una lista de tablas
común y el parseo de filas/fechas es idéntico para los dos.

IMPORTANTE: el documento de un año NUNCA se reutiliza para otro. Reutilizarlo
produciría datos FALSOS, porque las fechas son las reales de SU año. Para un año
sin fuente conocida se lanza `ValueError` en vez de devolver el documento de
otro año.

No hay código INE en la fuente, así que se deja `ine=None`, se rellena
`municipio_nombre` y se acota el join con la provincia (CPRO) deducida del
título de cada tabla. El parser de fechas es defensivo: tolera el «de» omitido o
desplazado, el día pegado al «de», comas como separador y el mes ausente en la
primera fecha (que se hereda de la siguiente).
"""
from __future__ import annotations

import io
import re
import unicodedata
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

import openpyxl

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Documento de fiestas locales por año. Cada año tiene su propio recurso y su
# formato (`html` del DOCM o `xlsx` de datos abiertos); ambos comparten la misma
# estructura lógica de tablas. Para añadir un año nuevo basta con dar de alta su
# recurso aquí. 2024 se omite a propósito: el DOCM de ese año publica las tablas
# como imágenes (anexos escaneados), no como tablas legibles, y el portal de
# datos abiertos no lo ofrece, así que no hay fuente parseable y se falla limpio.
_FUENTES_POR_ANYO: dict[int, dict[str, str]] = {
    2025: {
        # Portal de datos abiertos de CLM: XLSX de fiestas locales 2025.
        "formato": "xlsx",
        "url": (
            "https://datosabiertos.castillalamancha.es/sites/"
            "datosabiertos.castillalamancha.es/files/"
            "CALENDARIO%20FESTIVOS%20LOCALES%202025.xlsx"
        ),
    },
    2026: {
        # DOCM 12/12/2025 (2025_9468): HTML con cinco tablas, una por provincia.
        "formato": "html",
        "url": (
            "https://docm.jccm.es/docm/verArchivoHtml.do"
            "?ruta=2025/12/12/html/2025_9468.html&tipo=rutaDocm"
        ),
    },
}

# Nombre de provincia (normalizado) -> código INE de 2 dígitos (CPRO).
_PROVINCIAS_INE: dict[str, str] = {
    "albacete": "02",
    "ciudad real": "13",
    "cuenca": "16",
    "guadalajara": "19",
    "toledo": "45",
}

# Nombre de mes en castellano -> número de mes.
_MESES: dict[str, int] = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Día (1-2 dígitos) + «de» opcional + mes opcional (puede heredarse del siguiente).
_FECHA_RE = re.compile(
    r"(\d{1,2})\s*(?:de\s+)?(?:(" + "|".join(_MESES) + r")\b)?",
    re.IGNORECASE,
)

# Reconoce la provincia en la fila de título de cada tabla.
_TITULO_RE = re.compile(r"Fiestas Locales de\s+(.+)$", re.IGNORECASE)


def _normalizar(texto: str) -> str:
    """Pasa a minúsculas y elimina tildes para casar nombres de provincia."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_tildes.strip().lower()


class _TablasHTML(HTMLParser):
    """Extrae las tablas del DOCM como listas de filas (cada fila, lista de celdas)."""

    def __init__(self) -> None:
        super().__init__()
        self.tablas: list[list[list[str]]] = []
        self._tabla: list[list[str]] | None = None
        self._fila: list[str] | None = None
        self._celda: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._tabla = []
        elif tag == "tr" and self._tabla is not None:
            self._fila = []
        elif tag in ("td", "th") and self._fila is not None:
            self._celda = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._celda is not None:
            self._fila.append(" ".join("".join(self._celda).split()))  # type: ignore[union-attr]
            self._celda = None
        elif tag == "tr" and self._fila is not None:
            self._tabla.append(self._fila)  # type: ignore[union-attr]
            self._fila = None
        elif tag == "table" and self._tabla is not None:
            self.tablas.append(self._tabla)
            self._tabla = None

    def handle_data(self, data: str) -> None:
        if self._celda is not None:
            self._celda.append(data)


@registrar
class CastillaMancha(FuenteLocal):
    """Fiestas locales de Castilla-La Mancha desde el HTML del DOCM."""
    ccaa_iso = "ES-CM"
    nombre = "Castilla-La Mancha"

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el documento de fiestas locales del año.

        Resuelve el recurso CORRECTO de cada año en `_FUENTES_POR_ANYO`. La caché
        es POR AÑO (la clave incluye el año y el formato), de modo que el
        documento de un año nunca se confunde con el de otro. Si no hay fuente
        conocida para el año pedido se lanza `ValueError` en vez de reutilizar el
        documento de otro año (lo que daría fechas FALSAS con el año cambiado).
        """
        fuente = _FUENTES_POR_ANYO.get(anyo)
        if fuente is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-CM_{anyo}.{fuente['formato']}"
        if cache.exists():
            return cache.read_bytes()

        peticion = urllib.request.Request(
            fuente["url"], headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(peticion) as resp:
            bruto = resp.read()

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el documento del año en fiestas locales.

        El documento es HTML (DOCM) o XLSX (datos abiertos) según el año; en
        ambos casos se normaliza a una lista de tablas, una por provincia. Sus
        filas (saltando título y cabecera) traen «Municipio | Fiestas» con dos
        festivos en castellano, y el parseo es idéntico para los dos formatos.
        """
        fuente = _FUENTES_POR_ANYO.get(anyo)
        if fuente is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        if fuente["formato"] == "xlsx":
            tablas = self._tablas_xlsx(bruto)
        else:
            tablas = self._tablas_html(bruto)

        for tabla in tablas:
            if not tabla:
                continue
            provincia = self._provincia_de_titulo(tabla[0])

            for fila in tabla[1:]:
                if len(fila) < 2:
                    continue  # cabecera u otra fila sin las dos columnas
                municipio = fila[0].strip()
                celda_fiestas = fila[1].strip()
                if not municipio or not celda_fiestas:
                    continue  # parseo defensivo: fila incompleta
                if "fiesta" in municipio.lower():
                    continue  # fila de cabecera (Municipio | Fiestas)

                for fecha in self._fechas_iso(celda_fiestas, anyo):
                    yield FiestaLocalCruda(
                        fecha=fecha,
                        municipio_nombre=municipio,
                        ine=None,  # el DOCM no trae INE: se resuelve por nombre
                        provincia=provincia,
                        denominacion="Fiesta local",
                    )

    @staticmethod
    def _tablas_html(bruto: bytes) -> list[list[list[str]]]:
        """Normaliza el HTML del DOCM a una lista de tablas (filas de celdas)."""
        texto = bruto.decode("utf-8", errors="replace")
        analizador = _TablasHTML()
        analizador.feed(texto)
        return analizador.tablas

    @staticmethod
    def _tablas_xlsx(bruto: bytes) -> list[list[list[str]]]:
        """Normaliza el XLSX de datos abiertos a la MISMA estructura de tablas.

        La hoja única encadena las cinco provincias: una fila de título
        («Relación de Fiestas Locales de <Provincia>»), una de cabecera
        («Municipio | Fiestas») y las filas de municipios. Se trocea en una tabla
        por provincia (cada título abre una tabla) para que el parseo de filas
        sea idéntico al del HTML.
        """
        wb = openpyxl.load_workbook(io.BytesIO(bruto), read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]

        tablas: list[list[list[str]]] = []
        for fila in ws.iter_rows(values_only=True):
            celdas = ["" if v is None else str(v).strip() for v in fila]
            while celdas and celdas[-1] == "":
                celdas.pop()  # descarta celdas vacías a la derecha
            if not celdas:
                continue  # fila en blanco entre provincias
            if _TITULO_RE.search(celdas[0]):
                tablas.append([celdas])  # nueva provincia: abre tabla con su título
            elif tablas:
                tablas[-1].append(celdas)
        return tablas

    @staticmethod
    def _provincia_de_titulo(fila_titulo: list[str]) -> str | None:
        """Deduce el CPRO (2 dígitos) del título «... Fiestas Locales de <Prov>»."""
        if not fila_titulo:
            return None
        match = _TITULO_RE.search(fila_titulo[0])
        if not match:
            return None
        return _PROVINCIAS_INE.get(_normalizar(match.group(1)))

    @staticmethod
    def _fechas_iso(texto: str, anyo: int) -> list[str]:
        """Extrae las fechas de la celda y las devuelve en ISO `YYYY-MM-DD`.

        Tolera el «de» omitido/desplazado, el día pegado al «de», comas como
        separador y el mes ausente en una fecha (que se hereda de la siguiente).
        """
        pares: list[list[int | None]] = []
        for match in _FECHA_RE.finditer(texto.lower()):
            dia = int(match.group(1))
            mes = _MESES.get(match.group(2)) if match.group(2) else None
            pares.append([dia, mes])

        # Rellena el mes ausente con el de la siguiente fecha que sí lo trae.
        ultimo: int | None = None
        for par in reversed(pares):
            if par[1] is None:
                par[1] = ultimo
            else:
                ultimo = par[1]

        fechas: list[str] = []
        for dia, mes in pares:
            if mes is None or dia is None:
                continue
            if not (1 <= dia <= 31 and 1 <= mes <= 12):
                continue  # valor fuera de rango: se descarta
            fecha = f"{anyo:04d}-{mes:02d}-{dia:02d}"
            if fecha not in fechas:
                fechas.append(fecha)  # evita duplicados dentro de la misma celda
        return fechas
