"""Construcción del nivel local de una comunidad autónoma.

Recolecta las fiestas locales de la fuente registrada para la CCAA, resuelve cada
municipio a su código INE (directo si la fuente lo trae, o por Matcher nombre→INE
si no) y agrupa los `Festivo` por municipio.
"""
from __future__ import annotations

from collections import defaultdict

from .fuentes import REGISTRO
from .matching import Matcher, _claves, normaliza
from .modelo import Festivo, Fuente, Nivel, Tipo
from .nombres import nombre_movil, nombre_override
from .repos import MunicipioRepo

# Referencia legal/fuente por CCAA para el campo `source` de cada festivo.
_FUENTE_POR_CCAA: dict[str, tuple[str, str]] = {
    "ES-CT": ("Generalitat de Catalunya — Calendari de festes locals",
              "https://analisi.transparenciacatalunya.cat/resource/b4eh-r8up.json"),
    "ES-AN": ("Junta de Andalucía — Calendario de fiestas locales",
              "https://datos.juntadeandalucia.es/api/v0/work-calendar/all"),
}

# Prefijos de denominaciones genéricas: la fuente no da el nombre real del festivo
# (Andalucía usa la plantilla "FIESTA LOCAL EN <MUNICIPIO> (<PROVINCIA>)").
_PREFIJOS_GENERICOS = ("festiu local", "fiesta local", "festivo local", "festa local")


def _es_generico(denominacion: str) -> bool:
    texto = denominacion.strip().lower()
    return not texto or texto.startswith(_PREFIJOS_GENERICOS)


def _nombre_festivo(denominacion: str | None, iso: str) -> dict[str, str]:
    """Nombre i18n del festivo; usa un genérico cuando la fuente no da uno real."""
    if denominacion and not _es_generico(denominacion):
        return {"es": denominacion.strip()}
    if iso == "ES-CT":
        return {"es": "Festivo local", "ca": "Festa local"}
    return {"es": "Festivo local"}


def construye(iso: str, anyo: int, *, repo: MunicipioRepo,
              matcher: Matcher) -> tuple[dict[str, list[Festivo]], list[str]]:
    """Devuelve `(festivos_por_ine, no_resueltos)` para la CCAA y el año dados."""
    if iso not in REGISTRO:
        raise ValueError(f"sin fuente de fiestas locales registrada para {iso}")

    fuente = REGISTRO[iso]()
    legal_ref, legal_url = _FUENTE_POR_CCAA.get(iso, (fuente.nombre, ""))
    origen = Fuente(ref=legal_ref, url=legal_url or None)

    por_ine: dict[str, list[Festivo]] = defaultdict(list)
    no_resueltos: list[str] = []

    for cruda in fuente.parsear(fuente.descargar(anyo), anyo):
        if cruda.ine:
            ref = repo.por_ine(cruda.ine)
            if ref is None or ref.ccaa_iso != iso:
                # INE inexistente o de otra CCAA (error en la fuente).
                no_resueltos.append(f"{cruda.municipio_nombre or ''} [{cruda.ine}]")
                continue
            # Fuentes con INE nativo que cuelgan las pedanías del INE del municipio
            # padre (p. ej. Castilla y León): aceptar solo la fila del municipio.
            if cruda.municipio_nombre and normaliza(cruda.municipio_nombre) not in _claves(ref.name):
                no_resueltos.append(f"{cruda.municipio_nombre} [pedanía de {cruda.ine}]")
                continue
            ine = cruda.ine
        else:
            municipio = matcher.match(cruda.municipio_nombre or "",
                                      provincia=cruda.provincia, ccaa=iso)
            if municipio is None:
                no_resueltos.append(cruda.municipio_nombre or "?")
                continue
            ine = municipio.ine

        por_ine[ine].append(Festivo(
            date=cruda.fecha,
            name=_nombre_festivo(cruda.denominacion, iso),
            level=Nivel.LOCAL,
            type=Tipo.FIJO,
            source=origen,
        ))

    # Deduplica por fecha, aplica los nombres curados (donde el boletín solo da
    # fecha) y ordena cronológicamente.
    deduplicado: dict[str, list[Festivo]] = {}
    for ine, festivos in por_ine.items():
        unicos = {f.date: f for f in festivos}
        for festivo in unicos.values():
            # Solo rellena el nombre genérico; nunca pisa un nombre oficial.
            if _es_generico(festivo.name.get("es", "")):
                curado = (nombre_override(ine, festivo.date)
                          or nombre_movil(iso, anyo, festivo.date))
                if curado:
                    festivo.name = curado
        deduplicado[ine] = sorted(unicos.values(), key=lambda f: f.date)
    return deduplicado, no_resueltos
