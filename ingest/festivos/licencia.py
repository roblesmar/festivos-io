"""Procedencia y licencia embebidas en cada salida (provenance-as-data).

Estrategia: publicar el dato abierto bajo **CC BY 4.0** exigiendo atribución, y
hacerla EXPLÍCITA en cada fichero (no solo en el pie del sitio). Cada salida lleva
`license`, `attribution`, `homepage`, `last_updated` y `disclaimer`; además, cada
festivo conserva su `source` verificable (eso no se duplica aquí).

`last_updated` se fija una vez por ejecución (al importar el módulo): refleja
cuándo se generó el dataset, señal de frescura tras un BOE/boletín.
"""
from __future__ import annotations

from datetime import datetime, timezone

LICENSE = "CC-BY-4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
ATTRIBUTION = "festivos.io — CC BY 4.0"
HOMEPAGE = "https://festivos.io"

DISCLAIMER_FESTIVOS = (
    "Datos orientativos. No sustituyen a las fuentes oficiales (BOE, boletines "
    "autonómicos, bandos municipales): comprueba la fuente de cada festivo antes "
    "de tomar decisiones jurídicas o laborales."
)

# Marca temporal única de la ejecución (UTC), estable para todo el build.
GENERADO = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bloque(*, disclaimer: str = DISCLAIMER_FESTIVOS) -> dict:
    """Bloque de procedencia/licencia para incrustar en una salida JSON."""
    return {
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "attribution": ATTRIBUTION,
        "homepage": HOMEPAGE,
        "last_updated": GENERADO,
        "disclaimer": disclaimer,
    }


def descripcion_ics(nombre_calendario: str) -> str:
    """Texto de `X-WR-CALDESC`: atribución + licencia + aviso, para el .ics."""
    return (f"{nombre_calendario}. Fuente: {HOMEPAGE} · Datos bajo CC BY 4.0 "
            f"({LICENSE_URL}). Orientativo; verifica siempre la fuente oficial.")
