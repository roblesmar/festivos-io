# festivos-mcp · servidor MCP

Servidor MCP remoto que expone los festivos de España como **herramientas para
agentes** (Claude, etc.). En producción: **https://mcp.festivos.io**
(`/mcp` = Streamable HTTP, `/sse` = SSE).

Es un envoltorio fino sobre el dataset estático (festivos.io) y la API de consulta
(api.festivos.io); resuelve el municipio por nombre para que el agente no tenga que
conocer el código INE.

## Conectar

- **Claude Code:** `claude mcp add --transport sse festivos https://mcp.festivos.io/sse`
- **Claude / otros clientes:** añade un servidor MCP remoto con la URL
  `https://mcp.festivos.io/mcp` (Streamable HTTP) o `https://mcp.festivos.io/sse` (SSE).

## Herramientas

| Herramienta | Qué hace |
|---|---|
| `buscar_municipio(nombre, provincia?)` | Nombre de municipio → código INE (desambigua) |
| `festivos_municipio(municipio, anyo)` | Calendario completo de un municipio en un año |
| `es_festivo(municipio, fecha)` | ¿Es festivo esa fecha? ¿qué se celebra? |
| `dias_habiles(municipio, desde, hasta)` | Días laborables entre dos fechas |
| `puentes(municipio, anyo)` | Puentes (fines de semana largos) del año |
| `proximos_festivos(municipio, desde, n)` | Próximos N festivos |
| `sumar_dias_habiles(municipio, fecha, n)` | Suma/resta N días hábiles a una fecha |
| `siguiente_dia_habil(municipio, fecha)` | Primer día hábil posterior a una fecha |
| `anterior_dia_habil(municipio, fecha)` | Primer día hábil anterior a una fecha |
| `ultimo_dia_habil_mes(municipio, anyo, mes)` | Último día hábil de un mes |
| `calendario_fiscal(anyo, perfil?)` | Calendario fiscal (AEAT): plazos de impuestos |
| `proximas_obligaciones_fiscales(desde, perfil?, n)` | Próximas obligaciones fiscales |
| `calendario_escolar(ccaa, anyo)` | Calendario escolar de una comunidad autónoma |

`municipio` acepta nombre o código INE en todas.

## Desarrollo

```bash
npm install
npx wrangler dev        # local
npx wrangler deploy     # despliegue (cuenta Cloudflare)
```
