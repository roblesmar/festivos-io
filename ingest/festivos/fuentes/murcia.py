"""Fuente de fiestas locales de la Región de Murcia.

La Dirección General de Trabajo publica el calendario laboral anual en el BORM
(Boletín Oficial de la Región de Murcia) como un anuncio en texto plano. El
apartado b) contiene una tabla, separada por tabuladores, con cada municipio y
sus dos fiestas locales: ``N <TAB> MUNICIPIO <TAB> DíaSemana <TAB> Día <TAB>
Mes <TAB> DíaSemana <TAB> Día <TAB> Mes``.

Murcia es uniprovincial (CPRO 30) y la fuente no trae código INE de municipio,
así que se deja el INE sin resolver (lo hará después el Matcher por nombre) y
se rellena ``provincia`` con el CPRO para acotar el join nombre→INE.
"""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Murcia es uniprovincial: todos los municipios comparten el CPRO 30.
_CPRO_MURCIA = "30"

# Mes en texto español (minúsculas, sin tildes irrelevantes) -> número de mes.
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

# Fila de municipio: índice + nombre + dos tripletas (DíaSemana, Día, Mes).
# Los campos van separados por tabuladores; el día de la semana se ignora.
_FILA = re.compile(
    r"^\s*\d+\t"
    r"(?P<municipio>[^\t]+?)\s*\t"
    r"[^\t]*\t(?P<dia1>\d{1,2})\t(?P<mes1>[^\t]+?)\s*\t"
    r"[^\t]*\t(?P<dia2>\d{1,2})\t(?P<mes2>[^\t]+?)\s*$"
)


@registrar
class Murcia(FuenteLocal):
    """Fiestas locales de la Región de Murcia desde el anuncio del BORM."""
    ccaa_iso = "ES-MC"
    nombre = "Región de Murcia"

    # El calendario laboral de cada año se publica en el BORM el año ANTERIOR,
    # como un anuncio distinto (no hay fórmula con el año en la URL: ni el `ano`
    # de publicación, ni el `numero`, ni el `id` son derivables del año del
    # calendario). Por eso se mapea cada año a su anuncio CONCRETO y verificado;
    # nunca se reutiliza el documento de otro año (eso daría fechas falsas).
    #   2024: BORM n.º 143, de 23.06.2023 (Resolución de 13.06.2023)
    #   2025: BORM n.º 189, de 14.08.2024 (Resolución de 02.08.2024)
    #   2026: BORM n.º 163, de 17.07.2025 (Resolución de 07.07.2025)
    _URLS: dict[int, str] = {
        2024: "https://www.borm.es/services/anuncio/ano/2023/numero/3937/txt?id=820231",
        2025: "https://www.borm.es/services/anuncio/ano/2024/numero/4214/txt?id=829471",
        2026: "https://www.borm.es/services/anuncio/ano/2025/numero/3546/txt?id=837607",
    }

    # El BORM rechaza las descargas sin un User-Agent de navegador (devuelve una
    # página captcha de Radware en vez del anuncio). Se imita uno de Safari.
    _USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
    )

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el texto del anuncio del BORM del año.

        Cada año resuelve su anuncio CONCRETO del mapa ``_URLS`` y la caché es
        POR AÑO. Para años sin anuncio conocido se lanza ``ValueError`` y nunca
        se reutiliza el documento de otro año (evita fechas falsas).
        """
        url = self._URLS.get(anyo)
        if url is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-MC_{anyo}.txt"
        if cache.exists():
            return cache.read_bytes()

        peticion = urllib.request.Request(url, headers={"User-Agent": self._USER_AGENT})
        with urllib.request.urlopen(peticion) as resp:
            bruto = resp.read()

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Extrae las dos fiestas locales de cada municipio del texto del BORM.

        Cada fila aporta dos registros (1.er y 2.º festivo). El mes viene en
        texto español y el año es el solicitado; la fecha se devuelve en ISO.
        """
        texto = bruto.decode("utf-8")

        for linea in texto.splitlines():
            m = _FILA.match(linea)
            if not m:
                continue  # parseo defensivo: encabezados, narrativa, etc.

            municipio = self._limpiar_municipio(m.group("municipio"))
            if not municipio:
                continue

            for dia, mes in (
                (m.group("dia1"), m.group("mes1")),
                (m.group("dia2"), m.group("mes2")),
            ):
                fecha = self._fecha_iso(dia, mes, anyo)
                if not fecha:
                    continue  # día/mes ilegibles: se descarta ese festivo

                yield FiestaLocalCruda(
                    fecha=fecha,
                    municipio_nombre=municipio,
                    ine=None,  # la fuente no trae INE; lo resuelve el Matcher
                    provincia=_CPRO_MURCIA,
                    denominacion=None,
                )

    @staticmethod
    def _limpiar_municipio(nombre: str) -> str:
        """Normaliza el nombre del municipio (espacios y puntos sobrantes)."""
        return nombre.strip().strip(".").strip()

    @staticmethod
    def _fecha_iso(dia: str, mes: str, anyo: int) -> str | None:
        """Construye la fecha ISO `YYYY-MM-DD` a partir de día y mes en texto.

        El mes puede arrastrar un prefijo ("de abril"); se queda con la última
        palabra. Devuelve ``None`` si el día o el mes no son válidos.
        """
        clave = mes.strip().lower().split()[-1] if mes.strip() else ""
        num_mes = _MESES.get(clave)
        if num_mes is None or not dia.isdigit():
            return None

        num_dia = int(dia)
        if not 1 <= num_dia <= 31:
            return None

        return f"{anyo:04d}-{num_mes:02d}-{num_dia:02d}"
