#!/usr/bin/env python3
"""Exporta las propuestas de metadatos con el modelo y el FileSink de DataHub."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.ingestion.api.common import PipelineContext, RecordEnvelope
from datahub.ingestion.api.sink import NoopWriteCallback
from datahub.ingestion.sink.file import FileSink
from datahub.metadata import schema_classes as m


def aspects(catalog):
    datasets = catalog["datasets"]
    refs = {d["id"]: d["urn"] for d in datasets}
    for key, label in sorted({(d["domain_id"], d["domain"]) for d in datasets}):
        yield "urn:li:domain:lago-" + key, m.DomainPropertiesClass(name=label)
    for key, label in sorted({(d["owner_id"], d["owner"]) for d in datasets}):
        yield "urn:li:corpGroup:lago-" + key, m.CorpGroupInfoClass(displayName=label, admins=[], members=[], groups=[])
    for tag in sorted({tag for d in datasets for tag in d["tags"]}):
        yield "urn:li:tag:lago-" + tag, m.TagPropertiesClass(name=tag)
    types = {"string": m.StringTypeClass, "int32": m.NumberTypeClass,
             "int64": m.NumberTypeClass, "date32[day]": m.DateTypeClass}
    for d in datasets:
        urn = d["urn"]
        yield urn, m.DatasetPropertiesClass(name=d["id"], description=d["description"], uri=d["physical_path"],
            customProperties={"formato": d["format"], "granularidad": d["grain"], "filas": str(d["rows"]),
                              "archivo_sha256": d["sha256"], "lote_sha256": catalog["batch_sha256"]})
        raw = json.dumps([{c["name"]: c["type"]} for c in d["columns"]], ensure_ascii=False)
        fields = [m.SchemaFieldClass(fieldPath=c["name"], nativeDataType=c["type"], isPartOfKey=c["key"],
                  type=m.SchemaFieldDataTypeClass(type=types[c["type"]]()), description=f"{c['description']} {c['domain']}")
                  for c in d["columns"]]
        yield urn, m.SchemaMetadataClass(schemaName=d["id"], platform="urn:li:dataPlatform:s3", version=0,
            hash=sha256(raw.encode()).hexdigest(), platformSchema=m.OtherSchemaClass(rawSchema=raw), fields=fields)
        yield urn, m.OwnershipClass(owners=[m.OwnerClass(owner="urn:li:corpGroup:lago-" + d["owner_id"], type="BUSINESS_OWNER")])
        yield urn, m.DomainsClass(domains=["urn:li:domain:lago-" + d["domain_id"]])
        yield urn, m.GlobalTagsClass(tags=[m.TagAssociationClass(tag="urn:li:tag:lago-" + t) for t in d["tags"]])
        yield urn, m.UpstreamLineageClass(upstreams=[m.UpstreamClass(dataset=refs[u], type="TRANSFORMED") for u in d["upstream"]])


def export(catalog, output):
    sink = FileSink.create({"filename": str(output)}, PipelineContext(run_id="lago-" + catalog["batch_sha256"][:12]))
    for urn, aspect in aspects(catalog):
        event = MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect)
        if not event.validate():
            raise ValueError(f"Propuesta inválida para {urn} y {event.aspectName}")
        sink.write_record_async(RecordEnvelope(record=event, metadata={}), NoopWriteCallback())
    sink.close()
    print(f"FileSink exportó {len(json.loads(output.read_text()))} MCP.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    export(json.loads(args.catalog.read_text()), args.output)
