#!/usr/bin/env python3
"""Apaga un worker del laboratorio efímero identificado por sus etiquetas Docker."""
import argparse
import csv
import datetime as dt
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from urllib import error, request


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run(*args, timeout=25):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{args[0]} {args[1]} (rc {result.returncode}) {result.stderr.strip()}")
    return result.stdout.strip()


def put(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def k(*args):
    return run('kubectl', '--request-timeout=8s', *args)


def items(*args):
    return json.loads(k('get', *args, '-o', 'json'))['items']


def ready(resource):
    return next((c['status'] for c in resource['status'].get('conditions', [])
                 if c['type'] == 'Ready'), 'SinCondicion')


class Lab:
    def __init__(self, args):
        self.args = args
        self.out = args.output
        self.web = f'http://127.0.0.1:{args.http_port}'
        self.stats = f'http://127.0.0.1:{args.stats_port}/estado;csv'
        self.client = request.build_opener(request.ProxyHandler({}))
        self.report = {'inicio_utc': now(), 'tecnologia': args.mode, 'laboratorio': args.lab,
                       'worker_objetivo': args.worker, 'worker_superviviente': args.survivor,
                       'commit_fuente': run('git', 'rev-parse', 'HEAD'),
                       'run_id': os.getenv('GITHUB_RUN_ID'), 'fases': {}, 'acciones': [],
                       'capturas': {}, 'p5': 'Sin ejecutar'}
        self.phase = 'antes'
        self.samples = []
        self.done = threading.Event()

    def save(self):
        put(self.out / 'p5.json', self.report)

    def http(self):
        sample = {'utc': now(), 'fase': self.phase}
        start = time.monotonic()
        try:
            with self.client.open(self.web + '/identidad', timeout=2) as resp:
                sample.update(http=resp.status, identidad=resp.read(512).decode().strip())
        except (OSError, error.URLError) as exc:
            sample.update(http=getattr(exc, 'code', None), error=str(exc))
        sample['ms'] = round((time.monotonic() - start) * 1000)
        return sample

    def monitor(self):
        with (self.out / 'servicio.jsonl').open('w', buffering=1) as stream:
            while not self.done.is_set():
                result = self.http()
                self.samples.append(result)
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
                self.done.wait(1)

    def backends(self):
        with self.client.open(self.stats, timeout=4) as resp:
            contents = resp.read().decode().removeprefix('# ')
        return {r['svname']: {'estado': r['status'], 'sesiones': int(r['stot'])}
                for r in csv.DictReader(io.StringIO(contents))
                if r['pxname'] == 'p5-http' and r['svname'] in ('worker-1', 'worker-2')}

    def snapshot(self):
        nodes = {n['metadata']['name']: {'Ready': ready(n), 'uid': n['metadata']['uid'],
                    'ip': next(a['address'] for a in n['status']['addresses'] if a['type'] == 'InternalIP'),
                    'rol': 'control-plane' if 'node-role.kubernetes.io/control-plane' in n['metadata']['labels'] else n['metadata']['labels'].get('lago.lab/rol'),
                    'kubelet': n['status']['nodeInfo']['kubeletVersion']}
                 for n in items('nodes')}
        pods = [{'nombre': p['metadata']['name'], 'uid': p['metadata']['uid'],
                 'nodo': p['spec'].get('nodeName'), 'ip': p['status'].get('podIP'),
                 'fase': p['status']['phase'], 'Ready': ready(p),
                 'borrado': p['metadata'].get('deletionTimestamp')}
                for p in items('pods', '-n', 'lago-p5', '-l', 'app=testigo')]
        endpoints = [e for entry in items('endpointslices', '-n', 'lago-p5', '-l', 'kubernetes.io/service-name=testigo')
                     for e in entry.get('endpoints', [])]
        deployment = json.loads(k('get', 'deployment/testigo', '-n', 'lago-p5', '-o', 'json'))
        return {'utc': now(), 'nodos': nodes, 'pods': pods, 'endpoints': endpoints, 'backends': self.backends(),
                'replicas_deseadas': deployment['spec']['replicas'],
                'replicas_disponibles': deployment['status'].get('availableReplicas', 0), 'http': self.http()}

    def await_phase(self, name, predicate, seconds):
        deadline = time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            last = self.snapshot()
            if predicate(last):
                self.report['fases'][name] = last
                self.save()
                capture = [k('get', 'nodes', '-o', 'wide'), k('get', 'pods,deploy,svc,endpointslices', '-n', 'lago-p5', '-o', 'wide')]
                (self.out / f'kubectl-{name}.txt').write_text(last['utc'] + '\n' + '\n\n'.join(capture) + '\n')
                return last
            time.sleep(3)
        self.report['fases'][name + '-al-vencer'] = last
        raise RuntimeError(f'{name}: condición ausente tras {seconds} s')

    def capture(self, phase):
        browser = shutil.which('google-chrome') or shutil.which('chromium')
        if not browser:
            self.report['capturas'][phase] = 'Navegador ausente'
            return
        try:
            with tempfile.TemporaryDirectory() as profile:
                dest = self.out / f'servicio-{phase}.png'
                run(browser, '--headless', '--disable-gpu', '--disable-dev-shm-usage',
                    '--no-sandbox', f'--user-data-dir={profile}', '--window-size=1000,440',
                    f'--screenshot={dest.resolve()}', self.web, timeout=18)
                if not dest.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('PNG inválido')
                self.report['capturas'][phase] = dest.name
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            self.report['capturas'][phase] = f'Captura fallida: {str(exc)[:400]}'
        self.save()

    def check_owner(self):
        a = self.args
        tag = 'io.x-k8s.kind.cluster' if a.mode == 'kind' else 'lago.p5'
        ids = run('docker', 'ps', '-q', '--filter', f'label={tag}={a.lab}').splitlines()
        node_map = {}
        for cid in ids:
            data = json.loads(run('docker', 'inspect', cid))[0]
            node_map[data['Config']['Hostname']] = data['Id']
        inspected = json.loads(run('docker', 'inspect', a.container))[0]
        if (not a.lab.startswith('p5-') or inspected['Config']['Labels'].get(tag) != a.lab
                or node_map.get(a.worker) != inspected['Id'] or a.worker == a.survivor):
            raise ValueError('La identidad Docker del worker no corresponde a este laboratorio')
        return node_map, inspected['Id']

    def connectivity(self, state, containers):
        result = {'kubelets': {}, 'tcp_entre_nodos': [], 'http_entre_pods': []}
        for origin, node in state['nodos'].items():
            health = k('get', f'--raw=/api/v1/nodes/{origin}/proxy/healthz')
            if health != 'ok':
                raise RuntimeError(f'Kubelet sin salud verificable en {origin}')
            result['kubelets'][origin] = health
            for peer, destination in state['nodos'].items():
                if peer == origin:
                    continue
                run('docker', 'exec', containers[origin], 'timeout', '5', 'bash', '-ec',
                    'exec 3<>/dev/tcp/"$1"/10250', 'probe', destination['ip'])
                result['tcp_entre_nodos'].append({'origen': origin, 'destino': peer, 'puerto': 10250, 'rc': 0})
        for src in active(state):
            for dst in active(state):
                if src['nodo'] == dst['nodo']:
                    continue
                body = k('exec', '-n', 'lago-p5', src['nombre'], '--', 'wget', '-qO-', '-T', '5',
                         f"http://{dst['ip']}:8080/identidad")
                if body != f"{dst['nombre']} {dst['nodo']}":
                    raise RuntimeError(f"El pod remoto respondió {body!r}")
                result['http_entre_pods'].append({'origen': src['nombre'], 'destino': dst['nombre'], 'respuesta': body})
        probe = active(state)[0]['nombre']
        result['dns_y_service'] = k('exec', '-n', 'lago-p5', probe, '--', 'wget', '-qO-', '-T', '5',
                                   'http://testigo.lago-p5.svc.cluster.local/identidad')
        if result['dns_y_service'] not in [f"{p['nombre']} {p['nodo']}" for p in active(state)]:
            raise RuntimeError('La respuesta por DNS no pertenece al Deployment')
        return result

    def execute(self):
        a = self.args
        containers, cid = self.check_owner()
        self.report['id_contenedor_detenido'] = cid
        self.save()
        monitor = threading.Thread(target=self.monitor, daemon=True)
        monitor.start()
        stopped = False
        try:
            before = self.await_phase('antes', lambda s: healthy(s) and
                {p['nodo'] for p in active(s)} == {a.worker, a.survivor} and
                all_up(s) and serves(s), 100)
            self.report['comunicacion'] = self.connectivity(before, containers)
            stats_before = self.backends()
            probes = [self.http() for _ in range(12)]
            stats_after = self.backends()
            self.report['balanceo'] = {'antes': stats_before, 'despues': stats_after, 'respuestas': probes}
            if not all(x.get('http') == 200 for x in probes) or not all(
                stats_after[b]['sesiones'] > stats_before[b]['sesiones'] for b in ('worker-1', 'worker-2')):
                raise RuntimeError('La serie HTTP no acreditó tráfico en ambos backends')
            self.capture('antes')
            self.phase = 'apagando'
            self.report['acciones'].append({'utc': now(), 'orden': 'docker stop', 'id': cid})
            self.save()
            stopped = True
            run('docker', 'stop', '--time', '10', cid, timeout=30)
            if run('docker', 'inspect', '-f', '{{.State.Running}}', cid) != 'false':
                raise RuntimeError('Docker no confirmó la parada')
            self.report['p5'] = 'Worker detenido'
            self.phase = 'detenido'
            self.await_phase('nodo-fuera', lambda s: s['nodos'][a.worker]['Ready'] in ('False', 'Unknown')
                             and s['backends']['worker-1']['estado'].startswith('DOWN'), 150)
            original = {p['uid'] for p in active(before)}
            self.await_phase('reprogramado', lambda s:
                s['nodos'][a.worker]['Ready'] in ('False', 'Unknown') and
                len(active(s)) == 2 and all(p['nodo'] == a.survivor for p in active(s)) and
                any(p['uid'] not in original for p in active(s)) and s['replicas_disponibles'] == 2 and
                serves(s) and s['http']['identidad'].endswith(' ' + a.survivor) and
                len([e for e in s['endpoints'] if e['conditions'].get('ready') is True and e.get('nodeName') == a.survivor]) == 2, 210)
            self.capture('detenido')
            self.phase = 'recuperando'
            self.report['acciones'].append({'utc': now(), 'orden': 'docker start', 'id': cid})
            run('docker', 'start', cid, timeout=40)
            stopped = False
            after = self.await_phase('recuperado', lambda s: healthy(s) and all_up(s) and serves(s)
                                     and len(active(s)) == 2 and s['replicas_disponibles'] == 2, 200)
            if after['nodos'][a.worker]['uid'] != before['nodos'][a.worker]['uid']:
                raise RuntimeError('El UID del nodo cambió')
            self.report['kubelet_recuperado'] = k('get', f'--raw=/api/v1/nodes/{a.worker}/proxy/healthz')
            if self.report['kubelet_recuperado'] != 'ok':
                raise RuntimeError('Sin respuesta del kubelet recuperado')
            self.phase = 'recuperado'
            self.capture('recuperado')
            self.report['p5'] = 'Aprobada'
        except Exception as exc:
            self.report['error'] = str(exc)
            self.report['p5'] = 'Fallida' if self.report['acciones'] else 'Sin ejecutar'
            raise
        finally:
            if stopped:
                try:
                    run('docker', 'start', cid, timeout=40)
                    self.report['acciones'].append({'utc': now(), 'orden': 'recuperación de contingencia', 'id': cid})
                except Exception as exc:
                    self.report['error_recuperacion'] = str(exc)
            self.done.set()
            monitor.join(timeout=4)
            self.report['muestras_http'] = {p: {'total': len(subset), 'http_200': sum(x.get('http') == 200 for x in subset)}
                for p in dict.fromkeys(x['fase'] for x in self.samples)
                if (subset := [x for x in self.samples if x['fase'] == p])}
            self.report['fin_utc'] = now()
            self.save()
            (self.out / 'eventos.txt').write_text(k('get', 'events', '-n', 'lago-p5', '--sort-by=.metadata.creationTimestamp') + '\n')


def active(state):
    return [p for p in state['pods'] if p['Ready'] == 'True' and not p['borrado']]


def healthy(state):
    nodes = state['nodos'].values()
    return len(nodes) == 3 and all(n['Ready'] == 'True' for n in nodes) and sorted(n['rol'] or '' for n in nodes) == ['control-plane', 'worker', 'worker']


def all_up(state):
    return len(state['backends']) == 2 and all(b['estado'] == 'UP' for b in state['backends'].values())


def serves(state):
    return state['http'].get('http') == 200 and state['http'].get('identidad') in [f"{p['nombre']} {p['nodo']}" for p in active(state)]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--mode', required=True, choices=['rke2', 'kind'])
    for opt in ('lab', 'container', 'worker', 'survivor'):
        parser.add_argument('--' + opt, required=True)
    for opt in ('http-port', 'stats-port'):
        parser.add_argument('--' + opt, required=True, type=int)
    Lab(parser.parse_args()).execute()
