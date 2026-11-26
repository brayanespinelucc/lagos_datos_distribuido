"""Pruebas funcionales y de recuperación sobre un proyecto Docker nuevo y desechable."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infrastructure/minio/compose.yaml"
SERVERS = ["minio-1", "minio-2", "minio-3"]


def utc():
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def verify(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def wait_for(test, description, seconds=100):
    last = None
    for _ in range(seconds):
        try:
            value = test()
            if value:
                return value
        except (OSError, ValueError, RuntimeError) as exc:
            last = exc
        time.sleep(1)
    raise RuntimeError(f"Tiempo agotado esperando {description}. Último error: {last}")


class Lab:
    def __init__(self, directory):
        self.project = "lago-prueba-" + uuid.uuid4().hex[:10]
        self.env = dict(os.environ, MINIO_SECRETS_DIR=str(directory))
        self.secrets = directory
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for name in ["root_user", "root_password", "ingesta_password"]:
            path = directory / name
            path.write_text(secrets.token_hex(20), encoding="utf-8")
            # Docker monta sólo cada archivo; el directorio padre sólo admite al propietario.
            path.chmod(0o444)

    def compose(self, *args, data=None, check=True, timeout=180):
        proc = subprocess.run(
            ["docker", "compose", "-p", self.project, "-f", str(COMPOSE), *args],
            input=data, capture_output=True, env=self.env, timeout=timeout
        )
        if check and proc.returncode:
            message = proc.stderr.decode(errors="replace")[-1400:]
            raise RuntimeError(f"docker compose {args[0]} terminó con {proc.returncode}: {message}")
        return proc

    def mc(self, *args, data=None, check=True):
        return self.compose("exec", "-T", "cliente", "mc", *args, data=data, check=check)

    def health(self, path):
        with self.http.open(urllib.request.Request(self.api + path, method="HEAD"), timeout=5) as r:
            return {"http": r.status, **{k.lower(): v for k, v in r.headers.items()
                    if k.lower() in ("x-minio-read-quorum", "x-minio-write-quorum")}}

    def info(self, expected):
        body = json.loads(self.mc("admin", "info", "--json", "admin").stdout)["info"]
        be = body["backend"]
        if be["onlineDisks"] != expected:
            return None
        return {"backend": be, "servidores": [
            {"endpoint": s["endpoint"], "estado": s["state"],
             "discos": [{"endpoint": d["endpoint"], "estado": d["state"]} for d in s.get("drives", [])]}
            for s in body["servers"]]}

    def transfer(self, bucket_path, payload):
        self.mc("pipe", bucket_path, data=payload)
        return self.download(bucket_path, payload)

    def download(self, bucket_path, expected):
        raw = self.mc("cat", bucket_path).stdout
        verify(raw == expected, f"Diferencia al recuperar {bucket_path}")
        return {"objeto": bucket_path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    def screenshot(self, path):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=shutil.which("chromium"), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1280, "height": 840})
            page.goto(self.console, wait_until="domcontentloaded")
            page.get_by_placeholder("Username").fill((self.secrets / "root_user").read_text())
            page.get_by_placeholder("Password").fill((self.secrets / "root_password").read_text())
            page.get_by_role("button", name="Login").click()
            for bucket in ["bronze", "silver", "gold"]:
                page.get_by_text(bucket, exact=True).first.wait_for()
            page.screenshot(path=path)
            browser.close()

    def run(self, events, output, screenshot):
        def record(step, **values):
            events.append({"fecha_utc": utc(), "paso": step, **values})
            print(step, flush=True)
        self.compose("up", "-d", timeout=600)
        self.api = "http://" + self.compose("port", "lb-minio", "9000").stdout.decode().strip()
        self.console = "http://" + self.compose("port", "lb-minio", "9001").stdout.decode().strip()
        wait_for(lambda: self.health("/minio/health/cluster"), "escritura por HAProxy")
        record("Despliegue", proyecto=self.project, api_efimera=self.api, consola_efimera=self.console,
               minio=self.compose("exec", "-T", SERVERS[0], "minio", "--version").stdout.decode().splitlines()[0],
               mc=self.mc("--version").stdout.decode().splitlines()[0],
               haproxy=self.compose("exec", "-T", "lb-minio", "haproxy", "-v").stdout.decode().splitlines()[0])
        init = self.compose("exec", "-T", "-e", "MINIO_ENDPOINT=http://lb-minio:9000", "-e",
                            "MINIO_SECRETS_DIR=/run/secrets", "cliente", "sh", "/lab/bootstrap.sh")
        buckets = [json.loads(line)["key"].strip("/") for line in self.mc("ls", "--json", "admin").stdout.splitlines()]
        verify(set(buckets) == {"bronze", "silver", "gold"}, "Faltan buckets")
        user = json.loads(self.mc("admin", "user", "info", "admin", "ingesta-lab", "--json").stdout)
        verify(user["policyName"] == "ingesta-bronze" and user["userStatus"] == "enabled", "Política inactiva")
        denied = self.mc("pipe", "ingesta/gold/prohibido", data=b"sin permiso", check=False)
        error = (denied.stdout + denied.stderr).decode(errors="replace")
        verify(denied.returncode != 0 and "Access Denied" in error, "La escritura en Gold debía ser denegada por IAM")
        record("Buckets e IAM", buckets=buckets, usuario=user, salida=init.stdout.decode().splitlines(),
               prueba_negativa=error.strip(), codigo_denegado=denied.returncode)
        baseline = wait_for(lambda: self.info(6), "seis discos")
        verify(baseline["backend"]["standardSCParity"] == 2 and baseline["backend"]["totalDrivesPerSet"] == [6],
               "La configuración efectiva debe tener un set de seis discos con EC:2")
        for peer in SERVERS:
            endpoints = []
            for target in SERVERS:
                if peer != target:
                    status = self.compose("exec", "-T", peer, "curl", "-fsS", "-o", "/dev/null", "-w", "%{http_code}",
                                          f"http://{target}:9000/minio/health/live").stdout.decode()
                    verify(status == "200", "Fallo de comunicación entre nodos MinIO")
                    endpoints.append({"destino": target, "http": status})
            record("Comunicación entre servicios MinIO", origen=peer, destinos=endpoints)
        if screenshot:
            self.screenshot(output / "console.png")
            record("Consola web autenticada", captura="console.png", buckets_visibles=buckets)
        for _ in range(6):
            self.health("/minio/health/live")
        raw = self.compose("logs", "--no-log-prefix", "lb-minio").stdout.decode()
        routed = [line.strip() for line in raw.splitlines() if '"HEAD /minio/health/live ' in line]
        names = sorted(set(re.findall(r"minio_api/(minio-[123])", "\n".join(routed))))
        verify(names == SERVERS, "Rotación HAProxy incompleta")
        payload = (ROOT / "datasets/source/ventas.csv").read_bytes()
        record("Servicio nominal", **baseline, s3=self.transfer("ingesta/bronze/ventas.csv", payload),
               servidores_balanceados=names, registros_haproxy=routed[-6:],
               lectura=self.health("/minio/health/cluster/read"), escritura=self.health("/minio/health/cluster"))
        self.compose("stop", "-t", "4", "minio-3")
        reduced = wait_for(lambda: self.info(4), "detección del nodo caído")
        verify(reduced["backend"]["offlineDisks"] == 2, "El clúster debía informar dos discos fuera de línea")
        degraded = b"fecha,evento\n2025-04-22,escritura_con_un_nodo_detenido\n"
        record("P3 · un nodo detenido", **reduced, lectura=self.health("/minio/health/cluster/read"),
               escritura=self.health("/minio/health/cluster"), anterior=self.download("ingesta/bronze/ventas.csv", payload),
               nuevo=self.transfer("ingesta/bronze/degradado.csv", degraded))
        self.compose("start", "minio-3")
        restored = wait_for(lambda: self.info(6), "reincorporación de los seis discos")
        verify(all(s["estado"] == "online" for s in restored["servidores"]), "Algún servidor quedó fuera de línea")
        record("P4 · nodo recuperado", **restored, lectura=self.health("/minio/health/cluster/read"),
               escritura=self.health("/minio/health/cluster"), anterior=self.download("ingesta/bronze/ventas.csv", payload),
               durante_caida=self.download("ingesta/bronze/degradado.csv", degraded),
               posterior=self.transfer("ingesta/bronze/recuperado.csv", b"estado\nrecuperado\n"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/moment-01/minio")
    parser.add_argument("--sin-captura", action="store_true", help="ejecutar la validación S3 sin Playwright")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    events = []
    now = time.monotonic()
    result = {"inicio_utc": utc(), "entorno": "Docker Compose, tres contenedores y seis volúmenes sobre un host compartido",
              "comando": "python tests/minio/lab.py" + (" --sin-captura" if args.sin_captura else ""), "eventos": events}
    try:
        with tempfile.TemporaryDirectory(prefix="lago-minio-") as tmp:
            lab = Lab(Path(tmp))
            try:
                lab.run(events, args.output, not args.sin_captura)
            finally:
                lab.compose("down", "--volumes", "--timeout", "4", timeout=180)
        result["estado"] = "Ejecutada y aprobada"
    except Exception as exc:
        result.update(estado="Ejecutada y fallida", error=str(exc))
        raise
    finally:
        result.update(fin_utc=utc(), duracion_segundos=round(time.monotonic() - now, 2))
        (args.output / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
