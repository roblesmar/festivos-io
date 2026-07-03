# Fuentes de datos y atribución

festivos es una obra derivada de **información del sector público español
reutilizable**. El marco legal general es la **Ley 37/2007** (modificada por la
Ley 18/2015) y el **RD 1495/2011**: la información del sector público es
reutilizable para fines comerciales y no comerciales, normalmente bajo
condición de **citar la fuente** e indicar la fecha de actualización, sin
desnaturalizar el contenido.

Cada festivo publicado conserva su origen en el campo `source` (referencia legal
+ URL), de modo que toda fecha es verificable contra el boletín correspondiente.

## Fuentes por nivel

### Nacional y autonómico — BOE

El BOE publica cada año una **«Resolución de la Dirección General de Trabajo por
la que se publica la relación de fiestas laborales para el año N»**, con un anexo
que recoge en una tabla los festivos nacionales y los de las 17 CCAA + Ceuta y
Melilla. Es la fuente única y consolidada para los niveles nacional y autonómico.

- 2026: `BOE-A-2025-21667` — https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-21667
- 2025: `BOE-A-2024-21316` — https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-21316
- XML parseable: `https://www.boe.es/diario_boe/xml.php?id={ID}`
- **Atribución requerida:** «Fuente de los datos: Agencia Estatal Boletín Oficial del Estado».

### Local / municipal — portales autonómicos

No existe una fuente nacional única de fiestas locales municipales; se integran
por comunidad autónoma:

- **Catalunya** — *Calendari de festes locals* (Generalitat, Departament d'Empresa
  i Treball), datos abiertos en Socrata:
  - Estructurado (con `codi_municipi_ine`): `https://analisi.transparenciacatalunya.cat/resource/b4eh-r8up.json`
  - ICS: `https://analisi.transparenciacatalunya.cat/download/xxnh-f2kn/text/calendar`
  - **Atribución:** «Generalitat de Catalunya. Departament d'Empresa i Treball».
- **Aragón** — *Calendario de festivos* (Aragón Open Data, **CC BY 4.0**), CSV/XLSX/ICS
  con `CodigoINE`: https://opendata.aragon.es/datos/catalogo/dataset/calendario-de-festivos-en-comunidad-de-aragon-2026
- **Andalucía** — Resolución anual en BOJA + datos abiertos de la Junta.
- Resto de CCAA: relación anual en el diario oficial autonómico/provincial (PDF/HTML).

### Referencia territorial — INE

**Instituto Nacional de Estadística**, «Relación de municipios y sus códigos por
provincias» (referencia a 1 de enero, actualización anual):

- Diccionario consolidado: `https://www.ine.es/daco/daco42/codmun/diccionario{YY}.xlsx`
  (columnas `CODAUTO, CPRO, CMUN, DC, NOMBRE`; 8.132 municipios a 1-ene-2026).
- **Atribución requerida:** citar al INE como fuente.

## Resumen de licencias de las fuentes

| Fuente | Redistribución | Uso comercial | Condición |
|---|---|---|---|
| BOE | Sí | Sí | Citar «Agencia Estatal Boletín Oficial del Estado» |
| Generalitat de Catalunya | Sí | Sí | Citar Generalitat + departamento y fecha |
| INE | Sí | Sí | Citar al INE |
| Aragón Open Data | Sí | Sí | CC BY 4.0 (citar fuente + última actualización) |

Las cuatro permiten redistribución y uso comercial con atribución, lo que hace
compatible publicar este dataset derivado bajo **CC BY 4.0** (ver LICENSE-DATA)
conservando la atribución a las administraciones de origen.

El registro de atribución **legible por máquina** (editor oficial y base legal por
nivel/CCAA) se genera en **`/v1/ref/attribution.json`** (módulo `festivos/atribucion.py`);
el sitio y los `.ics` lo usan para mostrar la atribución requerida en cada festivo.
