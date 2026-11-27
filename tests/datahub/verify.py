#!/usr/bin/env python3
"""Contrasta el catálogo entregado con aspectos recuperados por HTTP de DataHub Lite."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def get(url):
    with urlopen(url, timeout=10) as response:
        return json.load(response)


def same(actual, expected, label):
    if actual != expected:
        raise ValueError(f"Difiere {label}")


def save(file, value):
    file.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify(endpoint, folder):
    catalog = json.loads((folder / "catalog.json").read_text())
    mcp = folder / "mcp.json"
    proposals = json.loads(mcp.read_text())
    same(get(endpoint + "/ping"), {"ping": "pong"}, "ping de DataHub Lite")
    ids = set(get(endpoint + "/entities"))
    same(ids, {p["entityUrn"] for p in proposals}, "inventario de entidades")
    urns = {d["id"]: d["urn"] for d in catalog["datasets"]}
    report = {"inicio_utc": now(), "servicio": "DataHub Lite", "version": "1.9.0.1", "almacen": "SQLite",
              "transporte": "HTTP", "url_efimera": endpoint, "propuestas": len(proposals), "entidades": len(ids),
              "mcp_sha256": hashlib.sha256(mcp.read_bytes()).hexdigest(), "datasets": []}
    for d in catalog["datasets"]:
        resource = quote(d["urn"], safe="")
        result = get(endpoint + "/ficha/" + resource)
        props = result["datasetProperties"]
        same((props["description"], props["uri"], props["customProperties"]["archivo_sha256"]),
             (d["description"], d["physical_path"], d["sha256"]), d["id"] + " metadatos")
        schema = result["schemaMetadata"]["fields"]
        same([(f["fieldPath"], f["nativeDataType"], f["description"]) for f in schema],
             [(c["name"], c["type"], f"{c['description']} {c['domain']}") for c in d["columns"]], "campos")
        parents = sorted(x["dataset"] for x in result["upstreamLineage"]["upstreams"])
        same(parents, sorted(urns[x] for x in d["upstream"]), "linaje")
        owner, = result["ownership"]["owners"]
        same(owner["owner"], "urn:li:corpGroup:lago-" + d["owner_id"], "responsable")
        same(result["domains"]["domains"], ["urn:li:domain:lago-" + d["domain_id"]], "dominio")
        same({t["tag"] for t in result["globalTags"]["tags"]}, {"urn:li:tag:lago-" + t for t in d["tags"]}, "etiquetas")
        report["datasets"].append({"id": d["id"], "urn": d["urn"], "campos": len(schema), "upstream": parents,
                                   "responsable": owner["owner"], "respuesta_http": 200})
        if d["id"] == "gold.ventas_diarias":
            save(folder / "ficha-gold.json", result)
            try:
                get(endpoint + "/entities/" + resource + "?aspects=datasetProperties")
                report["detalle_nativo_http"] = 200
            except HTTPError as exc:
                report["detalle_nativo_http"] = exc.code
    result = get(endpoint + "/search?query=ventas_diarias")
    same({hit["id"] for hit in result}, {urns["gold.ventas_diarias"]}, "búsqueda")
    save(folder / "busqueda.json", result)
    report.update(campos=sum(x["campos"] for x in report["datasets"]),
                  relaciones=sum(len(x["upstream"]) for x in report["datasets"]),
                  resultado="Aprobado en DataHub Lite", gms_en_kubernetes="Pendiente de despliegue", fin_utc=now())
    save(folder / "verificacion.json", report)
    print(f"{len(urns)} datasets, {report['campos']} campos y {report['relaciones']} enlaces verificados en DataHub Lite.")
    return urns["gold.ventas_diarias"]


def capture(endpoint, folder, urn):
    from playwright.sync_api import sync_playwright
    routes = {"busqueda": "/search?query=ventas_diarias",
              "linaje-gold": "/ficha/" + quote(urn, safe="") + "?aspects=upstreamLineage"}
    record = {}
    with sync_playwright() as driver:
        browser = driver.chromium.launch(executable_path=shutil.which("chromium") or shutil.which("google-chrome"),
                                         args=["--no-sandbox"])
        for title, path in routes.items():
            page = browser.new_page(viewport={"width": 1250, "height": 760})
            reply = page.goto(endpoint + path, wait_until="domcontentloaded", timeout=16000)
            same(reply.status, 200, "HTTP de la captura " + title)
            body = page.locator("body").inner_text()
            if "ventas_diarias" not in body and "silver.ventas" not in body:
                raise ValueError("Falta el activo esperado en " + path)
            toggle = page.locator('input[type="checkbox"]')
            if toggle.count() and toggle.first.is_visible():
                toggle.first.check()
            page.screenshot(path=str(folder / (title + ".png")))
            record[title] = {"ruta": path, "http": reply.status, "fecha_utc": now(),
                             "origen": "Respuesta JSON viva de DataHub Lite en Chromium"}
            page.close()
        record["chromium"] = browser.version
        browser.close()
    save(folder / "capturas.json", record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--screenshots", action="store_true")
    args = parser.parse_args()
    urn = verify(args.endpoint.rstrip("/"), args.evidence)
    if args.screenshots:
        capture(args.endpoint.rstrip("/"), args.evidence, urn)
