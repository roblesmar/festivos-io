/**
 * Resolución de nombre de municipio → código INE (para que las herramientas
 * acepten nombres, no solo códigos). Replica la normalización del pipeline:
 * mayúsculas, sin diacríticos, artículo pospuesto al frente, bilingües con barra.
 */

export interface Municipio {
  ine: string;
  name: string;
  province: string;
  province_name: string;
  ccaa_iso: string;
  ccaa_name: string;
}

const ARTICULOS = new Set([
  "EL", "LA", "LOS", "LAS", "L'", "ELS", "LES",
  "O", "A", "OS", "AS", "SA", "SES", "S'", "ES",
]);

function reordenaArticulo(s: string): string {
  const m = s.match(/^(.*?)[,(]\s*([A-Za-zÀ-ÿ']{1,4})\)?\s*$/);
  if (m) {
    const art = m[2].toUpperCase().replace(/[´`]/g, "'");
    if (ARTICULOS.has(art)) return `${m[2]} ${m[1].trim()}`;
  }
  return s;
}

export function normaliza(nombre: string): string {
  let s = reordenaArticulo(nombre.trim()).toUpperCase();
  s = s.normalize("NFD").replace(/[̀-ͯ]/g, "");
  s = s.replace(/[´`’]/g, "'").replace(/-/g, " ").replace(/\s*\/\s*/g, "/");
  return s.split(/\s+/).filter(Boolean).join(" ");
}

function claves(nombre: string): string[] {
  const cs = [normaliza(nombre)];
  if (nombre.includes("/")) {
    for (const parte of nombre.split("/")) {
      const k = normaliza(parte);
      if (k && !cs.includes(k)) cs.push(k);
    }
  }
  return cs;
}

export interface Indice {
  porClave: Map<string, Municipio[]>;
  porIne: Map<string, Municipio>;
}

export async function cargarIndice(dataBase: string): Promise<Indice> {
  const resp = await fetch(`${dataBase}/v1/ref/municipios.json`);
  const data = (await resp.json()) as { municipalities: Municipio[] };
  const porClave = new Map<string, Municipio[]>();
  const porIne = new Map<string, Municipio>();
  for (const m of data.municipalities) {
    porIne.set(m.ine, m);
    for (const clave of claves(m.name)) {
      const lista = porClave.get(clave);
      if (lista) lista.push(m);
      else porClave.set(clave, [m]);
    }
  }
  return { porClave, porIne };
}

export type Resultado =
  | { municipio: Municipio }
  | { candidatos: Municipio[] }
  | null;

export function buscar(idx: Indice, nombre: string, provincia?: string): Resultado {
  const prov = provincia?.trim().toLowerCase();
  for (const clave of claves(nombre)) {
    let cand = idx.porClave.get(clave) ?? [];
    if (prov) {
      cand = cand.filter(
        (m) => m.province === provincia || m.province_name.toLowerCase() === prov,
      );
    }
    const ines = new Set(cand.map((m) => m.ine));
    if (ines.size === 1) return { municipio: cand[0]! };
    if (ines.size > 1) return { candidatos: cand };
  }
  return null;
}
