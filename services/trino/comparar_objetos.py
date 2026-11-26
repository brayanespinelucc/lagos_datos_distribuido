"""Coteja los objetos leídos por Trino con las copias del repositorio."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from scripts.lake_pipeline import Storage
from services.trino.consultar import ROOT, write_json


def parquet_signature(source):
    import pyarrow.parquet as pq

    file = pq.ParquetFile(source)
    table = file.read()
    rows = [json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)
            for row in table.to_pylist()]

    def fingerprint(sequence):
        return sha256(('\n'.join(sequence) + '\n').encode()).hexdigest()

    return {'fichero': file.metadata.created_by, 'filas': len(rows), 'claves': table.column_names,
            'tipos': [str(col.type) for col in table.schema], 'multiconjunto_sha256': fingerprint(sorted(rows)),
            'orden_sha256': fingerprint(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    import pyarrow as pa

    storage = Storage()
    if not storage.client:
        raise RuntimeError('Defina las variables privadas de acceso a MinIO para verificar los objetos')
    report = {'inicio_utc': datetime.now(timezone.utc).isoformat(),
              'metodo': 'GET S3. SHA-256 de los bytes devueltos y del fichero versionado de referencia.',
              'metodo_parquet': 'PyArrow decodifica todas las columnas. Se cotejan esquema, número de filas y SHA-256 de las filas JSON ordenadas conservando multiplicidades.',
              'archivos': []}
    for table in json.loads((ROOT / 'results/lake.json').read_text())['tables']:
        layer, name = table['layer'], table['name']
        key = f'{name}.csv' if layer == 'bronze' else f'{name}/part-00000.parquet'
        path = ROOT / 'datasets' / layer / key
        obj = storage.client.get_object(Bucket=layer, Key=key)
        try:
            content = obj['Body'].read()
        finally:
            obj['Body'].close()
        actual = sha256(content).hexdigest()
        expected = sha256(path.read_bytes()).hexdigest()
        record = {'uri': f's3://{layer}/{key}', 'ruta_local': path.relative_to(ROOT).as_posix(),
                  'bytes_s3': len(content), 'sha256_s3': actual, 'sha256_local': expected,
                  'coinciden': actual == expected, 'id_peticion': obj['ResponseMetadata']['RequestId']}
        if layer != 'bronze':
            local = parquet_signature(path)
            remote = parquet_signature(pa.BufferReader(content))
            record.update(parquet_local=local, parquet_s3=remote, contenido_logico_igual=all(
                local[k] == remote[k] for k in ('filas', 'claves', 'tipos', 'multiconjunto_sha256')))
        report['archivos'].append(record)
    report['fin_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    if not all(r.get('contenido_logico_igual', r['coinciden']) for r in report['archivos']):
        raise SystemExit('Un origen de la consulta difiere en contenido de la referencia')


if __name__ == '__main__':
    main()
