/**
 * Servidor MCP remoto de festivos.
 *
 * Expone los festivos de España como herramientas para agentes. Es un envoltorio
 * fino: resuelve el municipio por nombre (índice INE) y delega los cálculos en la
 * API pública (api.festivos.io) y el dataset estático (festivos.io).
 */
import { McpAgent } from "agents/mcp";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { buscar, cargarIndice, type Indice, type Municipio } from "./municipios.js";

interface Env {
  API_BASE: string;
  DATA_BASE: string;
  MCP_OBJECT: DurableObjectNamespace;
}

type Contenido = { content: { type: "text"; text: string }[]; isError?: boolean };

function texto(obj: unknown): Contenido {
  return { content: [{ type: "text", text: JSON.stringify(obj, null, 2) }] };
}
function fallo(mensaje: string): Contenido {
  return { content: [{ type: "text", text: mensaje }], isError: true };
}

const CCAA_ISO: Record<string, string> = {
  "andalucia": "ES-AN", "aragon": "ES-AR", "asturias": "ES-AS",
  "baleares": "ES-IB", "illes balears": "ES-IB", "islas baleares": "ES-IB",
  "canarias": "ES-CN", "cantabria": "ES-CB", "castilla y leon": "ES-CL",
  "castilla-la mancha": "ES-CM", "castilla la mancha": "ES-CM",
  "cataluna": "ES-CT", "catalunya": "ES-CT", "ceuta": "ES-CE",
  "comunidad valenciana": "ES-VC", "comunitat valenciana": "ES-VC", "valencia": "ES-VC",
  "extremadura": "ES-EX", "galicia": "ES-GA", "la rioja": "ES-RI", "rioja": "ES-RI",
  "madrid": "ES-MD", "melilla": "ES-ML", "murcia": "ES-MC",
  "navarra": "ES-NC", "pais vasco": "ES-PV", "euskadi": "ES-PV", "euskal herria": "ES-PV",
};

function resolverCCAA(s: string): string | null {
  const t = s.trim();
  if (/^ES-[A-Za-z]{2}$/.test(t)) return t.toUpperCase();
  const norm = t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  return CCAA_ISO[norm] ?? null;
}

export class FestivosMCP extends McpAgent<Env> {
  server = new McpServer({
    name: "festivos",
    version: "0.1.0",
  });

  private indice?: Indice;

  private async idx(): Promise<Indice> {
    if (!this.indice) this.indice = await cargarIndice(this.env.DATA_BASE);
    return this.indice;
  }

  /** Resuelve un municipio (nombre o INE) a su código INE, o devuelve un mensaje. */
  private async resolver(
    municipio: string,
    provincia?: string,
  ): Promise<{ ine: string; m?: Municipio } | { error: string }> {
    if (/^\d{5}$/.test(municipio)) {
      return { ine: municipio, m: (await this.idx()).porIne.get(municipio) };
    }
    const r = buscar(await this.idx(), municipio, provincia);
    if (!r) {
      return { error: `No se encontró "${municipio}". Usa buscar_municipio para localizarlo.` };
    }
    if ("candidatos" in r) {
      const lista = r.candidatos
        .map((m) => `${m.name} (${m.province_name}) = ${m.ine}`)
        .join("; ");
      return { error: `"${municipio}" es ambiguo; indica la provincia. Candidatos: ${lista}` };
    }
    return { ine: r.municipio.ine, m: r.municipio };
  }

  private async api(path: string): Promise<unknown> {
    const r = await fetch(`${this.env.API_BASE}${path}`);
    return r.json();
  }

  async init(): Promise<void> {
    this.server.tool(
      "buscar_municipio",
      "Resuelve el nombre de un municipio español a su código INE de 5 dígitos. Útil antes que el resto de herramientas (que aceptan nombre o INE). Devuelve candidatos si el nombre es ambiguo.",
      {
        nombre: z.string().describe("Nombre del municipio, p. ej. 'Tarragona'"),
        provincia: z.string().optional().describe("Provincia para desambiguar (nombre o código de 2 dígitos)"),
      },
      async ({ nombre, provincia }) => {
        const r = buscar(await this.idx(), nombre, provincia);
        if (!r) return fallo(`Sin resultados para "${nombre}".`);
        if ("candidatos" in r) {
          return texto({
            ambiguo: true,
            candidatos: r.candidatos.map((m) => ({
              ine: m.ine, name: m.name, provincia: m.province_name, ccaa: m.ccaa_name,
            })),
          });
        }
        const m = r.municipio;
        return texto({ ine: m.ine, name: m.name, provincia: m.province_name, ccaa: m.ccaa_name });
      },
    );

    this.server.tool(
      "festivos_municipio",
      "Devuelve todos los festivos (nacionales, autonómicos y locales) de un municipio en un año, con sus nombres.",
      {
        municipio: z.string().describe("Nombre o código INE"),
        anyo: z.number().int().describe("Año, p. ej. 2026"),
        provincia: z.string().optional(),
      },
      async ({ municipio, anyo, provincia }) => {
        const r = await this.resolver(municipio, provincia);
        if ("error" in r) return fallo(r.error);
        const resp = await fetch(`${this.env.DATA_BASE}/v1/${anyo}/municipio/${r.ine}.json`);
        if (!resp.ok) return fallo(`No hay datos para ${r.ine} en ${anyo}.`);
        const d = (await resp.json()) as {
          municipality: { name: string }; year: number;
          holidays: { date: string; name: { es: string }; level: string }[];
        };
        return texto({
          municipio: d.municipality.name,
          ine: r.ine,
          year: d.year,
          festivos: d.holidays.map((h) => ({ date: h.date, name: h.name.es, level: h.level })),
        });
      },
    );

    this.server.tool(
      "es_festivo",
      "Indica si una fecha es festivo en un municipio y qué se celebra.",
      {
        municipio: z.string(),
        fecha: z.string().describe("Fecha ISO YYYY-MM-DD"),
        provincia: z.string().optional(),
      },
      async ({ municipio, fecha, provincia }) => {
        const r = await this.resolver(municipio, provincia);
        if ("error" in r) return fallo(r.error);
        return texto(await this.api(`/v1/is-holiday?date=${fecha}&municipio=${r.ine}`));
      },
    );

    this.server.tool(
      "dias_habiles",
      "Cuenta los días hábiles (laborables) entre dos fechas en un municipio, descontando fines de semana y sus festivos.",
      {
        municipio: z.string(),
        desde: z.string().describe("Fecha ISO YYYY-MM-DD"),
        hasta: z.string().describe("Fecha ISO YYYY-MM-DD"),
        provincia: z.string().optional(),
      },
      async ({ municipio, desde, hasta, provincia }) => {
        const r = await this.resolver(municipio, provincia);
        if ("error" in r) return fallo(r.error);
        return texto(await this.api(`/v1/dias-habiles?municipio=${r.ine}&from=${desde}&to=${hasta}`));
      },
    );

    this.server.tool(
      "sumar_dias_habiles",
      "Suma (o resta, con n negativo) N días hábiles a una fecha en un municipio, saltando fines de semana y festivos.",
      {
        municipio: z.string(),
        fecha: z.string().describe("Fecha ISO YYYY-MM-DD"),
        n: z.number().int().describe("Días hábiles a sumar (negativo = restar)"),
        provincia: z.string().optional(),
      },
      async ({ municipio, fecha, n, provincia }) => {
        const r = await this.resolver(municipio, provincia);
        if ("error" in r) return fallo(r.error);
        return texto(await this.api(`/v1/dias-habiles/sumar?municipio=${r.ine}&date=${fecha}&n=${n}`));
      },
    );

    this.server.tool(
      "siguiente_dia_habil",
      "Primer día hábil posterior a una fecha en un municipio (salta findes y festivos).",
      {
        municipio: z.string(),
        fecha: z.string().describe("Fecha ISO YYYY-MM-DD"),
        provincia: z.string().optional(),
      },
      async ({ municipio, fecha, provincia }) => {
        const r = await this.resolver(municipio, provincia);
        if ("error" in r) return fallo(r.error);
        return texto(await this.api(`/v1/dias-habiles/siguiente?municipio=${r.ine}&date=${fecha}`));
      },
    );

    this.server.tool(
      "anterior_dia_habil",
      "Primer día hábil anterior a una fecha en un municipio (salta findes y festivos).",
      {
        municipio: z.string(),
        fecha: z.string().describe("Fecha ISO YYYY-MM-DD"),
        provincia: z.string().optional(),
      },
      async ({ municipio, fecha, provincia }) => {
        const r = await this.resolver(municipio, provincia);
        if ("error" in r) return fallo(r.error);
        return texto(await this.api(`/v1/dias-habiles/anterior?municipio=${r.ine}&date=${fecha}`));
      },
    );

    this.server.tool(
      "ultimo_dia_habil_mes",
      "Último día hábil de un mes concreto en un municipio (útil para nóminas y cierres).",
      {
        municipio: z.string(),
        anyo: z.number().int(),
        mes: z.number().int().describe("Mes 1-12"),
        provincia: z.string().optional(),
      },
      async ({ municipio, anyo, mes, provincia }) => {
        const r = await this.resolver(municipio, provincia);
        if ("error" in r) return fallo(r.error);
        return texto(await this.api(`/v1/dias-habiles/ultimo-mes?municipio=${r.ine}&year=${anyo}&month=${mes}`));
      },
    );

    this.server.tool(
      "puentes",
      "Detecta los puentes (fines de semana largos) de un municipio en un año.",
      {
        municipio: z.string(),
        anyo: z.number().int(),
        provincia: z.string().optional(),
      },
      async ({ municipio, anyo, provincia }) => {
        const r = await this.resolver(municipio, provincia);
        if ("error" in r) return fallo(r.error);
        return texto(await this.api(`/v1/puentes?municipio=${r.ine}&year=${anyo}`));
      },
    );

    this.server.tool(
      "proximos_festivos",
      "Próximos festivos de un municipio a partir de una fecha.",
      {
        municipio: z.string(),
        desde: z.string().describe("Fecha ISO desde la que buscar"),
        n: z.number().int().default(3).describe("Cuántos devolver"),
        provincia: z.string().optional(),
      },
      async ({ municipio, desde, n, provincia }) => {
        const r = await this.resolver(municipio, provincia);
        if ("error" in r) return fallo(r.error);
        const anyo = Number(desde.slice(0, 4));
        const out: { date: string; name: string; level: string }[] = [];
        for (const y of [anyo, anyo + 1]) {
          const resp = await fetch(`${this.env.DATA_BASE}/v1/${y}/municipio/${r.ine}.json`);
          if (!resp.ok) continue;
          const d = (await resp.json()) as {
            holidays: { date: string; name: { es: string }; level: string }[];
          };
          for (const h of d.holidays) {
            if (h.date >= desde) out.push({ date: h.date, name: h.name.es, level: h.level });
          }
          if (out.length >= n) break;
        }
        out.sort((a, b) => a.date.localeCompare(b.date));
        return texto({ proximos: out.slice(0, n) });
      },
    );

    this.server.tool(
      "calendario_fiscal",
      "Calendario fiscal de España (AEAT): plazos de presentación de impuestos de un año, opcionalmente filtrados por perfil.",
      {
        anyo: z.number().int().default(2026),
        perfil: z.enum(["particular", "autonomo", "empresa"]).optional()
          .describe("particular (persona física), autonomo o empresa"),
      },
      async ({ anyo, perfil }) => {
        const path = perfil ? `/v1/${anyo}/fiscal/${perfil}.json` : `/v1/${anyo}/fiscal.json`;
        const r = await fetch(`${this.env.DATA_BASE}${path}`);
        if (!r.ok) return fallo(`No hay calendario fiscal para ${anyo}.`);
        const d = (await r.json()) as {
          year: number; profile?: string; count: number;
          deadlines: { date: string; figure: string; models: string[]; name: { es: string } }[];
        };
        return texto({
          year: d.year, profile: d.profile ?? "todos", count: d.count,
          deadlines: d.deadlines.map((x) => ({ date: x.date, figure: x.figure, models: x.models, name: x.name.es })),
        });
      },
    );

    this.server.tool(
      "proximas_obligaciones_fiscales",
      "Próximas obligaciones fiscales (AEAT) a partir de una fecha, opcionalmente por perfil.",
      {
        desde: z.string().describe("Fecha ISO YYYY-MM-DD"),
        perfil: z.enum(["particular", "autonomo", "empresa"]).optional(),
        n: z.number().int().default(5),
      },
      async ({ desde, perfil, n }) => {
        const anyo = Number(desde.slice(0, 4));
        const path = perfil ? `/v1/${anyo}/fiscal/${perfil}.json` : `/v1/${anyo}/fiscal.json`;
        const r = await fetch(`${this.env.DATA_BASE}${path}`);
        if (!r.ok) return fallo(`No hay calendario fiscal para ${anyo}.`);
        const d = (await r.json()) as {
          deadlines: { date: string; figure: string; models: string[]; name: { es: string } }[];
        };
        const prox = d.deadlines
          .filter((x) => x.date >= desde).slice(0, n)
          .map((x) => ({ date: x.date, figure: x.figure, models: x.models, name: x.name.es }));
        return texto({ desde, perfil: perfil ?? "todos", proximas: prox });
      },
    );

    this.server.tool(
      "calendario_escolar",
      "Calendario escolar de una comunidad autónoma: inicio/fin de curso, vacaciones y días no lectivos.",
      {
        ccaa: z.string().describe("Nombre o código ES-XX de la comunidad (p. ej. 'Madrid' o 'ES-MD')"),
        anyo: z.number().int().default(2026).describe("Año natural de inicio del curso (2026 = curso 2026-2027)"),
      },
      async ({ ccaa, anyo }) => {
        const iso = resolverCCAA(ccaa);
        if (!iso) return fallo(`No reconozco la comunidad "${ccaa}". Usa el nombre o el código ES-XX.`);
        const r = await fetch(`${this.env.DATA_BASE}/v1/${anyo}/escolar/${iso}.json`);
        if (!r.ok) return fallo(`No hay calendario escolar de ${iso} para el curso ${anyo}-${anyo + 1}.`);
        return texto(await r.json());
      },
    );
  }
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const { pathname } = new URL(request.url);
    if (pathname === "/sse" || pathname === "/sse/message") {
      return FestivosMCP.serveSSE("/sse").fetch(request, env, ctx);
    }
    if (pathname === "/mcp") {
      return FestivosMCP.serve("/mcp").fetch(request, env, ctx);
    }
    return new Response(
      [
        "festivos · servidor MCP",
        "",
        "Endpoints: /mcp (Streamable HTTP) y /sse (SSE).",
        "Herramientas: buscar_municipio, festivos_municipio, es_festivo, proximos_festivos, " +
          "dias_habiles, sumar_dias_habiles, siguiente_dia_habil, anterior_dia_habil, ultimo_dia_habil_mes, " +
          "puentes, calendario_fiscal, proximas_obligaciones_fiscales, calendario_escolar.",
        "Datos: https://festivos.io · API: https://api.festivos.io",
      ].join("\n"),
      // CORS abierto para permitir sondas de disponibilidad desde el navegador.
      { headers: { "content-type": "text/plain; charset=utf-8", "access-control-allow-origin": "*" } },
    );
  },
};
