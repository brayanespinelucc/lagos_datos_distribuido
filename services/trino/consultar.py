#!/usr/bin/env python3
"""Ejecuta el catálogo y las consultas P2 por el protocolo HTTP de Trino."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler, Request

ROOT = Path(__file__).resolve().parents[2]


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def write_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


class Coordinator:
    def __init__(self, base):
        self.base = base.rstrip('/')
        target = urlsplit(self.base)
        if target.scheme not in ('http', 'https') or not target.hostname or target.username or target.password:
            raise ValueError('Se requiere una URL del coordinador sin credenciales')
        self.origin = (target.scheme, target.netloc)
        self.client = build_opener(ProxyHandler({}))
        self.headers = {'X-Trino-User': 'evaluacion', 'X-Trino-Source': 'lago-p2'}

    def query(self, sql):
        started = utc()
        request = Request(f'{self.base}/v1/statement', data=sql.encode('utf-8'), headers=self.headers)
        rows = []
        columns = []
        deadline = time.monotonic() + 180
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError('El coordinador no terminó la consulta en 180 segundos')
            with self.client.open(request, timeout=30) as response:
                page = json.load(response)
            if 'error' in page:
                problem = page['error']
                raise RuntimeError(f"{page['id']} · {problem['errorName']} · {problem['message']}")
            columns = page.get('columns') or columns
            rows.extend(page.get('data') or [])
            if not page.get('nextUri'):
                break
            next_url = urlsplit(page['nextUri'])
            if (next_url.scheme, next_url.netloc) != self.origin:
                raise ValueError('El coordinador cambió el origen de nextUri')
            request = Request(page['nextUri'], headers=self.headers)
        stats = page['stats']
        if stats['state'] != 'FINISHED':
            raise RuntimeError(f"{page['id']} terminó en {stats['state']}")
        meta = {'query_id': page['id'], 'inicio_utc': started, 'fin_utc': utc(),
                'estadisticas': {k: stats[k] for k in ('state', 'nodes', 'processedRows', 'processedBytes',
                                                      'cpuTimeMillis', 'elapsedTimeMillis') if k in stats}}
        return columns, rows, meta


def statements(source):
    buffer = ''
    for line in source.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            yield buffer.strip().removesuffix(';')
            buffer = ''
    if buffer.strip():
        raise ValueError('El DDL termina con una sentencia incompleta')


def verify(rows_by_query):
    expected = json.loads((ROOT / 'evidence/moment-02/spark/conciliacion.json').read_text())
    lake = json.loads((ROOT / 'results/lake.json').read_text())
    control, = rows_by_query['01-conciliacion']
    assertions = {
        'entrada': control['recibidas'] == expected['ventas_entrada'],
        'aceptadas': control['aceptadas'] == expected['ventas_aceptadas'],
        'duplicadas': control['duplicadas'] == expected['duplicados'],
        'rechazadas': control['rechazadas'] == expected['rechazados'],
        'unidades_silver_gold_spark': control['unidades'] == control['unidades_gold'] == expected['unidades'],
        'importe_silver_gold_spark': control['importe_cop'] == control['importe_gold_cop'] == expected['ventas_cop'],
        'conteo_concilia_en_trino': control['conteo_concilia'] is True,
        'importes_concilian_en_trino': control['importes_concilian'] is True,
    }
    counts = {r['uri']: r['filas'] for r in rows_by_query['15-origenes']}
    reference = {}
    for table in lake['tables']:
        layer, name = table['layer'], table['name']
        key = name + '.csv' if layer == 'bronze' else name + '/part-00000.parquet'
        reference[f's3://{layer}/{key}'] = table['rows']
    assertions['doce_objetos_minio_y_conteos'] = counts == reference and len(counts) == 12
    causes = {row['motivo']: row['lineas_rechazadas'] for row in rows_by_query['12-rechazos']}
    assertions['causas_rechazo'] = causes == expected['causas']
    receipt = json.loads((ROOT / 'evidence/moment-02/spark/ejecucion.json').read_text())
    return {'criterios': assertions, 'control_trino': control, 'referencia_spark': expected,
            'lote_sha256': receipt['lote_sha256'], 'spark_application_id': receipt['application_id'],
            'objetos_y_filas': counts, 'estado': 'Aprobada' if all(assertions.values()) else 'Fallida'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coordinador', required=True)
    parser.add_argument('--resultados', type=Path, default=ROOT / 'results/sql')
    parser.add_argument('--evidencia', type=Path, default=ROOT / 'evidence/moment-02/trino')
    args = parser.parse_args()
    output, evidence = args.resultados.resolve(), args.evidencia.resolve()
    output.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    service = Coordinator(args.coordinador)
    with service.client.open(service.base + '/v1/info', timeout=10) as response:
        info = json.load(response)
    if info['starting'] or not info['coordinator']:
        raise RuntimeError('El coordinador todavía no está listo')
    catalog = ROOT / 'sql/catalogo.sql'
    index = {'engine': 'Trino', 'version': info['nodeVersion']['version'], 'executed_at': utc(), 'queries': []}
    report = {'inicio_utc': utc(), 'motor': 'Trino', 'version': index['version'],
              'contexto': 'Coordinador del laboratorio y MinIO por S3, catálogo Hive con metastore de archivos.',
              'coordinador': {k: info[k] for k in ('nodeId', 'environment', 'coordinatorId', 'state') if k in info},
              'catalogo_sql_sha256': digest(catalog), 'registro_catalogo': [], 'consultas': []}
    rows_by_query = {}
    try:
        for statement in statements(catalog.read_text()):
            _, _, meta = service.query(statement)
            report['registro_catalogo'].append({'sentencia': statement.splitlines()[0], 'query_id': meta['query_id']})
        for path in sorted((ROOT / 'sql/queries').glob('*.sql')):
            first, sql = path.read_text().split('\n', 1)
            columns, rows, meta = service.query(sql.strip().removesuffix(';'))
            names = [c['name'] for c in columns]
            rows_by_query[path.stem] = [dict(zip(names, row, strict=True)) for row in rows]
            target = output / (path.stem + '.csv')
            tmp = target.with_suffix('.tmp')
            with tmp.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream, lineterminator='\n')
                writer.writerow(names)
                writer.writerows(rows)
            tmp.replace(target)
            entry = {'id': path.stem, 'title': first.removeprefix('-- ').strip(), 'sql': path.relative_to(ROOT).as_posix(),
                     'csv': 'results/sql/' + target.name, 'rows': len(rows), 'query_id': meta['query_id']}
            index['queries'].append(entry)
            report['consultas'].append({**entry, **meta, 'tipos': {c['name']: c['type'] for c in columns},
                                       'sql_sha256': digest(path), 'csv_sha256': digest(target)})
            print(entry['id'], entry['query_id'], len(rows), flush=True)
        report['p2'] = verify(rows_by_query)
        if report['p2']['estado'] != 'Aprobada':
            raise RuntimeError('La conciliación de las consultas no satisface los criterios P2')
        write_json(output / 'index.json', index)
    except Exception as exc:
        report['error'] = str(exc)
        report['fin_utc'] = utc()
        write_json(evidence / 'intento-fallido.json', report)
        raise
    report['fin_utc'] = utc()
    write_json(evidence / 'p2.json', report)


if __name__ == '__main__':
    main()
