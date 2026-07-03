"""Tests del join nombre→INE (Matcher), con foco en la regresión del fix:
el match exacto acotado por CCAA NO debe caer al índice global y casar un
homónimo de otra comunidad (caso real: «Cordovilla» Navarra → Salamanca).

Ejecutar: PYTHONPATH=ingest python -m pytest ingest/tests -q
"""
from __future__ import annotations

from festivos.matching import Matcher
from festivos.modelo import Municipio
from festivos.repos import MunicipioRepo


def _muni(ine, name, prov, prov_name, ccaa_iso, ccaa_name, ccaa_ine):
    return Municipio(ine=ine, name=name, province=prov, province_name=prov_name,
                     ccaa_ine=ccaa_ine, ccaa_iso=ccaa_iso, ccaa_name=ccaa_name)


def _repo():
    return MunicipioRepo([
        # «Cordovilla» solo existe (con INE) en Castilla y León (Salamanca).
        _muni("37110", "Cordovilla", "37", "Salamanca", "ES-CL", "Castilla y León", "07"),
        # «Sada» es homónimo: existe en Galicia y en Navarra.
        _muni("15074", "Sada", "15", "A Coruña", "ES-GA", "Galicia", "12"),
        _muni("31218", "Sada", "31", "Navarra", "ES-NC", "Comunidad Foral de Navarra", "15"),
    ])


def test_no_fuga_global_entre_ccaa():
    """REGRESIÓN: un nombre de la fuente de Navarra sin INE propio en Navarra
    NO debe casar con el homónimo de otra CCAA."""
    m = Matcher(_repo(), fuzzy=False)
    assert m.match("Cordovilla", ccaa="ES-NC") is None
    assert "Cordovilla" in m.no_resueltos


def test_match_en_su_ccaa_si_funciona():
    m = Matcher(_repo(), fuzzy=False)
    encontrado = m.match("Cordovilla", ccaa="ES-CL")
    assert encontrado is not None and encontrado.ine == "37110"


def test_homonimo_se_resuelve_por_ccaa():
    """Mismo nombre en dos CCAA: cada uno se resuelve dentro de su ámbito."""
    m = Matcher(_repo(), fuzzy=False)
    assert m.match("Sada", ccaa="ES-GA").ine == "15074"
    assert m.match("Sada", ccaa="ES-NC").ine == "31218"


def test_sin_ambito_usa_el_global():
    """Sin ámbito, el índice global sigue resolviendo un nombre inequívoco."""
    m = Matcher(_repo(), fuzzy=False)
    assert m.match("Cordovilla").ine == "37110"
    # «Sada» es ambiguo a nivel global (dos CCAA) → no resuelve sin ámbito.
    assert m.match("Sada") is None
