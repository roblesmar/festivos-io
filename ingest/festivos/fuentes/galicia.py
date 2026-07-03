"""Fuente de fiestas locales de Galicia (Xunta de Galicia).

La Xunta publica el calendario laboral en su portal de datos abiertos
(`abertos.xunta.gal`) como un único CSV. El fichero trae todos los ámbitos
(estatal, autonómico y municipal); aquí nos quedamos con las filas
`ambito == "municipal"` del año solicitado. El campo `id_municipio` es el código
INE nativo del municipio (5 dígitos).

OJO: cada año tiene su PROPIO dataset (no es el mismo recurso con el año en la
ruta). El segmento `calendario-laboral-{anyo}` de la URL es cosmético y el
portal sirve siempre el documento del dataset, así que reutilizar el dataset de
2026 para 2024/2025 produciría datos FALSOS. Por eso mapeamos año -> dataset:

    2024 -> 0603    2025 -> 0613    2026 -> 0684

Además el formato del CSV cambia entre años: 2024 y 2025 usan delimitador coma
(y 2024 trae una línea basura antes de la cabecera real), mientras que 2026 usa
punto y coma. El parseo detecta el delimitador y salta hasta la cabecera real.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from pathlib import Path
from typing import Iterable

from .base import FuenteLocal, FiestaLocalCruda, registrar

# Año -> identificador de dataset en abertos.xunta.gal. Cada año es un dataset
# distinto; NO reutilizar uno para otro año (daría datos de otro año).
_DATASETS: dict[int, str] = {
    2024: "0603",
    2025: "0613",
    2026: "0684",
}

# Cabeceras esperadas del CSV (en cualquiera de los delimitadores).
_CABECERA = ("fecha", "descripcion", "ambito", "id_municipio", "lugar")


@registrar
class Galicia(FuenteLocal):
    """Fiestas locales de Galicia desde el CSV de datos abiertos de la Xunta."""
    ccaa_iso = "ES-GA"
    nombre = "Galicia"

    def descargar(self, anyo: int) -> bytes:
        """Descarga (o lee de caché) el CSV del calendario laboral del año.

        Resuelve el dataset CORRECTO de cada año vía `_DATASETS`. Para años sin
        fuente conocida lanza `ValueError` en vez de reutilizar otro documento.
        """
        dataset = _DATASETS.get(anyo)
        if dataset is None:
            raise ValueError(f"sin fuente de {self.ccaa_iso} para {anyo}")

        raiz = Path(__file__).resolve().parents[3]
        cache = raiz / ".cache" / f"local_ES-GA_{anyo}.csv"
        if cache.exists():
            return cache.read_bytes()

        url = (
            "https://abertos.xunta.gal/es/catalogo/economia-empresa-emprego/-/"
            f"dataset/{dataset}/calendario-laboral-{anyo}/001/"
            "descarga-directa-del-fichero.csv"
        )
        with urllib.request.urlopen(url) as resp:
            bruto = resp.read()

        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bruto)
        return bruto

    def parsear(self, bruto: bytes, anyo: int) -> Iterable[FiestaLocalCruda]:
        """Convierte el CSV en fiestas locales del año.

        Columnas: fecha;descripcion;ambito;id_municipio;lugar

        El delimitador varía por año (`;` en 2026, `,` en 2024/2025), la
        codificación también (UTF-8 en 2026, Windows-1252 en 2024/2025) y algún
        año antepone una línea de título antes de la cabecera real; todo ello se
        detecta automáticamente.
        """
        texto = self._decodificar(bruto)
        delimitador, contenido = self._normalizar_csv(texto)
        lector = csv.DictReader(io.StringIO(contenido), delimiter=delimitador)
        objetivo = str(anyo)

        for fila in lector:
            if (fila.get("ambito") or "").strip().lower() != "municipal":
                continue  # solo fiestas locales/municipales

            fecha = (fila.get("fecha") or "").strip()
            if len(fecha) != 10 or fecha[4] != "-" or fecha[7] != "-":
                continue  # parseo defensivo: fecha no ISO
            if fecha[:4] != objetivo:
                continue  # pertenece a otro año

            ine = (fila.get("id_municipio") or "").strip()
            if not ine.isdigit():
                continue  # registro sin código INE de municipio válido

            yield FiestaLocalCruda(
                fecha=fecha,
                municipio_nombre=(fila.get("lugar") or "").strip() or None,
                ine=ine.zfill(5),  # INE nativo del municipio
                provincia=ine.zfill(5)[:2],
                denominacion=(fila.get("descripcion") or "").strip() or None,
            )

    @staticmethod
    def _decodificar(bruto: bytes) -> str:
        """Decodifica el CSV probando UTF-8 y, si falla, Windows-1252.

        2026 viene en UTF-8 (con BOM); 2024/2025 vienen en cp1252. No se puede
        decodificar siempre como cp1252 porque convertiría las tildes UTF-8 de
        2026 en mojibake.
        """
        try:
            return bruto.decode("utf-8-sig")
        except UnicodeDecodeError:
            return bruto.decode("cp1252")

    @staticmethod
    def _normalizar_csv(texto: str) -> tuple[str, str]:
        """Devuelve `(delimitador, texto_desde_la_cabecera)`.

        Detecta el delimitador (`;` o `,`) por la cabecera `fecha...lugar` y
        descarta cualquier línea previa (p. ej. el título `Calendario laboral
        2024` del fichero de 2024).
        """
        lineas = texto.splitlines(keepends=True)
        for i, linea in enumerate(lineas):
            campos_pc = [c.strip().lower() for c in linea.rstrip("\r\n").split(";")]
            campos_co = [c.strip().lower() for c in linea.rstrip("\r\n").split(",")]
            if campos_pc[:len(_CABECERA)] == list(_CABECERA):
                return ";", "".join(lineas[i:])
            if campos_co[:len(_CABECERA)] == list(_CABECERA):
                return ",", "".join(lineas[i:])

        # No se encontró cabecera reconocible: caer al formato histórico por
        # defecto (punto y coma) sin descartar líneas, para no romper en seco.
        return ";", texto
