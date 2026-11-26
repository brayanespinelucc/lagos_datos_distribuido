"""Comprueba el frontend API de HAProxy con un kube-apiserver y un etcd reales."""
from contextlib import ExitStack
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request


def validate(binary, directory, temporary, kubeconfig, environment, kubectl, secure, ports, root):
    directory.mkdir(parents=True, exist_ok=True)
    frontend, browser_port = ports
    source = (root / 'infrastructure/load-balancers/kubernetes/haproxy.cfg').read_text()
    listen = source.split('listen api\n', 1)[1].split('listen supervisor', 1)[0]
    listen = listen.replace('10.42.10.11:6443', f'127.0.0.1:{frontend}').replace('10.42.10.31:6443', f'127.0.0.1:{secure}')
    conf = temporary / 'haproxy.cfg'
    conf.write_text('global\n    log stdout format raw local0\ndefaults\n    mode tcp\n    log global\n    option tcplog\n    timeout connect 3s\n    timeout client 10s\n    timeout server 10s\nlisten api\n' + listen)
    route = f'https://127.0.0.1:{frontend}'
    kubeconfig['clusters'][0]['cluster']['server'] = route
    Path(environment['KUBECONFIG']).write_text(json.dumps(kubeconfig))
    transcript = []

    def k(*args, output=True):
        p = subprocess.run([kubectl, '--request-timeout=4s', *args], env=environment,
                           text=True, capture_output=True, timeout=10, check=True)
        if output:
            transcript.append('$ kubectl ' + ' '.join(args) + '\n' + (p.stdout + p.stderr).strip())
        return p.stdout

    def terminate(p):
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()

    utc = lambda: dt.datetime.now(dt.timezone.utc).isoformat()
    report = {'inicio_utc': utc(), 'ruta': ['kubectl', 'HAProxy (TCP)', 'kube-apiserver (TLS)', 'etcd'],
              'frontend': route, 'backend': f'127.0.0.1:{secure}', 'modo': 'procesos efímeros en loopback',
              'p5': 'Sin ejecutar en este entorno', 'verificacion_tls': 'CA del laboratorio y SAN 127.0.0.1'}
    with ExitStack() as resources:
        logfile = resources.enter_context((directory / 'haproxy-api.log').open('w'))
        proxy = subprocess.Popen([binary, '-db', '-f', conf], stdout=logfile, stderr=subprocess.STDOUT)
        resources.callback(terminate, proxy)
        for _ in range(35):
            try:
                if k('get', '--raw=/readyz', output=False) == 'ok':
                    break
            except subprocess.CalledProcessError:
                pass
            time.sleep(.2)
        else:
            raise RuntimeError('El frontend no estableció una sesión TLS con el API')
        report['haproxy'] = subprocess.check_output([binary, '-v'], text=True).splitlines()[0]
        report['readyz'] = k('get', '--raw=/readyz?verbose').splitlines()
        report['version_servidor'] = json.loads(k('version', '-o', 'json', output=False))['serverVersion']['gitVersion']
        report['aplicar'] = k('apply', '--server-side', '--validate=strict', '-f', 'tests/kubernetes/aplicacion-p5.yaml').splitlines()
        report['nodos_observados'] = len(json.loads(k('get', 'nodes', '-o', 'json', output=False))['items'])
        report['pods_observados'] = len(json.loads(k('-n', 'lago-p5', 'get', 'pods', '-o', 'json', output=False))['items'])
        for args in [('get', 'nodes', '-o', 'wide'), ('-n', 'lago-p5', 'get', 'deploy,svc,pods', '-o', 'wide')]:
            k(*args)
        (directory / 'kubectl-api.txt').write_text(report['inicio_utc'] + '\n\n' + '\n\n'.join(transcript) + '\n')
        # Chromium obtiene /readyz en vivo mediante el proxy local autenticado de kubectl.
        chromium = shutil.which('chromium') or shutil.which('google-chrome')
        if chromium:
            gateway = subprocess.Popen([kubectl, 'proxy', '--address=127.0.0.1', f'--port={browser_port}'],
                                       env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            resources.callback(terminate, gateway)
            url = f'http://127.0.0.1:{browser_port}/readyz?verbose'
            direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                for _ in range(35):
                    try:
                        with direct.open(url, timeout=2) as response:
                            if b'readyz check passed' in response.read():
                                break
                    except OSError:
                        pass
                    time.sleep(.2)
                else:
                    raise RuntimeError('La respuesta del proxy de kubectl no contiene readyz')
                shot = directory / 'api-readyz.png'
                try:
                    from playwright.sync_api import sync_playwright
                except ImportError:
                    subprocess.run([chromium, '--headless', '--no-sandbox', '--disable-gpu',
                                    '--disable-dev-shm-usage', f'--user-data-dir={temporary}/chromium',
                                    '--window-size=1040,820', f'--screenshot={shot.resolve()}', url],
                                   capture_output=True, timeout=20, check=True)
                else:
                    with sync_playwright() as driver:
                        browser = driver.chromium.launch(executable_path=chromium, args=['--no-sandbox'])
                        page = browser.new_page(viewport={'width': 1040, 'height': 820})
                        response = page.goto(url, wait_until='domcontentloaded', timeout=12000)
                        if response.status != 200 or 'readyz check passed' not in page.locator('body').inner_text():
                            raise RuntimeError('El navegador no recibió la lista de readiness')
                        page.screenshot(path=str(shot))
                        browser.close()
                if not shot.is_file() or not shot.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                    raise RuntimeError('La captura PNG no se completó')
                report['captura'] = {'archivo': shot.name, 'url': url, 'origen': 'Chromium sobre kubectl proxy y HAProxy'}
            except Exception as exc:
                report['captura'] = {'error': str(exc)}
        report['fin_utc'] = utc()
        (directory / 'api.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
