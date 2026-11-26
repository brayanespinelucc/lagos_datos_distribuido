#!/usr/bin/env python3
"""Verifica el acta P5 descargada empleando solo la biblioteca estándar."""
import argparse
import datetime as dt
import json
from pathlib import Path


def check(condition, message):
    if not condition:
        raise ValueError(message)


def verify(directory):
    report = json.loads((directory / 'p5.json').read_text())
    check(report['p5'] == 'Aprobada', 'El acta no acredita P5')
    names = ['antes', 'nodo-fuera', 'reprogramado', 'recuperado']
    phases = [report['fases'][name] for name in names]
    times = [dt.datetime.fromisoformat(p['utc']) for p in phases]
    check(all(a < b for a, b in zip(times, times[1:])), 'Cronología de fases inválida')
    before, down, replaced, after = phases
    worker, other = report['worker_objetivo'], report['worker_superviviente']
    for phase in (before, after):
        check(len(phase['nodos']) == 3 and all(n['Ready'] == 'True' for n in phase['nodos'].values()), 'Faltan nodos Ready')
    check(down['nodos'][worker]['Ready'] in ('Unknown', 'False') and
          down['backends']['worker-1']['estado'].startswith('DOWN'), 'Falta la salida de servicio')
    check([a['orden'] for a in report['acciones']] == ['docker stop', 'docker start'] and
          {a['id'] for a in report['acciones']} == {report['id_contenedor_detenido']}, 'Cambió la identidad Docker')
    check(before['nodos'][worker]['uid'] == after['nodos'][worker]['uid'], 'Cambió la identidad del nodo')
    initial = {p['uid']: p['nodo'] for p in before['pods'] if p['Ready'] == 'True' and not p['borrado']}
    current = {p['uid']: p['nodo'] for p in replaced['pods'] if p['Ready'] == 'True' and not p['borrado']}
    check(set(initial.values()) == {worker, other} and len(initial) == 2, 'Distribución inicial incorrecta')
    check(len(current) == 2 and set(current.values()) == {other} and set(current) - set(initial), 'Sin reemplazo demostrable')
    endpoints = {e['targetRef']['uid'] for e in replaced['endpoints'] if e['conditions'].get('ready')}
    check(endpoints == set(current), 'Los endpoints listos no coinciden con los pods sanos')
    for name, phase in zip(names, phases):
        text = (directory / f'kubectl-{name}.txt').read_text()
        check(all(n in text for n in phase['nodos']), f'Inventario kubectl incompleto en {name}')
    samples = [json.loads(line) for line in (directory / 'servicio.jsonl').read_text().splitlines()]
    for name, count in report['muestras_http'].items():
        values = [s for s in samples if s['fase'] == name]
        check(len(values) == count['total'] and sum(s.get('http') == 200 for s in values) == count['http_200'],
              f'Conteo HTTP incongruente durante {name}')
    check(any(s['fase'] == 'detenido' and s.get('http') == 200 and s.get('identidad', '').endswith(' ' + other)
              for s in samples), 'Sin petición atendida por el superviviente durante la caída')
    check(report['kubelet_recuperado'] == 'ok', 'Kubelet sin confirmación posterior')
    print(f"P5 verificada en {report['tecnologia']}. Cuatro fases, tres nodos y {len(samples)} muestras HTTP.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directorio', type=Path)
    verify(parser.parse_args().directorio)
