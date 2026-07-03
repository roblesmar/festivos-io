"""Fuentes de fiestas locales por comunidad autónoma (una clase por CCAA)."""
from .base import REGISTRO, FiestaLocalCruda, FuenteLocal, registrar  # noqa: F401

# Importar cada módulo registra su clase en REGISTRO mediante @registrar.
from . import (  # noqa: F401,E402
    andalucia, aragon, asturias, baleares, canarias, cantabria,
    castilla_leon, castilla_mancha, catalunya, ceuta, extremadura,
    galicia, la_rioja, madrid, melilla, murcia, navarra, pais_vasco,
    valenciana,
)
