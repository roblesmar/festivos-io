"""Fuente de fiestas locales de la Comunitat Valenciana (Generalitat Valenciana).

La Generalitat publica las fiestas locales en una resolución del DOGV (Diari
Oficial de la Generalitat Valenciana) en formato PDF con texto seleccionable
(sin OCR). El anexo lista, bajo una cabecera por provincia (Alicante, Castellón
y Valencia), un municipio por línea con el patrón:

    MUNICIPIO: fecha1[, descripción]; fecha2[, descripción].

Las fechas vienen en lengua natural («13 de abril», «27 y 28 de agosto»). No hay
código INE en la fuente, así que se deja `ine=None` y se rellena
`municipio_nombre` junto con la `provincia` (CPRO) de la cabecera para acotar el
join nombre→INE posterior. Los municipios marcados «SIN DETERMINAR» se omiten.

El texto se extrae con `pdftotext` (Poppler); si no está disponible se intenta
`pdfplumber` y, en último término, `pypdf`.
"""
from __future__ import annotations

import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Nombre de mes (en minúsculas) -> número de mes de 2 dígitos.
_MESES: dict[str, str] = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
}

# Cabecera de provincia -> código INE de 2 dígitos (CPRO).
_PROVINCIAS_INE: dict[str, str] = {
    "ALICANTE": "03",
    "CASTELLÓN": "12",
    "CASTELLON": "12",
    "VALENCIA": "46",
}

# Cabecera del anexo que abre la relación de cada provincia. Según el año, la
# maquetación del DOGV pone «… PROVINCIA DE ALICANTE 2025» en una sola línea
# (2025, 2026) o la parte en dos: «… PROVINCIA DE» y, debajo, «ALICANTE 2024»
# (2024). Por eso `parsear` reensambla la cabecera partida antes de casarla.
_RE_CABECERA = re.compile(
    r"RELACIÓN DE FIESTAS LOCALES EN LA PROVINCIA DE\s+(.+?)\s+\d{4}", re.I
)
# Apertura de la cabecera cuando provincia y año caen en la línea siguiente.
_RE_CABECERA_ABIERTA = re.compile(
    r"RELACIÓN DE FIESTAS LOCALES EN LA PROVINCIA DE\s*$", re.I
)
# Línea «CLAVE: resto» (la clave es el nombre del municipio).
_RE_ENTRADA = re.compile(r"^\s*(.+?):\s*(.*)$")
# Fecha en lengua natural: «13 de abril», «27 y 28 de agosto», «3 septiembre».
# El «de» es opcional para tolerar erratas de la fuente; el mes se valida aparte.
_RE_FECHA = re.compile(
    r"(\d{1,2})(?:\s+y\s+(\d{1,2}))?\s+(?:de\s+)?"
    r"([A-Za-zÁÉÍÓÚÜáéíóúüÀ-ÿ]+)",
    re.I,
)
# Marca del "siguiente" festivo embebido en una misma cola (lista sin «;»): una fecha
# introducida por coma o por «y» —no por «de/del», que sería parte del nombre—.
_RE_SIG_FECHA = re.compile(
    r"[,;]\s*(?:y\s+)?\d{1,2}\s+(?:de\s+)?[A-Za-z\u00c0-\u00ff]{3,}"
    r"|\sy\s+\d{1,2}\s+(?:de\s+)?[A-Za-z\u00c0-\u00ff]{3,}",
    re.I,
)

# Fragmentos de pie de página / maquetación que no forman parte del anexo.
_RUIDO = ("CVE:", "https://dogv", "Núm.", "Num.", "DOGV-")


@registrar
class Valenciana(FuenteLocal):
    """Fiestas locales de la Comunitat Valenciana desde el PDF del DOGV."""
    ccaa_iso = "ES-VC"
    nombre = "Comunitat Valenciana"

    # PDF del DOGV con la resolución del calendario de fiestas locales de CADA
    # año (la resolución de un año se publica a finales del anterior). NO hay un
    # patrón de URL deducible del año —el número de CVE es arbitrario—, así que
    # se mapea cada año a su documento concreto. Para años sin fuente conocida se
    # lanza `ValueError` y NUNCA se reutiliza el documento de otro año (lo que
    # produciría fechas falsas con el año cambiado).
    _URLS: dict[int, str] = {
        # Resolución de 30.11.2023 (DOGV 9740, 05.12.2023).
        2024: "https://dogv.gva.es/datos/2023/12/05/pdf/2023_12266.pdf",
        # Resolución de 13.11.2024 (DOGV 9986, 18.11.2024).
        2025: "https://dogv.gva.es/datos/2024/11/18/pdf/2024_11987_es.pdf",
        # Resolución de 12.11.2025 (DOGV 10238, 14.11.2025).
        2026: "https://dogv.gva.es/datos/2025/11/14/pdf/2025_46326_es.pdf",
    }

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el PDF del DOGV con el calendario del año.

        Cada año resuelve su documento concreto a través de ``_URLS`` y la caché
        es POR AÑO (la clave incluye el año). Para un año sin fuente conocida se
        lanza ``ValueError`` en lugar de reutilizar el PDF de otro año, que daría
        datos falsos al reetiquetar las fechas con el año pedido.
        """
        url = self._URLS.get(anyo)
        if url is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-VC_{anyo}.pdf"
        if cache.exists():
            return cache.read_bytes()

        peticion = urllib.request.Request(url, headers={"User-Agent": "festivos-api"})
        with urllib.request.urlopen(peticion) as resp:
            bruto = resp.read()

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Extrae el texto del PDF y emite las fiestas locales del año."""
        texto = self._extraer_texto(bruto)
        if not texto:
            return  # sin texto utilizable no hay nada que parsear

        cpro: str | None = None
        municipio: str | None = None
        buffer: list[str] = []

        def volcar() -> Iterable[FiestaLocalCruda]:
            if municipio and buffer:
                yield from self._fiestas(" ".join(buffer), municipio, cpro, anyo)

        for linea in self._lineas(texto):
            linea = linea.strip()
            if not linea or any(r in linea for r in _RUIDO):
                continue
            if re.fullmatch(r"\d+\s*/\s*\d+", linea):
                continue  # marcador «página / total»

            cab = _RE_CABECERA.search(linea)
            if cab:
                yield from volcar()
                municipio, buffer = None, []
                cpro = _PROVINCIAS_INE.get(cab.group(1).strip().upper())
                continue
            if cpro is None:
                continue  # aún en el preámbulo, antes de la primera provincia

            resto = self._inicio_municipio(linea)
            if resto is not None:
                yield from volcar()
                clave = _RE_ENTRADA.match(linea)
                municipio = clave.group(1).strip() if clave else None
                buffer = [resto]
            elif municipio:
                buffer.append(linea)  # continuación de la línea anterior

        yield from volcar()

    @staticmethod
    def _lineas(texto: str) -> Iterable[str]:
        """Itera las líneas reensamblando la cabecera de provincia partida.

        En el DOGV de 2024 la cabecera se maqueta en dos líneas («… PROVINCIA
        DE» y, debajo, «ALICANTE 2024»); se fusionan en una sola para que case
        `_RE_CABECERA`. En 2025/2026 la cabecera ya viene completa y se emite tal
        cual.
        """
        lineas = texto.splitlines()
        i = 0
        while i < len(lineas):
            linea = lineas[i]
            if _RE_CABECERA_ABIERTA.search(linea.strip()) and i + 1 < len(lineas):
                yield f"{linea.rstrip()} {lineas[i + 1].strip()}"
                i += 2
                continue
            yield linea
            i += 1

    @staticmethod
    def _inicio_municipio(linea: str) -> str | None:
        """Si la línea abre un municipio (`CLAVE: resto`), devuelve `resto`.

        La clave debe ser mayúsculas en su mayoría (los nombres del anexo van en
        versales), salvo las entidades locales menores («Eatim ...», «Mareny ...»)
        que figuran en minúsculas; en otro caso es una línea de continuación.
        """
        m = _RE_ENTRADA.match(linea)
        if not m:
            return None
        clave = m.group(1).strip()
        if not clave or len(clave) > 80:
            return None
        letras = [c for c in clave if c.isalpha()]
        if not letras:
            return None
        if sum(1 for c in letras if c.isupper()) / len(letras) >= 0.6:
            return m.group(2).strip()
        if clave.lower().startswith(("eatim", "mareny", "barraca")):
            return m.group(2).strip()
        return None

    def _fiestas(
        self, blob: str, municipio: str, cpro: str | None, anyo: int
    ) -> Iterable[FiestaLocalCruda]:
        """Extrae como mucho dos fiestas locales del texto de un municipio."""
        if "SIN DETERMINAR" in blob.upper():
            return  # el ayuntamiento no fijó aún sus fiestas

        vistas: set[str] = set()
        emitidas = 0
        for trozo in re.split(r"[;]", blob):
            for fecha, deno in self._fechas_trozo(trozo, anyo):
                if fecha in vistas:
                    continue
                vistas.add(fecha)
                emitidas += 1
                yield FiestaLocalCruda(
                    fecha=fecha,
                    municipio_nombre=municipio,
                    ine=None,  # la fuente no trae INE; se resuelve por nombre
                    provincia=cpro,
                    denominacion=deno,
                )
                if emitidas >= 2:
                    return  # máximo dos fiestas locales por municipio

    @staticmethod
    def _fechas_trozo(trozo: str, anyo: int) -> Iterable[tuple[str, str | None]]:
        """Devuelve las fechas ISO de un fragmento, con su denominación si la hay."""
        for m in _RE_FECHA.finditer(trozo):
            mes = _MESES.get(m.group(3).lower())
            if not mes:
                continue  # la palabra tras el día no es un mes válido
            cola = trozo[m.end():].lstrip(" ,").rstrip(" .;").strip()
            # Si la cola contiene otra fecha (el siguiente festivo del municipio, en la
            # misma línea y sin «;»), recórtala ahí: esa fecha y su texto son del
            # festivo siguiente, no de este (evita nombres «fusionados»).
            sig = _RE_SIG_FECHA.search(cola)
            if sig is not None:
                cola = cola[: sig.start()].strip()
            denominacion = (cola[0].upper() + cola[1:]) if cola else None
            for dia_txt in (m.group(1), m.group(2)):
                if dia_txt is None:
                    continue
                dia = int(dia_txt)
                if 1 <= dia <= 31:
                    yield f"{anyo}-{mes}-{dia:02d}", denominacion

    @staticmethod
    def _extraer_texto(bruto: bytes) -> str:
        """Extrae el texto del PDF con pdftotext, pdfplumber o pypdf (en ese orden)."""
        try:
            res = subprocess.run(
                ["pdftotext", "-nopgbrk", "-", "-"],
                input=bruto,
                capture_output=True,
                check=True,
            )
            if res.stdout.strip():
                return res.stdout.decode("utf-8", "replace")
        except (OSError, subprocess.CalledProcessError):
            pass

        import io

        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(io.BytesIO(bruto)) as pdf:
                paginas = (p.extract_text() or "" for p in pdf.pages)
                texto = "\n".join(paginas)
            if texto.strip():
                return texto
        except Exception:
            pass

        try:
            import pypdf  # type: ignore

            lector = pypdf.PdfReader(io.BytesIO(bruto))
            texto = "\n".join(p.extract_text() or "" for p in lector.pages)
            if texto.strip():
                return texto
        except Exception:
            pass

        return ""
