# Guía de ingesta de fiestas locales municipales (España, 2026)

Guía operativa para integrar las **fiestas locales municipales** de las 17 CCAA + Ceuta y
Melilla en `festivos`. Una fuente por comunidad autónoma. El objetivo es cubrir los
**~8.132 municipios** de España con el calendario de fiestas locales (normalmente 2 por
municipio; 1 en Navarra; 2 fijas en Ceuta y Melilla, que son municipio único).

Clave territorial del proyecto: **código INE de municipio (5 dígitos)**. Donde la fuente no
lo trae, hay que enriquecer por *join* nombre→INE contra el diccionario INE
(`diccionario{YY}.xlsx`, ver `FUENTES.md`).

Estado de las fuentes verificado a **27/06/2026** (una revisión por comunidad autónoma).

---

## 1. Mastertabla (ordenada por dificultad)

| CCAA | Boletín / portal | Formato | ¿INE? | Método de ingesta | Dificultad | Confianza | URL principal |
|---|---|---|:---:|---|:---:|:---:|---|
| **Aragón** (ES-AR) | Aragón Open Data | CSV/XLSX/ICS | ✅ sí | Descarga CSV directa (`;`), col. `CodigoINE` | fácil | alta | `https://opendata.aragon.es/datos/catalogo/dataset/calendario-de-festivos-en-comunidad-de-aragon-2026` |
| **Castilla y León** (ES-CL) | Opendatasoft JCyL | CSV/JSON/XLSX | ✅ sí | Explore API v2.1, filtro `where=fecha_fiesta` 2026; campo `ine` | fácil | alta | `https://analisis.datosabiertos.jcyl.es/explore/dataset/fiestas-locales-calendario-de-fiestas-de-caracter-local/` |
| **Catalunya** (ES-CT) | SODA / Transparència | JSON/CSV/ICS | ✅ sí | API SODA `$where=any_calendari='2026'`; `codi_municipi_ine` | fácil | alta | `https://analisi.transparenciacatalunya.cat/resource/b4eh-r8up.json?$where=any_calendari='2026'&$limit=5000` |
| **Galicia** (ES-GA) | Abertos Xunta (dataset 0684) | CSV/XLSX/ICS | ✅ sí | CSV (`;`), filtrar `ambito='municipal'`; `id_municipio` = INE | fácil | alta | `https://abertos.xunta.gal/es/catalogo/economia-empresa-emprego/-/dataset/0684/calendario-laboral-2026/001/descarga-directa-del-fichero.csv` |
| **Madrid** (ES-MD) | datos.comunidad.madrid (CKAN) | CSV/JSON | ⚠️ derivable | CSV (`;`, latin-1); INE = `28` + `municipio_codigo` (3 díg.) | fácil | alta | `https://datos.comunidad.madrid/catalogo/dataset/f160eb6c-6715-471e-9bc0-38497aae950f/resource/ba59e7e8-3d8d-4221-a5fa-b5e78b82707f/download/festivos_locales.csv` |
| **Andalucía** (ES-AN) | datos.juntadeandalucia.es | CSV/JSON/ICS | ❌ no | API work-calendar (`\|`), filtrar `type=LOCAL` + `year=2026`; join nombre→INE | fácil | alta | `https://datos.juntadeandalucia.es/api/v0/work-calendar/all?format=csv` |
| **Asturias** (ES-AS) | descargas.asturias.es | JSON/CSV/XLSX | ❌ no | JSON (UTF-8) recomendado; filtrar `AMBITO=LOCAL`; join nombre→INE | fácil | alta | `https://descargas.asturias.es/asturias/opendata/CulturayOcio/calendario/dataset_calendario_festivos.json` |
| **Navarra** (ES-NC) | Datos Abiertos Navarra (CKAN) | CSV/JSON | ❌ no | CKAN dump CSV (UTF-8 BOM); **1 fiesta/localidad**; join nombre→INE | fácil | alta | `https://datosabiertos.navarra.es/es/datastore/dump/f48e36ae-a700-4796-ab37-9ec0a353cfa1?format=csv&bom=True` |
| **País Vasco** (ES-PV) | Open Data Euskadi | CSV/JSON/XLSX/ICS | ❌ no | CSV (`;`); 1 local/municipio + común territorio; join nombre/coord→INE | fácil | alta | `https://opendata.euskadi.eus/contenidos/ds_eventos/calendario_laboral_2026/opendata/calendario_laboral_2026.csv` |
| **Illes Balears** (ES-IB) | intranet.caib.es / datos.gob.es | CSV | ❌ no | CSV (ISO-8859-1); fecha en catalán texto; join nombre→INE | fácil | alta | `https://intranet.caib.es/opendatacataleg/dataset/e89fb44b-67f3-4e29-affc-2df135b719e5/resource/edf08154-bbc0-4259-a254-3b0185411354/download/calendari-laboral-2026.csv` |
| **Murcia** (ES-MC) | BORM (HTML/PDF) | HTML | ❌ no | Parsear endpoint `/txt` del anuncio 3546; mes texto→fecha; join nombre→INE | media | alta | `https://www.borm.es/services/anuncio/ano/2025/numero/3546/txt?id=837607` |
| **Canarias** (ES-CN) | BOC (HTML/PDF) | HTML | ❌ no | Parsear HTML BOC disp. 3029; 88 municipios×2; join nombre→INE | media | alta | `https://www.gobiernodecanarias.org/boc/2025/165/3029.html` |
| **Castilla-La Mancha** (ES-CM) | DOCM (HTML/PDF) | PDF/HTML | ❌ no | Parsear HTML/PDF DOCM `[2025/9468]`; fecha texto; join nombre→INE | media | alta | `https://docm.jccm.es/docm/verArchivoHtml.do?ruta=2025/12/12/html/2025_9468.html&tipo=rutaDocm` |
| **C. Valenciana** (ES-VC) | DOGV (PDF) | PDF | ❌ no | `pdftotext` (sin OCR) DOGV 2025_46326; regex prosa; join nombre→INE | media | alta | `https://dogv.gva.es/datos/2025/11/14/pdf/2025_46326_es.pdf` |
| **Extremadura** (ES-EX) | DOE (PDF) / datos.gob.es (XLSX) | PDF/XLSX | ❌ no | XLSX abierto (sólo 2025 publicado) o PDF DOE 204; join nombre→INE | media | alta | `https://doe.juntaex.es/pdfs/doe/2025/2040o/25063799.pdf` |
| **Ceuta** (ES-CE) | BOCCE (PDF) | PDF | ❌ manual | Municipio único INE **51001**; 2 fechas fijas (20/03, 13/06) | media | alta | `https://www.ceuta.es/ceuta/bocce` |
| **Melilla** (ES-ML) | BOME (HTML/PDF) | HTML | ❌ manual | Municipio único INE **52001**; 2 fechas fijas (08/09, 17/09) | media | alta | `https://bomemelilla.es/bome/BOME-B-2025-6315/articulo/1033` |
| **Cantabria** (ES-CB) | BOC (PDF) | PDF | ❌ no | `pdftotext -layout` BOC 238; tabla AYUNTAMIENTO\|FESTIVIDAD; join nombre→INE | difícil | alta | `https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=428192` |
| **La Rioja** (ES-RI) | BOR (PDF) | PDF | ❌ no | `pdftotext -layout` BOR 159; **prosa + cláusula "Restantes municipios"** | difícil | alta | `https://ias1.larioja.org/boletin/Bor_Boletin_visor_Servlet?referencia=36153930-1-PDF-571537` |

> No hay ninguna CCAA realmente **bloqueada**: las 19 fuentes están localizadas y verificadas.
> Las únicas marcadas «difícil» (Cantabria, La Rioja) lo son por ser PDF maquetado y, en La
> Rioja, por cobertura incompleta (cláusula genérica para municipios pequeños).

---

## 2. Resumen ejecutivo

**Reparto por facilidad de ingesta (19 fuentes):**

| Categoría | Nº CCAA | CCAA |
|---|:---:|---|
| 🟢 Datos abiertos estructurados **con INE nativo/derivable** | **5** | Aragón, Castilla y León, Catalunya, Galicia, Madrid* |
| 🟢 Datos abiertos estructurados **sin INE** (join por nombre) | **5** | Andalucía, Asturias, Navarra, País Vasco, Illes Balears |
| 🟡 Parseo **HTML** | **3** | Murcia, Canarias, Castilla-La Mancha (HTML disponible) |
| 🟠 Parseo **PDF** | **6** | C. Valenciana, Extremadura, Cantabria, La Rioja, Ceuta, Melilla |
| 🔴 Bloqueadas (sin fuente) | **0** | — |

\* Madrid no trae el INE literal pero es **trivialmente derivable**: `INE = 28 + municipio_codigo`
(3 dígitos con cero a la izquierda). Verificado: Madrid `079`→`28079`, Alcalá `005`→`28005`.

**Cobertura estimada de los ~8.132 municipios por las fuentes «fáciles»**

Las **10 CCAA fáciles** (datos estructurados, con o sin INE) cubren de forma directa, según
los conteos reales descargados:

| CCAA | Municipios cubiertos (aprox.) |
|---|---:|
| Castilla y León | ~2.248 (5.044 reg. / 2) |
| Catalunya | ~947 (+ pedanías; 2.794 reg.) |
| Andalucía | 774 (de ~785) |
| Aragón | ~731 (3 provincias) |
| Galicia | 313 (exacto) |
| País Vasco | 251 |
| Navarra | 272 municipios (publicado por ~694 localidades) |
| Madrid | 165 (de 179; resto «no comunicado») |
| Illes Balears | 67 (exacto) |
| Asturias | 78 (exacto) |

**Total fáciles ≈ 5.846 municipios → ~72 % de los 8.132.** Sumando las 3 HTML (Murcia 45,
Canarias 88, Castilla-La Mancha ~919) se llega a **~6.898 ≈ 85 %**, y con las 6 PDF
(C. Valenciana ~542, Extremadura ~442, Cantabria 102, La Rioja ~174, Ceuta 1, Melilla 1) se
alcanza la **cobertura prácticamente total (~100 %)**.

Conclusión: con la **Oleada 1 (10 CCAA estructuradas)** se cubre ~72 % de los municipios con
esfuerzo mínimo; el 28 % restante exige parseo HTML/PDF pero todas las fuentes existen.

---

## 3. Plan de ingesta por oleadas

### Oleada 1 — Datos estructurados (10 CCAA, ~72 % municipios)

Descarga directa + parseo trivial. Prioridad máxima.

**1a. Con código INE nativo o derivable (5):**

- **Aragón** — `GET https://opendata.aragon.es/datos/catalogo/dataset/calendario-de-festivos-en-comunidad-de-aragon-2026` → abrir y tomar el enlace del recurso `festivos_aragon_2026_completo.csv` (UUID cambia cada año). CSV `;`, cols `Provincia;CodigoINE;Municipio;Fecha(DD-MM-AAAA);NombreFestivo`. INE listo.
- **Castilla y León** — `GET https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/fiestas-locales-calendario-de-fiestas-de-caracter-local/exports/csv?where=fecha_fiesta>='2026-01-01' and fecha_fiesta<='2026-12-31'`. Campos `provincia;municipio;fecha_fiesta;nombre_fiesta;ine`. INE listo (zero-pad a 5).
- **Catalunya** — `GET https://analisi.transparenciacatalunya.cat/resource/b4eh-r8up.json?$where=any_calendari='2026'&$limit=5000`. Campo `codi_municipi_ine` (5 díg.), `data` ISO. INE listo. Re-descargar tras modificaciones (Ordre EMT/3/2026).
- **Galicia** — `GET https://abertos.xunta.gal/es/catalogo/economia-empresa-emprego/-/dataset/0684/calendario-laboral-2026/001/descarga-directa-del-fichero.csv`. CSV `;`, filtrar `ambito='municipal'`. `id_municipio` = INE. 626 reg. = 313 concellos × 2.
- **Madrid** — `GET https://datos.comunidad.madrid/catalogo/dataset/f160eb6c-6715-471e-9bc0-38497aae950f/resource/ba59e7e8-3d8d-4221-a5fa-b5e78b82707f/download/festivos_locales.csv` (mejor resolver vía CKAN `package_show?id=festivos_regionales_locales`). latin-1→UTF-8. **INE = `28`+`municipio_codigo`.**

**1b. Estructurado sin INE — requiere join nombre→INE (5):**

- **Andalucía** — `GET https://datos.juntadeandalucia.es/api/v0/work-calendar/all?format=csv` (delim. `|`). Filtrar `type=LOCAL` y `year=2026`. Join `municipality`+`province`→INE.
- **Asturias** — `GET https://descargas.asturias.es/asturias/opendata/CulturayOcio/calendario/dataset_calendario_festivos.json` (UTF-8). Filtrar `AMBITO='LOCAL'` y fecha 2026. Join nombre concejo→INE (78 concejos).
- **Navarra** — `GET https://datosabiertos.navarra.es/es/datastore/dump/f48e36ae-a700-4796-ab37-9ec0a353cfa1?format=csv&bom=True`. Cols `LOCALIDAD,DIA,MES,NOTAS`. **OJO: 1 fiesta por localidad** (modelo navarro). Mes texto español→fecha; gestionar fiestas móviles en `NOTAS`. Join localidad→INE.
- **País Vasco** — `GET https://opendata.euskadi.eus/contenidos/ds_eventos/calendario_laboral_2026/opendata/calendario_laboral_2026.csv` (delim. `;`). `municipalitycode` **NO es INE** (índice EUSTAT interno). Join por `municipalityEs`/coords WGS84→INE. La 2ª fiesta local es la común del territorio (28/04 San Prudencio en Araba; 31/07 San Ignacio en Bizkaia/Gipuzkoa).
- **Illes Balears** — `GET https://intranet.caib.es/opendatacataleg/dataset/e89fb44b-67f3-4e29-affc-2df135b719e5/resource/edf08154-bbc0-4259-a254-3b0185411354/download/calendari-laboral-2026.csv` (ISO-8859-1, resolver URL vía ficha datos.gob.es `a04003003-...-2026`). Filtrar `Ambit='Local'`. Fecha en catalán texto (`24 de juny`)→ISO. Join municipi→INE (67).

### Oleada 2 — HTML parseable (3 CCAA)

- **Murcia** — `GET https://www.borm.es/services/anuncio/ano/2025/numero/3546/txt?id=837607`. Tabla nº/MUNICIPIO/festivo1/festivo2; mes texto→fecha 2026. Join nombre→INE 30xxx (45 municipios; cuidado con artículo pospuesto «ALCÁZARES, LOS»).
- **Canarias** — `GET https://www.gobiernodecanarias.org/boc/2025/165/3029.html`. Anexo «RELACIÓN DE FIESTAS LOCALES PARA EL AÑO 2026», formato `MUNICIPIO. DD de mes: denominación`. 88 municipios × 2. Join nombre→INE.
- **Castilla-La Mancha** — `GET https://docm.jccm.es/docm/verArchivoHtml.do?ruta=2025/12/12/html/2025_9468.html&tipo=rutaDocm`. Tabla `Municipios`/`Fiestas` por provincia. Fecha texto español («8 de mayo y 29 de septiembre»)→ISO. Join nombre→INE. (El XLSX abierto 2026 aún no estaba publicado a 27/06/2026; sólo existe el de 2025.)

### Oleada 3 — Parseo PDF (6 CCAA)

- **C. Valenciana** — `pdftotext` sobre `https://dogv.gva.es/datos/2025/11/14/pdf/2025_46326_es.pdf` (texto seleccionable, sin OCR). Regex `MUNICIPIO: fecha1[, desc]; fecha2[, desc].` por las 3 cabeceras de provincia. Aplicar **2 modificaciones**: `2026_1043` (Alcosser, Onil, Penàguila, Villamalur, Benissoda) y `2026_6733` (Orba). Join nombre→INE (~542).
- **Extremadura** — Preferido cuando exista: XLSX abierto (ficha `datos.gob.es/.../a11002926`, a 27/06/2026 aún apunta a 2025). Mientras tanto PDF `https://doe.juntaex.es/pdfs/doe/2025/2040o/25063799.pdf`, regex `NOMBRE.- fecha1 y fecha2.` por provincia. Aplicar modificación DOE nº24 (05/02/2026). Join nombre→INE.
- **Cantabria** — `pdftotext -layout https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=428192`. Tabla `AYUNTAMIENTO|FESTIVIDAD|DÍA|MES`, 2 filas/municipio (~102). Atención a erratas («NITRA SRA», «SAN PEDRUCU»). Join nombre→INE 39xxx.
- **La Rioja** — `pdftotext -layout https://ias1.larioja.org/boletin/Bor_Boletin_visor_Servlet?referencia=36153930-1-PDF-571537`. Prosa `Municipio: fecha y fecha`. **Cobertura parcial:** cláusula «Restantes municipios de La Rioja: las dos fiestas tradicionales» deja municipios pequeños sin fechas concretas. Espejo de respaldo (FER): `https://sie.fer.es/recursos/richImg/doc/36010/festivos%20locales%202026%20la%20rioja.pdf`. Join nombre→INE 26xxx.
- **Ceuta** — Municipio único **INE 51001**. Transcribir 2 fechas fijas: **20/03/2026** (Eid al-Fitr) y **13/06/2026** (San Antonio). Fuente: BOCCE 6.549 (`https://www.ceuta.es/ceuta/bocce`).
- **Melilla** — Municipio único **INE 52001**. Transcribir 2 fechas fijas: **08/09/2026** (Virgen de la Victoria) y **17/09/2026** (Día de Melilla). Fuente: `https://bomemelilla.es/bome/BOME-B-2025-6315/articulo/1033`.

### Oleada 4 — Bloqueadas

**Ninguna.** Todas las CCAA tienen fuente localizada y verificada.

---

## 4. Fuentes que requieren seguimiento

Las fuentes 2026 están **todas localizadas y verificadas**; no hay nada estrictamente
bloqueante. Quedan 2 CCAA «difíciles» (PDF) y algunos puntos frágiles a vigilar para
**años futuros** o para **cerrar el calendario definitivo**.

**CCAA difíciles (PDF maquetado) — confirma el PDF vigente si cambia la URL:**

- **Cantabria (ES-CB)** — Si la URL del PDF caduca (el `idAnuBlob` cambia cada año), ir al hub
  estable **`https://dgte.cantabria.es/calendario-laboral`** y abrir el enlace del año. Término
  de búsqueda en `boc.cantabria.es`: **«calendario de fiestas nacionales, autonómicas y locales 2026»**.
- **La Rioja (ES-RI)** — Cobertura incompleta por la cláusula «Restantes municipios». Para
  obtener las fechas de los municipios pequeños no listados, conviene **solicitar a la
  Dirección General de Trabajo y Salud Laboral un listado completo**. Descubrimiento del PDF:
  buscador BOR **`https://web.larioja.org/bor-portada/bor`**, título **«fiestas locales 2026»**,
  o **`https://www.larioja.org/relaciones-laborales/es/calendario-festivos-laborales-2026`**.

**Datasets abiertos 2026 pendientes de publicar (vigilar y avisar cuando salgan):**

- **Castilla-La Mancha (ES-CM)** — el XLSX abierto 2026 aún no existía (404). Vigilar la ficha
  CKAN con slug **`...-para-el-año-2026-de`** en `datosabiertos.castillalamancha.es` o el archivo
  **`CALENDARIO FESTIVOS LOCALES 2026.xlsx`**. Mientras tanto se usa el HTML del DOCM.
- **Extremadura (ES-EX)** — el XLSX abierto 2026 aún no existía (404). Vigilar la ficha
  **`datos.gob.es/.../a11002926-festivos-locales-en-extremadura`** hasta que su distribución
  cambie a `FestivosLocales2026.xlsx` y tomar de ahí la URL (el `docId` cambia cada año).

**Modificaciones a aplicar sobre la base (confirmar que la fuente abierta ya las incorpora):**

- **C. Valenciana** — modificaciones DOGV `2026_1043` (enero) y `2026_6733` (febrero).
- **Catalunya** — Ordre EMT/3/2026 (enero); re-descargar SODA después.
- **Madrid** — corrección BOCM 309 (29/12/2025); el CSV (act. 13/01/2026) debería reflejarla.
- **Navarra** — Resolución 765/2025 (BON nº1, 02/01/2026).
- **Baleares** — correcciones BOIB 139/150/26; el CSV abierto puede no incorporarlas todas.
- **Andalucía** — modificaciones BOJA 247/2025 y 79/2026 (la API ya las incorpora).
- **Extremadura** — DOE nº24 (05/02/2026).

---

## 5. Riesgos y notas

**Falta de código INE (la regla, no la excepción).** Sólo Aragón, Castilla y León, Catalunya
y Galicia traen INE nativo; Madrid lo deriva trivialmente. Las **14 fuentes restantes**
identifican el municipio **por nombre**, lo que obliga a un *join* contra el diccionario INE
con **normalización agresiva**: mayúsculas/minúsculas, tildes, ñ, y sobre todo **artículos
pospuestos** (`ALCÁZARES, LOS` → `Los Alcázares`, `UNIÓN, LA`, `ATZÚBIA, L'`, `ALBUERA (LA)`).
Recomendado: tabla de equivalencias por CCAA + normalización Unicode (NFD, quitar diacríticos).

**URLs que cambian cada año.** Pocas URLs son estables interanualmente:

- *Estables (sólo cambia el año o un filtro):* Catalunya (`b4eh-r8up` fijo, filtrar `any_calendari`),
  Castilla y León (dataset fijo, filtrar fecha), Andalucía (endpoint único multi-año, filtrar `year`),
  Asturias (fichero acumulativo único), País Vasco (`.../calendario_laboral_{AÑO}/...`), Madrid (slug/id CKAN fijos).
- *Frágiles (UUID/id opaco cambia cada año):* Aragón (UUID de recurso), Galicia (id numérico de dataset, sin fórmula),
  Navarra (resource_id por año), Baleares (UUIDs), Cantabria (`idAnuBlob`), La Rioja (`anu-XXXXXX`),
  Murcia (`numero`/`id`), todos los PDF de boletín. → **Resolver dinámicamente** vía la página de
  ficha/CKAN del año, nunca hardcodear el id de descarga.

**Correcciones a lo largo del año.** Casi todas las CCAA publican **resoluciones modificativas**
(enero–abril) tras la base de otoño/invierno. Un pipeline robusto debe (a) re-descargar los
datasets abiertos después de las fechas de modificación conocidas, y (b) para las fuentes PDF,
aplicar explícitamente las modificaciones listadas en §4. El campo `source` por festivo debe
apuntar a la resolución vigente (base o modificación).

**Formatos y encoding heterogéneos.** Vigilar:

- *Delimitadores no estándar:* Andalucía `|`, Asturias CSV `§` (byte 0xA7); el resto `;`.
- *Encodings:* Asturias CSV e Illes Balears y Madrid en **ISO-8859-1/latin-1**; preferir JSON/UTF-8 donde exista (Asturias).
- *Fechas en texto:* Baleares (catalán), Castilla-La Mancha, Extremadura, Murcia, Navarra, La Rioja, C. Valenciana → normalizar mes español/catalán a número.
- *Navarra:* CSV con **BOM**.

**Casos especiales del modelo de datos:**

- **Navarra:** **1 sola fiesta local** por municipio (no 2). El resto del calendario es autonómico.
- **País Vasco:** **1 fiesta local propia** por municipio + **1 común del territorio** histórico
  (San Prudencio 28/04 en Araba; San Ignacio 31/07 en Bizkaia y Gipuzkoa). El dataset abierto
  sólo lista la propia; la común va como fila a nivel territorio.
- **Canarias:** el calendario autonómico/por isla está en **Decreto 61/2025** (documento aparte);
  las **locales municipales** están en la **Orden de 6/08/2025** (BOC 165, disp. 3029) — usar esta.
- **Ceuta y Melilla:** municipio único (51001 / 52001), 2 fechas fijas cada uno, asignar INE a mano.
- **Pedanías/núcleos:** Catalunya, Baleares, Asturias, Navarra y Extremadura desglosan fiestas a
  nivel de pedanía/EATIM/parroquia → un municipio puede aparecer en >2 filas. Decidir si se agregan
  al municipio o se conservan como entidad.
- **Madrid / La Rioja — cobertura incompleta:** Madrid lista 165/179 (resto «no comunicado por el
  Ayuntamiento»); La Rioja remite los municipios pequeños a «sus dos fiestas tradicionales» sin
  fechas. Estos huecos no se resuelven con la fuente; documentarlos como `null`/pendiente.

**Atribución.** Cada fuente exige citar al organismo de origen (ver `FUENTES.md`). Conservar en
`source` la referencia legal (Resolución/Orden/Decreto + boletín) y la URL del dataset/boletín.
Licencias confirmadas CC BY / CC BY-SA donde se indica (Aragón CC BY 4.0, Galicia CC BY-SA 4.0,
Castilla y León CC BY 4.0, Asturias CC BY 4.0, Navarra CC BY 4.0, Baleares CC-BY).
