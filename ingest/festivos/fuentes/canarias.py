"""Fuente de fiestas locales de Canarias (Gobierno de Canarias).

El Gobierno de Canarias publica las fiestas locales en una Orden del Boletín
Oficial de Canarias (BOC), en formato HTML. Bajo el anexo «RELACIÓN DE FIESTAS
LOCALES PARA EL AÑO ...» figura, por cada municipio, una línea con su nombre en
mayúsculas seguida de sus dos fiestas locales en líneas del tipo
`DD de mes: denominación.`. La fecha viene en texto castellano y se convierte a
ISO. La fuente no trae código INE, así que se deja `ine=None` y el join
nombre→INE se resuelve después; el ámbito es toda la CCAA (dos provincias: 35
Las Palmas y 38 Santa Cruz de Tenerife), por lo que `provincia` queda en `None`.
"""
from __future__ import annotations

import re
import unicodedata
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Nombre del mes en castellano (normalizado, sin tildes) -> número de mes.
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

# Cabecera del anexo que abre la relación de fiestas locales.
_RE_ANEXO = re.compile(r"RELACION DE FIESTAS LOCALES PARA EL ANO")

# "20 de enero: Festividad de San Sebastián." -> (día, mes, denominación).
# El "de" es opcional para tolerar erratas de la fuente (p. ej. "24 octubre:").
_RE_FIESTA = re.compile(
    r"^(\d{1,2})\s+(?:de\s+)?([A-Za-zñÑáéíóúÁÉÍÓÚ]+)\s*:\s*(.+)$"
)

# Línea de municipio: en mayúsculas y terminada en punto (sin dos puntos).
_RE_MUNICIPIO = re.compile(r"^[^:\d].*\.$")


def _normalizar(texto: str) -> str:
    """Pasa a minúsculas y elimina tildes para casar cabecera y nombres de mes."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_tildes.strip().lower()


@registrar
class Canarias(FuenteLocal):
    """Fiestas locales de Canarias desde la Orden anual del BOC (HTML)."""
    ccaa_iso = "ES-CN"
    nombre = "Canarias"

    # Cada año tiene su PROPIA Orden del BOC (la del año N se publica el año
    # anterior). NO hay un documento único reutilizable: descargar el BOC de
    # otro año daría las fiestas de ese otro año con el año cambiado, es decir,
    # datos FALSOS. Por eso se mapea explícitamente la URL de cada año y los
    # años sin Orden conocida fallan en `descargar` en vez de reutilizar otra.
    #   - 2024: BOC 2023/253 (Orden de 22.12.2023), AÑO 2024.
    #   - 2025: BOC 2024/238 (Orden de 14.11.2024), AÑO 2025.
    #   - 2026: BOC 2025/165 (Orden de 6.8.2025),  AÑO 2026.
    URLS_POR_ANYO: dict[int, str] = {
        2024: "https://www.gobiernodecanarias.org/boc/2023/253/025.html",
        2025: "https://www.gobiernodecanarias.org/boc/2024/238/3948.html",
        2026: "https://www.gobiernodecanarias.org/boc/2025/165/3029.html",
    }

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el HTML del BOC con las fiestas del año.

        Resuelve la Orden CORRECTA de cada año vía `URLS_POR_ANYO` y cachea POR
        AÑO. Para un año sin Orden conocida se lanza ``ValueError`` y NUNCA se
        reutiliza el documento de otro año (eso produciría datos falsos).
        """
        url = self.URLS_POR_ANYO.get(anyo)
        if url is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-CN_{anyo}.html"
        if cache.exists():
            return cache.read_bytes()

        peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(peticion) as resp:
            bruto = resp.read()

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el HTML del BOC en fiestas locales del año.

        Recorre el texto a partir del anexo: cada línea en mayúsculas fija el
        municipio en curso y las líneas `DD de mes: denominación.` que la siguen
        generan sus fiestas locales.
        """
        for linea in self._lineas_anexo(bruto):
            municipio_actual = getattr(self, "_municipio", None)

            coincidencia = _RE_FIESTA.match(linea)
            if coincidencia and municipio_actual:
                fecha = self._fecha_iso(
                    int(coincidencia.group(1)), coincidencia.group(2), anyo
                )
                if not fecha:
                    continue  # parseo defensivo: mes/día ilegible
                denominacion = coincidencia.group(3).strip().rstrip(".").strip()
                yield FiestaLocalCruda(
                    fecha=fecha,
                    municipio_nombre=municipio_actual,
                    ine=None,         # se resuelve después con el Matcher (nombre -> INE)
                    provincia=None,   # ámbito CCAA (provincias 35 y 38)
                    denominacion=denominacion or None,
                )
                continue

            # ¿Es una cabecera de municipio?
            if _RE_MUNICIPIO.match(linea):
                candidato = linea[:-1].strip()
                if (
                    candidato
                    and candidato == candidato.upper()
                    and "GOBIERNO" not in candidato.upper()
                ):
                    self._municipio = candidato
                    continue
            # Cualquier otra línea (encabezados, notas, pie) corta el municipio.
            self._municipio = None

    def _lineas_anexo(self, bruto: bytes) -> list[str]:
        """Extrae el texto del HTML y devuelve las líneas desde el anexo."""
        try:
            from bs4 import BeautifulSoup  # dependencia opcional
            texto = BeautifulSoup(bruto, "lxml").get_text("\n")
        except Exception:
            # Repliegue sin BeautifulSoup: quitar etiquetas a mano.
            texto = re.sub(r"<[^>]+>", "\n", bruto.decode("utf-8", "replace"))

        lineas = [ln.strip() for ln in texto.split("\n") if ln.strip()]
        self._municipio = None
        for indice, linea in enumerate(lineas):
            if _RE_ANEXO.search(_normalizar(linea).upper()):
                return lineas[indice + 1:]
        return []

    @staticmethod
    def _fecha_iso(dia: int, mes_token: str, anyo: int) -> str | None:
        """Convierte (día, mes en texto, año) a ISO `YYYY-MM-DD`."""
        mes = _MESES.get(_normalizar(mes_token))
        if mes is None or not 1 <= dia <= 31:
            return None
        return f"{anyo:04d}-{mes:02d}-{dia:02d}"
