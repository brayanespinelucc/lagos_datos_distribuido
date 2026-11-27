"""Sirve las rutas de DataHub Lite sobre la base SQLite que recibió los MCP."""
import os
from fastapi import Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from datahub.lite.lite_server import app, lite
from datahub.lite.lite_util import get_datahub_lite


def catalog():
    config = {"type": "sqlite", "config": {"file": os.environ["LAGO_DATAHUB_DB"], "read_only": True}}
    backend = get_datahub_lite(config)
    try:
        yield backend
    finally:
        backend.close()


app.dependency_overrides[lite] = catalog


@app.get("/ficha/{urn}", response_class=JSONResponse)
def ficha(urn: str, aspects: list[str] | None = Query(None), backend=Depends(catalog)):
    # La anotación de /entities/{id} en 1.9.0.1 rechaza valores escalares legítimos.
    # Esta ruta conserva los datos de la misma lectura y los devuelve como JSON.
    entity = backend.get(urn, aspects=aspects, typed=False)
    if not entity:
        raise HTTPException(status_code=404, detail="Dataset ausente")
    return JSONResponse(entity)
