#!/usr/bin/env python3
"""Genera un lote comercial sintético reproducible, con cuatro defectos conocidos."""
import argparse
import csv
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory

SIZES = {"pequeno": 120, "mediano": 2400, "grande": 30000}
COLUMNS = {
    "clientes": ("cliente_id", "segmento"),
    "categorias": ("categoria_id", "categoria"),
    "productos": ("producto_id", "categoria_id", "precio_unitario_cop"),
    "sucursales": ("sucursal_id", "region"),
    "transacciones": ("transaccion_id", "fecha", "cliente_id", "sucursal_id"),
    "ventas": ("venta_id", "transaccion_id", "producto_id", "cantidad"),
    "inventario": ("fecha", "sucursal_id", "producto_id", "existencias"),
}


def generate(output, size="pequeno", seed=42):
    rng = random.Random(seed)
    branches = [(f"S{i:02}", r) for i, r in enumerate(("Centro", "Norte", "Occidente"), 1)]
    categories = [(f"C{i:02}", s) for i, s in enumerate(("Alimentos", "Hogar", "Papelería", "Cuidado"), 1)]
    customers = [(f"CL{i:04}", ("Ocasional", "Frecuente", "Empresa")[i % 3]) for i in range(1, 53)]
    products = [(f"P{i:03}", categories[(i - 1) % 4][0], rng.randrange(8, 160) * 500) for i in range(1, 25)]
    tickets, lines = [], []
    for i in range(1, SIZES[size] + 1):
        ticket = f"T{i:07}"
        day = date(2025, 1, 1) + timedelta(days=(i - 1) % 90)
        tickets.append((ticket, day.isoformat(), rng.choice(customers)[0], rng.choice(branches)[0]))
        for _ in range(rng.randint(1, 3)):
            lines.append((f"V{len(lines) + 1:08}", ticket, rng.choice(products)[0], rng.randint(1, 6)))
    clean_lines = len(lines)
    lines.extend([
        lines[0],
        ("ERROR-NULO", tickets[0][0], "", 1),
        ("ERROR-FK", tickets[1][0], "P999", 2),
        ("ERROR-CANTIDAD", tickets[2][0], products[0][0], -1),
    ])
    inventory = [("2025-04-01", b[0], p[0], rng.randint(0, 300)) for b in branches for p in products]
    tables = dict(clientes=customers, categorias=categories, productos=products,
                  sucursales=branches, transacciones=tickets, ventas=lines, inventario=inventory)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"origen": "Sintético", "semilla": seed, "tamano": size, "moneda": "COP",
                "ventas_validas_previstas": clean_lines, "defectos": {"duplicado_exacto": 1,
                "producto_nulo": 1, "producto_desconocido": 1, "cantidad_no_positiva": 1}, "archivos": {}}
    with TemporaryDirectory(dir=output) as tmp:
        staging = Path(tmp)
        for name, rows in tables.items():
            path = staging / f"{name}.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(COLUMNS[name])
                writer.writerows(rows)
            manifest["archivos"][path.name] = {"filas": len(rows), "sha256": sha256(path.read_bytes()).hexdigest()}
        marker = staging / "lote.json"
        marker.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        for name in manifest["archivos"]:
            (staging / name).replace(output / name)
        marker.replace(output / marker.name)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("datasets/source"))
    parser.add_argument("--size", choices=SIZES, default="pequeno")
    parser.add_argument("--seed", type=int, default=42)
    opts = parser.parse_args()
    batch = generate(opts.output, opts.size, opts.seed)
    print(f"{len(batch['archivos'])} CSV · {batch['archivos']['ventas.csv']['filas']} líneas de venta · semilla {opts.seed}")
