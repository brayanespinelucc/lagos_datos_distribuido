#!/usr/bin/env python3
"""Ejecuta una etapa del lago; usa S3 real cuando se indica LAGO_S3_ENV o S3_ENDPOINT."""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.generate_data import COLUMNS

LAYERS = (("silver", "ventas"), ("silver", "inventario"), ("silver", "rechazos"),
          ("gold", "ventas_diarias"), ("gold", "productos"))


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(path):
    with path.open("rb") as stream:
        return sha256(stream.read()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class Storage:
    def __init__(self):
        self.client = None
        settings = {}
        if file := os.getenv("LAGO_S3_ENV"):
            for line in Path(file).read_text().splitlines():
                if line.strip() and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    settings[key] = value.strip().strip("'\"")
        for key in ("S3_ENDPOINT_HOST", "S3_ENDPOINT", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"):
            if key in os.environ:
                settings[key] = os.environ[key]
        endpoint = settings.get("S3_ENDPOINT_HOST") or settings.get("S3_ENDPOINT")
        if endpoint:
            import boto3
            from botocore.config import Config
            url = urlsplit(endpoint)
            if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password:
                raise ValueError("Endpoint S3 inválido")
            self.client = boto3.client("s3", endpoint_url=endpoint,
                                       region_name=settings.get("AWS_DEFAULT_REGION", "us-east-1"),
                                       aws_access_key_id=settings["AWS_ACCESS_KEY_ID"],
                                       aws_secret_access_key=settings["AWS_SECRET_ACCESS_KEY"],
                                       config=Config(signature_version="s3v4",s3={"addressing_style": "path"},
                                                     proxies={}, retries={"max_attempts": 3}))

    def put(self, bucket, key, path):
        if self.client:
            self.client.upload_file(str(path), bucket, key, ExtraArgs={"Metadata": {"sha256": digest(path)}})

    def verify(self, bucket, key, local, target=None):
        if not self.client:
            if target:
                shutil.copyfile(local, target)
            return
        body = self.client.get_object(Bucket=bucket, Key=key)["Body"]
        try:
            content = body.read()
        finally:
            body.close()
        if sha256(content).hexdigest() != digest(local):
            raise ValueError(f"Integridad S3 incorrecta en {bucket}/{key}")
        if target:
            target.write_bytes(content)


def ingest(root, store):
    source, bronze = root / "source", root / "bronze"
    manifest = json.loads((source / "lote.json").read_text())
    if {f"{t}.csv" for t in COLUMNS} != set(manifest["archivos"]):
        raise ValueError("El lote debe contener las siete fuentes del contrato")
    bronze.mkdir(exist_ok=True)
    for name, info in manifest["archivos"].items():
        path = source / name
        if digest(path) != info["sha256"]:
            raise ValueError(f"Fuente alterada: {name}")
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream)
            if next(reader) != list(COLUMNS[path.stem]) or sum(1 for _ in reader) != info["filas"]:
                raise ValueError(f"Esquema o número de filas incorrecto: {name}")
    for name in manifest["archivos"]:
        target = bronze / name
        temp = target.with_suffix(".tmp")
        shutil.copyfile(source / name, temp)
        store.put("bronze", name, temp)
        store.verify("bronze", name, temp)
        temp.replace(target)
    receipt = {"ingesta_utc": now(), "origen": "Generador comercial sintético", "s3": bool(store.client),
               "lote_sha256": digest(source / "lote.json"), "archivos": manifest["archivos"]}
    save(bronze / "ingesta.json", receipt)
    store.put("bronze", "_control/ingesta.json", bronze / "ingesta.json")
    return {"fuentes": len(receipt["archivos"]), "s3": receipt["s3"]}


def process(root, store):
    from services.spark.transform import transform
    bronze = root / "bronze"
    receipt = json.loads((bronze / "ingesta.json").read_text())
    if receipt["lote_sha256"] != digest(root / "source/lote.json"):
        raise ValueError("La fuente cambió después de la ingesta")
    with TemporaryDirectory(prefix="spark-", dir=root / "run") as tmp:
        staging = Path(tmp)
        inputs = staging / "entradas"
        inputs.mkdir()
        for name, info in receipt["archivos"].items():
            if digest(bronze / name) != info["sha256"]:
                raise ValueError(f"Bronze alterado: {name}")
            store.verify("bronze", name, bronze / name, inputs / name)
        os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
        os.environ.setdefault("PYSPARK_SUBMIT_ARGS", "--master local[2] --driver-memory 512m pyspark-shell")
        engine = transform(inputs, staging)
        for layer, name in LAYERS:
            part, = (staging / layer / name).glob("*.parquet")
            target = root / layer / name / "part-00000.parquet"
            target.parent.mkdir(parents=True, exist_ok=True)
            key = name + "/" + target.name
            store.put(layer, key, part)
            store.verify(layer, key, part)
            part.replace(target)
    engine.update(fecha_utc=now(), s3=bool(store.client), lote_sha256=receipt["lote_sha256"])
    save(root / "run/spark.json", engine)
    return engine


def validate(root, store):
    import pyarrow.parquet as pq
    source = root / "source"
    manifest = json.loads((source / "lote.json").read_text())
    bronze = root / "bronze"
    tables = []
    frames = {}
    for layer, name in [("bronze", n) for n in COLUMNS] + list(LAYERS):
        csv_source = layer == "bronze"
        path = bronze / f"{name}.csv" if csv_source else root / layer / name / "part-00000.parquet"
        key = path.relative_to(root / layer).as_posix()
        store.verify(layer, key, path)
        if csv_source:
            rows = read_rows(path)
            if digest(path) != manifest["archivos"][path.name]["sha256"]:
                raise ValueError(f"Bronze no concuerda con la fuente en {name}")
            schema = [{"name": c, "type": "string"} for c in COLUMNS[name]]
        else:
            arrow = pq.read_table(path)
            rows = arrow.to_pylist()
            schema = [{"name": f.name, "type": str(f.type)} for f in arrow.schema]
            frames[layer, name] = rows
        tables.append({"layer": layer, "name": name, "format": "CSV" if csv_source else "Parquet",
                       "rows": len(rows), "columns": schema, "preview": rows[:6],
                       "files": [{"path": "datasets/" + path.relative_to(root).as_posix(),
                                  "bytes": path.stat().st_size, "sha256": digest(path)}]})
    # Oráculo independiente a partir de CSV. Compara claves y todos los agregados con Spark.
    tickets = {r["transaccion_id"]: r for r in read_rows(source / "transacciones.csv")}
    products = {r["producto_id"]: r for r in read_rows(source / "productos.csv")}
    categories = {r["categoria_id"]: r["categoria"] for r in read_rows(source / "categorias.csv")}
    sales = read_rows(source / "ventas.csv")
    by_id, daily, by_product = {}, defaultdict(lambda: [0, 0, set()]), defaultdict(lambda: [0, 0])
    errors = {}
    duplicates = 0
    seen = set()
    for row in sales:
        signature = tuple(row.values())
        if signature in seen:
            duplicates += 1
            continue
        seen.add(signature)
        sku = row["producto_id"]
        reason = None
        if not sku:
            reason = "producto_nulo"
        elif sku not in products:
            reason = "producto_desconocido"
        elif int(row["cantidad"]) <= 0:
            reason = "cantidad_no_positiva"
        if reason:
            errors[row["venta_id"]] = reason
            continue
        ticket = tickets[row["transaccion_id"]]
        product = products[sku]
        amount = int(row["cantidad"]) * int(product["precio_unitario_cop"])
        day = date.fromisoformat(ticket["fecha"])
        qty = int(row["cantidad"])
        by_id[row["venta_id"]] = (row["transaccion_id"], day, ticket["cliente_id"], ticket["sucursal_id"],
                                 sku, categories[product["categoria_id"]], qty, int(product["precio_unitario_cop"]), amount)
        group = daily[day, ticket["sucursal_id"]]
        group[0] += amount
        group[1] += qty
        group[2].add(row["transaccion_id"])
        pgroup = by_product[sku, categories[product["categoria_id"]]]
        pgroup[0] += amount
        pgroup[1] += qty
    silver = frames["silver", "ventas"]
    fields = ("transaccion_id","fecha","cliente_id","sucursal_id","producto_id","categoria",
              "cantidad","precio_unitario_cop","importe_cop")
    actual = {r["venta_id"]: tuple(r[k] for k in fields) for r in silver}
    d_actual = {(r["fecha"],r["sucursal_id"]): (r["ventas_cop"],r["unidades"],r["transacciones"])
                for r in frames["gold", "ventas_diarias"]}
    p_actual = {(r["producto_id"],r["categoria"]): [r["ventas_cop"],r["unidades"]]
                for r in frames["gold", "productos"]}
    stock = {(date.fromisoformat(r["fecha"]),r["sucursal_id"],r["producto_id"],int(r["existencias"]))
             for r in read_rows(source / "inventario.csv")}
    observed_stock = {(r["fecha"],r["sucursal_id"],r["producto_id"],r["existencias"]) for r in frames["silver","inventario"]}
    checks = {"ventas": actual == by_id and len(actual) == len(silver),
              "inventario": observed_stock == stock and len(stock) == len(frames["silver","inventario"]),
              "rechazos": {r["venta_id"]:r["motivo"] for r in frames["silver","rechazos"]} == errors,
              "ventas_diarias": d_actual == {k:(v[0],v[1],len(v[2])) for k,v in daily.items()},
              "productos": p_actual == by_product,
              "conciliacion": len(sales) == len(silver) + duplicates + len(errors)}
    if not all(checks.values()):
        raise ValueError(f"Conciliación fallida: {checks}")
    quality = {"ventas_entrada": len(sales), "ventas_aceptadas": len(silver), "duplicados": duplicates,
               "rechazados": len(errors), "ventas_cop": sum(v[0] for v in by_product.values()),
               "unidades": sum(v[1] for v in by_product.values()), "causas": dict(Counter(errors.values()))}
    result = {"fecha_utc": now(), "lote_sha256": digest(source / "lote.json"), "s3_verificado": bool(store.client),
              "motor": json.loads((root / "run/spark.json").read_text()), "quality": quality, "checks": checks, "tables": tables}
    save(root / "run/quality.json", quality)
    save(root / "run/lake.json", result)
    store.put("gold", "_control/lote-validado.json", root / "run/lake.json")
    return {**quality,"s3_verificado": bool(store.client)}


def catalog(root, store):
    if not (root / "run/lake.json").is_file():
        raise ValueError("Validar el lote antes de publicar sus metadatos")
    out = root / "run/catalog"
    subprocess.run([sys.executable, str(ROOT / "services/datahub/build_catalog.py"),
                    "--data-root", str(root), "--output", str(out)],check=True)
    store.put("gold", "_control/catalog.json", out / "catalog.json")
    return {"catalogo": "run/catalog/catalog.json", "s3": bool(store.client)}


if __name__ == "__main__":
    actions = {"ingest": ingest, "transform": process, "validate": validate, "catalog": catalog}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=actions)
    parser.add_argument("--data-root", type=Path, default=ROOT / "datasets")
    args = parser.parse_args()
    data = args.data_root.resolve()
    (data / "run").mkdir(parents=True, exist_ok=True)
    with (data / "run/.lake.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        print(json.dumps(actions[args.stage](data, Storage()), indent=2, ensure_ascii=False, default=str))
