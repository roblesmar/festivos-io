"""Feeds iCalendar oficiales de la AEAT (calendario del contribuyente).

La Agencia Tributaria publica el calendario como ~13 calendarios públicos
(Google Calendar, formato .ics RFC 5545), uno por figura tributaria, listados en:
  sede.agenciatributaria.gob.es/Sede/ayuda/calendario-contribuyente/icalendar/instrucciones-integrar-calendario.html

Cada feed es acumulativo multianual: al construir un año se filtra por DTSTART.
Las URLs `www.google.com/...` responden 302 → `calendar.google.com/...`; urllib
sigue la redirección automáticamente.
"""
from __future__ import annotations

# Una URL por figura tributaria (orden: Renta, Renta y Sociedades, Sociedades, IVA,
# Informativas, IIEE, Primas de seguros, Depósitos, NIF, Cuenta Corriente Tributaria,
# Servicios digitales, Transacciones financieras, y el último calendario publicado).
FEEDS: tuple[str, ...] = (
    "https://www.google.com/calendar/ical/invitado2aeat%40gmail.com/public/basic.ics",
    "https://www.google.com/calendar/ical/aio2b0s64q65r7v87j5ma8fvog%40group.calendar.google.com/public/basic.ics",
    "https://www.google.com/calendar/ical/b7g1j3bod3gdjbka03uo6kr988%40group.calendar.google.com/public/basic.ics",
    "https://www.google.com/calendar/ical/517mcuhcis0lldnp9b7c0nk2q8%40group.calendar.google.com/public/basic.ics",
    "https://www.google.com/calendar/ical/hqp9h5ft4snag42aea96791g28%40group.calendar.google.com/public/basic.ics",
    "https://calendar.google.com/calendar/ical/mvdk363hjsatf9c2524ja2npo8%40group.calendar.google.com/public/basic.ics",
    "https://www.google.com/calendar/ical/1rr0g308smpmmffgmsnc6pnsh8%40group.calendar.google.com/public/basic.ics",
    "https://www.google.com/calendar/ical/g8q6rbiq56i8al6sm0vabq6nlk%40group.calendar.google.com/public/basic.ics",
    "https://www.google.com/calendar/ical/p39ok1tj2rrm7vrs65lscihuks%40group.calendar.google.com/public/basic.ics",
    "https://www.google.com/calendar/ical/jaktdfpo1d6frode4enl3of2jk%40group.calendar.google.com/public/basic.ics",
    "https://www.google.com/calendar/ical/tekufkgl2uie27akil3mslp36g%40group.calendar.google.com/public/basic.ics",
    "https://www.google.com/calendar/ical/h49aor2o93bmm0ierkvh9r8jis%40group.calendar.google.com/public/basic.ics",
    "https://calendar.google.com/calendar/ical/kt3mgvpnivgb640ak8jr134lks%40group.calendar.google.com/public/basic.ics",
)


def categoria(summary: str) -> str:
    """Normaliza la figura tributaria (SUMMARY del feed) a una categoría-slug."""
    s = summary.upper()
    if "TRANSACCIONES FINANCIERAS" in s:
        return "transacciones-financieras"
    if "SERVICIOS DIGITALES" in s:
        return "servicios-digitales"
    if "PRIMAS DE SEGUROS" in s:
        return "primas-seguros"
    if "IMPUESTOS ESPECIALES" in s:
        return "iiee"
    if "DECLARACIONES INFORMATIVAS" in s:
        return "informativas"
    if "RENTA Y SOCIEDADES" in s:
        return "retenciones"
    if "SOCIEDADES" in s:
        return "sociedades"
    if s == "RENTA":
        return "renta"
    if s == "IVA":
        return "iva"
    if "IDENTIFICACI" in s:  # Número de Identificación Fiscal
        return "censos"
    return "otros"
