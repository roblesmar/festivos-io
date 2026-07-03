"""Escritura de calendarios iCalendar (RFC 5545) deterministas.

Genera un fichero `.ics` con un `VEVENT` de día completo por festivo, sin
`RRULE` (los festivos móviles y los traslados no son expresables como regla de
recurrencia). La salida es reproducible: `DTSTAMP` se recibe como parámetro y no
se calcula con `datetime.now()`.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from .. import licencia
from ..modelo import Festivo


def escribe_ics(
    path,
    eventos: list[Festivo],
    *,
    nombre_calendario: str,
    uid_scope: str,
    dtstamp: str,
    descripcion: str | None = None,
    fuente_url: str | None = None,
    prodid: str = "-//festivos.io//festivos-api//ES",
) -> None:
    """Escribe `eventos` como calendario iCalendar (RFC 5545) en `path`.

    Parámetros:
        path: ruta del fichero `.ics` a generar.
        eventos: festivos a volcar (un `VEVENT` por festivo).
        nombre_calendario: nombre legible del calendario (`NAME`/`X-WR-CALNAME`).
        uid_scope: identificador del calendario (p. ej. código INE o de CCAA)
            usado para construir `UID` estables entre regeneraciones.
        dtstamp: marca temporal UTC en formato `AAAAMMDDTHHMMSSZ`.
        prodid: identificador del producto generador (`PRODID`).
    """
    lineas: list[str] = []

    # Cabecera VCALENDAR.
    lineas.append("BEGIN:VCALENDAR")
    lineas.append("VERSION:2.0")
    lineas.append(f"PRODID:{prodid}")
    lineas.append("CALSCALE:GREGORIAN")
    lineas.append("METHOD:PUBLISH")
    lineas.append(f"NAME:{_escapa_texto(nombre_calendario)}")
    lineas.append(f"X-WR-CALNAME:{_escapa_texto(nombre_calendario)}")
    lineas.append("X-WR-TIMEZONE:Europe/Madrid")
    desc = descripcion or licencia.descripcion_ics(nombre_calendario)
    lineas.append(f"X-WR-CALDESC:{_escapa_texto(desc)}")
    if fuente_url:
        lineas.append(f"SOURCE;VALUE=URI:{fuente_url}")
        lineas.append(f"URL:{fuente_url}")

    # Un VEVENT por festivo.
    for festivo in eventos:
        lineas.extend(_construye_vevent(festivo, uid_scope=uid_scope, dtstamp=dtstamp))

    lineas.append("END:VCALENDAR")

    # Plegado a 75 octetos y terminadores CRLF.
    contenido = "".join(_pliega_linea(linea) for linea in lineas)

    salida = Path(path)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(contenido, encoding="utf-8", newline="")


def _construye_vevent(festivo: Festivo, *, uid_scope: str, dtstamp: str) -> list[str]:
    """Devuelve las líneas (sin plegar) del `VEVENT` de un festivo."""
    inicio = _compacta_fecha(festivo.date)          # AAAAMMDD del festivo
    fin = _compacta_fecha(_dia_siguiente(festivo.date))  # AAAAMMDD del día siguiente
    nivel = festivo.level.value
    resumen = _escapa_texto(_resumen(festivo.name))

    return [
        "BEGIN:VEVENT",
        f"UID:{inicio}-{uid_scope}-{nivel}@festivos.io",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;VALUE=DATE:{inicio}",
        f"DTEND;VALUE=DATE:{fin}",
        f"SUMMARY:{resumen}",
        "TRANSP:TRANSPARENT",
        f"CATEGORIES:Festivos,{nivel}",
        "END:VEVENT",
    ]


def _resumen(name: dict[str, str]) -> str:
    """Devuelve el nombre en español o, si falta, el primer idioma disponible."""
    if "es" in name:
        return name["es"]
    return next(iter(name.values()), "")


def _dia_siguiente(fecha_iso: str) -> str:
    """Devuelve la fecha ISO `AAAA-MM-DD` del día siguiente a `fecha_iso`."""
    actual = date.fromisoformat(fecha_iso)
    return (actual + timedelta(days=1)).isoformat()


def _compacta_fecha(fecha_iso: str) -> str:
    """Convierte una fecha ISO `AAAA-MM-DD` en formato `DATE` `AAAAMMDD`."""
    return fecha_iso.replace("-", "")


def _escapa_texto(texto: str) -> str:
    """Escapa un valor de texto según RFC 5545 §3.3.11.

    Reglas: `\\` y los caracteres `;` y `,` se prefijan con `\\`; los saltos de
    línea se sustituyen por `\\n`.
    """
    resultado = texto.replace("\\", "\\\\")
    resultado = resultado.replace(";", "\\;")
    resultado = resultado.replace(",", "\\,")
    resultado = resultado.replace("\r\n", "\\n")
    resultado = resultado.replace("\r", "\\n")
    resultado = resultado.replace("\n", "\\n")
    return resultado


def _pliega_linea(linea: str) -> str:
    """Pliega una línea de contenido a 75 octetos (RFC 5545 §3.1) y añade CRLF.

    El plegado opera sobre octetos UTF-8 sin partir nunca una secuencia
    multibyte: la primera línea lleva hasta 75 octetos y cada continuación
    comienza con `CRLF` + un espacio, con hasta 74 octetos de carga útil.
    """
    octetos = linea.encode("utf-8")
    if len(octetos) <= 75:
        return linea + "\r\n"

    trozos: list[bytes] = []
    inicio = 0
    limite = 75  # primera línea: 75 octetos
    while inicio < len(octetos):
        fin = min(inicio + limite, len(octetos))
        # Retrocede para no partir una secuencia multibyte UTF-8: los octetos de
        # continuación tienen los bits altos `10xxxxxx` (0x80–0xBF).
        while fin > inicio and fin < len(octetos) and (octetos[fin] & 0xC0) == 0x80:
            fin -= 1
        trozos.append(octetos[inicio:fin])
        inicio = fin
        limite = 74  # continuaciones: 1 octeto de espacio + 74 de carga

    primera = trozos[0].decode("utf-8")
    continuaciones = ("\r\n " + trozo.decode("utf-8") for trozo in trozos[1:])
    return primera + "".join(continuaciones) + "\r\n"
