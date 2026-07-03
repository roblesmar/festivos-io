import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const base = process.argv[2] || "https://mcp.festivos.io";
const transport = new StreamableHTTPClientTransport(new URL(base + "/mcp"));
const client = new Client({ name: "test-festivos", version: "1.0.0" });
await client.connect(transport);

const { tools } = await client.listTools();
console.log("HERRAMIENTAS:", tools.map((t) => t.name).join(", "));

async function llama(name, args) {
  const r = await client.callTool({ name, arguments: args });
  console.log(`\n${name}(${JSON.stringify(args)}) →\n${r.content[0].text}`);
}

await llama("buscar_municipio", { nombre: "Tarragona" });
await llama("es_festivo", { municipio: "Tarragona", fecha: "2026-09-23" });
await llama("proximos_festivos", { municipio: "Madrid", desde: "2026-05-01", n: 2 });
await llama("dias_habiles", { municipio: "Barcelona", desde: "2026-12-01", hasta: "2026-12-31" });

await client.close();
