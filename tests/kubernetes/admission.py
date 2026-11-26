#!/usr/bin/env python3
"""Ensaya los manifiestos con etcd y el API oficial, sin kubelet ni scheduler."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess as sp
import tempfile
import time
from contextlib import ExitStack

ROOT = Path(__file__).resolve().parents[2]


def free_ports(count):
    with ExitStack() as stack:
        sockets = [stack.enter_context(socket.socket()) for _ in range(count)]
        for sock in sockets:
            sock.bind(("127.0.0.1", 0))
        return [sock.getsockname()[1] for sock in sockets]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path, help="Directorio con kube-apiserver, etcd y kubectl")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--haproxy", type=Path, help="Ensayar el frontend API y la carga P5 en un directorio de salida")
    args = parser.parse_args()
    bin_dir = args.assets.resolve()
    started = dt.datetime.now(dt.timezone.utc)
    with tempfile.TemporaryDirectory() as scratch, ExitStack() as cleanup:
        tmp = Path(scratch)
        client, peer, secure = free_ports(3)
        def url(port):
            return f"http://127.0.0.1:{port}"

        def cmd(*argv, check=True, **kwargs):
            return sp.run(argv, capture_output=True, text=True, check=check, timeout=30, **kwargs)

        def service(name, *argv):
            log = cleanup.enter_context((tmp / f"{name}.log").open("w+"))
            proc = sp.Popen([bin_dir / name, *argv], stdout=log, stderr=log)
            def stop():
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except sp.TimeoutExpired:
                        proc.kill()
                        proc.wait()
            cleanup.callback(stop)
            return proc, log

        cmd("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
            "-keyout", tmp / "server.key", "-out", tmp / "server.crt", "-subj", "/CN=localhost",
            "-addext", "subjectAltName=IP:127.0.0.1")
        cmd("openssl", "genrsa", "-out", tmp / "sa.key", "2048")
        token = secrets.token_hex(32)
        (tmp / "token.csv").write_text(f"{token},laboratorio,lago-1,system:masters\n")
        etcd, _ = service("etcd", "--name=prueba", f"--data-dir={tmp}/data",
                          f"--listen-client-urls={url(client)}", f"--advertise-client-urls={url(client)}",
                          f"--listen-peer-urls={url(peer)}", f"--initial-advertise-peer-urls={url(peer)}",
                          f"--initial-cluster=prueba={url(peer)}")
        server, log = service("kube-apiserver", "--advertise-address=127.0.0.1", "--bind-address=127.0.0.1",
                              f"--secure-port={secure}", f"--etcd-servers={url(client)}",
                              "--authorization-mode=RBAC", "--anonymous-auth=false",
                              "--service-cluster-ip-range=10.53.0.0/16", "--service-account-issuer=https://cluster.local",
                              f"--service-account-key-file={tmp}/sa.key", f"--service-account-signing-key-file={tmp}/sa.key",
                              f"--tls-cert-file={tmp}/server.crt", f"--tls-private-key-file={tmp}/server.key",
                              f"--token-auth-file={tmp}/token.csv", f"--cert-dir={tmp}/certs")
        kubeconf = {"apiVersion":"v1", "kind":"Config", "clusters":[{"name":"m1","cluster":{
            "server": f"https://127.0.0.1:{secure}", "certificate-authority": str(tmp/"server.crt")}}],
            "users":[{"name":"prueba","user":{"token":token}}], "contexts":[{"name":"m1","context":{
                "cluster":"m1","user":"prueba"}}], "current-context":"m1"}
        config = tmp / "kubeconfig"
        config.write_text(json.dumps(kubeconf))
        env = {**os.environ, "KUBECONFIG":str(config), "KUBECTL":str(bin_dir/"kubectl"),
               "HOME":scratch, "NO_PROXY":"127.0.0.1", "no_proxy":"127.0.0.1"}
        def k(*argv, **opts):
            return cmd(bin_dir/"kubectl", *argv, env=env, **opts)

        for _ in range(100):
            result = k("--request-timeout=1s", "get", "--raw=/readyz", check=False)
            if result.returncode == 0 and result.stdout == "ok":
                break
            if server.poll() is not None or etcd.poll() is not None:
                log.seek(0)
                raise RuntimeError(log.read()[-2500:])
            time.sleep(.2)
        else:
            raise RuntimeError("El API no pasó /readyz")
        if args.haproxy:
            from api_proxy import validate
            validate(args.haproxy.resolve(), args.output, tmp, kubeconf, env, bin_dir/"kubectl", secure, free_ports(2), ROOT)
            return
        script = ROOT/"infrastructure/kubernetes/deploy.sh"
        first = cmd(script, env=env).stdout.splitlines()
        def fingerprint():
            crt = k("get", "secret", "m1-ingress-tls", "-n", "lago-m1", "-o", "jsonpath={.data.tls\\.crt}").stdout
            return hashlib.sha256(crt.encode()).hexdigest()
        cert_before = fingerprint()
        second = cmd(script, env=env).stdout.splitlines()
        if fingerprint() != cert_before:
            raise RuntimeError("La reconciliación rotó el certificado")
        invalid = {"apiVersion":"v1", "kind":"ConfigMap","metadata":{"name":"invalido","namespace":"lago-m1"},
                   "campoDesconocido": 1}
        rejection = k("apply", "--server-side", "--dry-run=server", "--validate=strict", "-f", "-",
                      input=json.dumps(invalid), check=False)
        if not rejection.returncode or "campoDesconocido" not in rejection.stderr:
            raise RuntimeError("Falló el control negativo de esquema")
        resources = {}
        for types, namespace in [("ns,sc,pv", []), ("deploy,sts,svc,ingress,pvc,configmap,networkpolicy,secret", ["-n","lago-m1"])]:
            for item in json.loads(k("get", types, *namespace, "-o", "json").stdout)["items"]:
                name = item["metadata"]["name"]
                if namespace or name.startswith("lago-m1"):
                    resources.setdefault(item["kind"], []).append(name)
        if not {"StatefulSet","Deployment","Secret","NetworkPolicy","Ingress","PersistentVolume","StorageClass"} <= resources.keys():
            raise RuntimeError("Faltan recursos admitidos")
        nodes = json.loads(k("get","nodes","-o","json").stdout)["items"]
        if nodes:
            raise RuntimeError("El API de prueba recibió nodos ajenos")
        result = {"inicio_utc":started.isoformat(), "fin_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
                  "alcance":"etcd y kube-apiserver reales en loopback, sin kubelet, scheduler, RKE2 ni tráfico de Pods",
                  "version_api":json.loads(k("get","--raw=/version").stdout)["gitVersion"],
                  "version_etcd":cmd(bin_dir/"etcd","--version").stdout.splitlines()[0],
                  "readyz":"ok", "nodos_observados":len(nodes), "primera_aplicacion":first,
                  "segunda_aplicacion":second,"certificado_preservado":True,
                  "objetos_leidos_del_api":resources,"rechazo_control_negativo":rejection.stderr.strip()}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
    print(f"Admisión y reconciliación verificadas: {args.output}")


if __name__ == "__main__":
    main()
