"""Escritura de colecciones JSON con un elemento por línea (diffs limpios en git)."""
import json
from pathlib import Path


def escribe_coleccion(path, meta: dict, items: list[dict], clave: str) -> None:
    """Escribe `{ ...meta, "<clave>": [ item, ... ] }` con un item por línea."""
    salida = Path(path)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", encoding="utf-8") as f:
        f.write("{\n")
        for k, v in meta.items():
            f.write(f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},\n")
        f.write(f"  {json.dumps(clave)}: [\n")
        ultimo = len(items) - 1
        for i, it in enumerate(items):
            coma = "," if i < ultimo else ""
            f.write("    " + json.dumps(it, ensure_ascii=False) + coma + "\n")
        f.write("  ]\n}\n")
