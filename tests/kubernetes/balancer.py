#!/usr/bin/env python3
"""Comprueba el enrutamiento y los cambios de salud con sockets de ensayo locales."""
import argparse
import csv
import datetime as dt
import json
import re
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Reply(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self.request.sendall(self.server.label.encode() + b"\n")
        except ConnectionError:
            pass


class Backend(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--haproxy", default="haproxy")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    template = (ROOT/"infrastructure/load-balancers/kubernetes/haproxy.cfg").read_text()
    keys = sorted(set(re.findall(r"10\.42\.10\.\d+:\d+", template)))
    with tempfile.TemporaryDirectory() as scratch, ExitStack() as cleanup:
        with ExitStack() as reserve:
            ports = {}
            for key in keys:
                sock = reserve.enter_context(socket.socket())
                sock.bind(("127.0.0.1",0))
                ports[key] = sock.getsockname()[1]
        active = {}
        def start(key):
            backend = Backend(("127.0.0.1", ports[key]), Reply)
            backend.label = key
            threading.Thread(target=backend.serve_forever, daemon=True).start()
            active[key] = backend
        def stop(key):
            backend = active.pop(key)
            backend.shutdown()
            backend.server_close()
        def stop_all():
            for key in list(active):
                stop(key)
        cleanup.callback(stop_all)
        for key in keys:
            if not key.startswith("10.42.10.11:"):
                start(key)
        stats = str(Path(scratch)/"admin.sock")
        for key in sorted(keys, key=len, reverse=True):
            template = template.replace(key, f"127.0.0.1:{ports[key]}")
        config = Path(scratch)/"haproxy.cfg"
        config.write_text(f"global\n    stats socket {stats} mode 600 level user\n\n" +
                          template[template.index("defaults\n"):].replace("    log global\n",""))
        def run(*cmd):
            return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        version = run(args.haproxy, "-v").stdout.splitlines()[0]
        run(args.haproxy, "-c", "-f", config)
        log = cleanup.enter_context((Path(scratch)/"proxy.log").open("w"))
        proxy = subprocess.Popen([args.haproxy, "-db","-f",config], stdout=log, stderr=log)
        def close_proxy():
            if proxy.poll() is None:
                proxy.terminate()
                proxy.wait(timeout=10)
        cleanup.callback(close_proxy)
        started = dt.datetime.now(dt.timezone.utc)
        def states():
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect(stats)
                s.sendall(b"show stat\n")
                rows = s.makefile().read().lstrip("# ").splitlines()
            return {(r["pxname"],r["svname"]):r["status"] for r in csv.DictReader(rows)}
        def wait(worker_state):
            end = time.monotonic()+18
            while time.monotonic() < end:
                try:
                    if states().get(("ingress-http","worker-1")) == worker_state:
                        return
                except (FileNotFoundError, ConnectionRefusedError):
                    pass
                time.sleep(.2)
            raise RuntimeError(f"Tiempo agotado esperando {worker_state}")
        def replies(port, count=1):
            values=[]
            for _ in range(count):
                with socket.create_connection(("127.0.0.1",ports[f"10.42.10.11:{port}"]),timeout=3) as s:
                    values.append(s.makefile().readline().strip())
            return values
        wait("UP")
        initial={port:replies(port,4) for port in (6443,9345,80,443)}
        for port in (6443,9345):
            assert set(initial[port]) == {f"10.42.10.31:{port}"}
        for port in (80,443):
            assert set(initial[port]) == {f"10.42.10.{i}:{port}" for i in (32,33)}
        stop("10.42.10.32:80")
        wait("DOWN")
        down=replies(80,4)
        assert set(down)=={"10.42.10.33:80"}
        start("10.42.10.32:80")
        wait("UP")
        recovered=replies(80,4)
        assert set(recovered)=={"10.42.10.32:80","10.42.10.33:80"}
        report={"inicio_utc":started.isoformat(),"fin_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
                "haproxy":version,"alcance":"HAProxy real; endpoints TCP de ensayo en loopback. Los nombres de respuesta representan el destino del inventario. Sin workers ni tráfico Kubernetes.",
                "respuestas_iniciales":initial,"worker_1_apagado":{"check":"DOWN","respuestas":down},
                "worker_1_recuperado":{"check":"UP","respuestas":recovered}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(f"Reenvío, exclusión y reincorporación verificadas: {args.output}")


if __name__=="__main__":
    main()
