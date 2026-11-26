#!/usr/bin/env python3
"""Construye el catálogo portátil a partir del lote validado por lake_pipeline.py."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

DOMAINS = {
    "comercial": "Ventas y clientes",
    "abastecimiento": "Abastecimiento",
    "calidad": "Calidad de datos",
    "analitica": "Analítica comercial",
}
OWNERS = {
    "operaciones": "Operaciones comerciales",
    "inventarios": "Control de inventarios",
    "calidad": "Equipo de calidad de datos",
    "analitica": "Equipo de analítica comercial",
}
# Descripción, grano, dominio, grupo propietario y clave lógica del negocio.
TABLES = {
    "bronze.clientes": ("Clientes sintéticos y su segmento comercial.", "Cliente", "comercial", "operaciones", ["cliente_id"]),
    "bronze.categorias": ("Catálogo de las categorías de mercancías.", "Categoría", "abastecimiento", "inventarios", ["categoria_id"]),
    "bronze.productos": ("Maestro de productos, categoría y precio unitario de lista.", "Producto", "abastecimiento", "inventarios", ["producto_id"]),
    "bronze.sucursales": ("Sucursales de la cadena y su región comercial.", "Sucursal", "comercial", "operaciones", ["sucursal_id"]),
    "bronze.transacciones": ("Cabeceras de transacciones con fecha, cliente y sucursal.", "Tiquete", "comercial", "operaciones", ["transaccion_id"]),
    "bronze.ventas": ("Líneas de venta originales, con las anomalías deliberadas del lote de prueba.", "Línea recibida", "comercial", "operaciones", ["venta_id"]),
    "bronze.inventario": ("Existencias originales por sucursal, producto y fecha de corte.", "Producto en una sucursal y fecha", "abastecimiento", "inventarios", ["fecha", "sucursal_id", "producto_id"]),
    "silver.ventas": ("Líneas únicas aceptadas después de comprobar claves, cantidades, precios y dimensiones.", "Línea aceptada", "comercial", "calidad", ["venta_id"]),
    "silver.inventario": ("Existencias con fechas y cantidades tipadas.", "Producto en una sucursal y fecha", "abastecimiento", "inventarios", ["fecha", "sucursal_id", "producto_id"]),
    "silver.rechazos": ("Líneas excluidas de los indicadores y motivo de su rechazo.", "Línea rechazada", "calidad", "calidad", []),
    "gold.ventas_diarias": ("Ingresos en COP, unidades y tiquetes distintos por fecha y sucursal.", "Sucursal y día", "analitica", "analitica", ["fecha", "sucursal_id"]),
    "gold.productos": ("Ingresos y unidades vendidas por producto y categoría.", "Producto y categoría", "analitica", "analitica", ["producto_id", "categoria"]),
}
SALES_INPUTS = ["bronze.ventas", "bronze.transacciones", "bronze.productos", "bronze.categorias", "bronze.clientes", "bronze.sucursales"]
PARENTS = {
    "silver.ventas": SALES_INPUTS,
    "silver.rechazos": SALES_INPUTS,
    "silver.inventario": ["bronze.inventario"],
    "gold.ventas_diarias": ["silver.ventas"],
    "gold.productos": ["silver.ventas"],
}
COLUMNS = {
    "cliente_id": ("Identificador sintético del cliente en el maestro comercial.", "Texto alfanumérico, prefijo CL en el generador."),
    "segmento": ("Segmento comercial asignado al cliente.", "Ocasional, Frecuente o Empresa."),
    "categoria_id": ("Identificador estable de una categoría de productos.", "Código de la dimensión categorias."),
    "categoria": ("Nombre comercial de la categoría.", "Alimentos, Hogar, Papelería o Cuidado."),
    "producto_id": ("Identificador del producto o SKU utilizado en el maestro, la venta o las existencias.", "Código del maestro productos. En Bronze puede faltar o no existir."),
    "precio_unitario_cop": ("Precio de una unidad del producto, expresado en pesos colombianos.", "Importe entero en COP, mayor o igual a cero en líneas aceptadas."),
    "sucursal_id": ("Identificador de la tienda donde se registró la operación.", "Código de la dimensión sucursales."),
    "region": ("Región comercial de la sucursal.", "Centro, Norte u Occidente."),
    "transaccion_id": ("Identificador del tiquete que agrupa una o más líneas de venta.", "Código de la cabecera transacciones."),
    "venta_id": ("Identificador de una línea individual de venta.", "Clave lógica en Bronze, donde puede repetirse. Única en Silver ventas."),
    "fecha": ("Fecha de la transacción o del corte de existencias, según el conjunto.", "Fecha civil ISO 8601. Gold diario agrupa por esta fecha."),
    "cantidad": ("Número de unidades del producto en una línea de venta.", "Entero estrictamente positivo para las líneas aceptadas."),
    "existencias": ("Unidades de un producto disponibles en una sucursal al cierre del inventario.", "Conteo entero sintético."),
    "importe_cop": ("Importe de la línea en pesos colombianos.", "cantidad multiplicada por precio_unitario_cop."),
    "motivo": ("Primera regla incumplida durante la clasificación de la venta.", "id_nulo, id_con_conflicto, producto_nulo, producto_desconocido, cantidad_no_positiva, transaccion_invalida, dimension_incompleta o precio_invalido."),
    "ventas_cop": ("Suma de los importes de líneas válidas del grupo, en pesos colombianos.", "Suma de importe_cop."),
    "unidades": ("Suma de las cantidades de las líneas válidas del grupo.", "Conteo entero de unidades vendidas."),
    "transacciones": ("Cantidad de tiquetes distintos incluidos en el grupo.", "COUNT DISTINCT de transaccion_id por día y sucursal."),
}
GLOSSARY = [
    {"term": "Tiquete", "definition": "Transacción que reúne una o más líneas de venta."},
    {"term": "SKU", "definition": "Unidad identificable del catálogo de productos. Su código es producto_id."},
    {"term": "Venta aceptada", "definition": "Línea única con dimensiones válidas, cantidad positiva y precio válido."},
    {"term": "COP", "definition": "Peso colombiano, unidad monetaria de los precios e importes del lote."},
]


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def build_catalog(data_root, output):
    source = json.loads((data_root / "run/lake.json").read_text())
    if not source["checks"] or not all(source["checks"].values()):
        raise ValueError("El lote no superó la conciliación")
    batch = hashlib.sha256((data_root / "source/lote.json").read_bytes()).hexdigest()
    if batch != source["lote_sha256"]:
        raise ValueError("El acta de conciliación corresponde a otro lote")
    datasets = []
    for asset in source["tables"]:
        layer, name = asset["layer"], asset["name"]
        key = f"{layer}.{name}"
        description, grain, domain, owner, keys = TABLES[key]
        file, = asset["files"]
        path = Path(file["path"])
        if path.is_absolute() or ".." in path.parts or path.parts[:2] != ("datasets", layer):
            raise ValueError(f"Ruta de inventario inesperada en {key}")
        local = data_root.joinpath(*path.parts[1:])
        if hashlib.sha256(local.read_bytes()).hexdigest() != file["sha256"]:
            raise ValueError(f"La huella del archivo de {key} difiere del acta")
        columns = []
        for column in asset["columns"]:
            label = column["name"]
            definition, rule = COLUMNS[label]
            columns.append({**column, "description": definition, "domain": rule, "key": label in keys})
        classification = "Restringido" if key in {"bronze.clientes", "bronze.transacciones", "silver.ventas", "silver.rechazos"} else "Interno"
        datasets.append({
            "id": key, "urn": f"urn:li:dataset:(urn:li:dataPlatform:s3,lago.{key},DEV)",
            "name": name, "layer": layer, "format": asset["format"], "description": description,
            "grain": grain, "business_keys": keys, "classification": classification,
            "domain_id": domain, "domain": DOMAINS[domain], "owner_id": owner, "owner": OWNERS[owner],
            "tags": [layer, "sintetico", classification.lower()], "rows": asset["rows"],
            "physical_path": "s3://" + "/".join(path.parts[1:]), "repository_file": str(path),
            "sha256": file["sha256"], "upstream": PARENTS.get(key, []), "columns": columns,
        })
    if len(datasets) != len(TABLES) or {d["id"] for d in datasets} != set(TABLES):
        raise ValueError("Conjuntos ausentes o duplicados en el acta de conciliación")
    edges = [{"source": upstream, "target": d["id"],
              "provenance": "Vista lógica Spark validas, compartida por Silver y Gold" if d["layer"] == "gold" else "SQL de services/spark/transform.py"}
             for d in datasets for upstream in d["upstream"]]
    output.mkdir(parents=True, exist_ok=True)
    catalog = {"batch_sha256": batch, "validated_at": source["fecha_utc"], "s3_verified_by_pipeline": source["s3_verificado"],
               "platform": "MinIO (S3)", "environment": "DEV", "datasets": datasets, "edges": edges, "glossary": GLOSSARY}
    write_json(output / "catalog.json", catalog)
    with (output / "diccionario.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["dataset", "campo", "tipo_fisico", "parte_de_clave", "definicion", "dominio_o_regla"])
        for dataset in datasets:
            for col in dataset["columns"]:
                writer.writerow([dataset["id"], col["name"], col["type"], "sí" if col["key"] else "no", col["description"], col["domain"]])
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = build_catalog(args.data_root, args.output)
    print(f"{len(catalog['datasets'])} conjuntos, {len(catalog['edges'])} relaciones y "
          f"{sum(len(d['columns']) for d in catalog['datasets'])} campos documentados.")
