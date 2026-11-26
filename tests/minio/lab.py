"""Pruebas funcionales y de recuperación sobre un proyecto Docker nuevo y desechable."""
import argparse
from collections import Counter
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
from xml.etree import ElementTree

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
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = test()
            if value:
                return value
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
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

    def mc(self, *args, data=None, check=True, timeout=60):
        return self.compose("exec", "-T", "cliente", "mc", *args, data=data, check=check, timeout=timeout)

    def health(self, path):
        with self.http.open(urllib.request.Request(self.api + path, method="HEAD"), timeout=5) as r:
            return {"http": r.status, **{k.lower(): v for k, v in r.headers.items()
                    if k.lower() in ("x-minio-read-quorum", "x-minio-write-quorum")}}

    def info(self, expected, alias="admin"):
        body = json.loads(self.mc("admin", "info", "--json", alias, timeout=55).stdout)["info"]
        be = body["backend"]
        if be["onlineDisks"] != expected:
            return None
        return {"backend": be, "deployment_id": body.get("deploymentID"), "servidores": [
            {"endpoint": s["endpoint"], "estado": s["state"],
             "discos": [{"endpoint": d["endpoint"], "estado": d["state"]} for d in s.get("drives", [])]}
            for s in body["servers"]]}

    def transfer(self, bucket_path, payload):
        self.mc("pipe", bucket_path, data=payload)
        return self.download(bucket_path, payload)

    def download(self, bucket_path, expected):
        return self.integrity(bucket_path, expected, self.mc("cat", bucket_path).stdout)

    @staticmethod
    def integrity(key, source, downloaded):
        original = hashlib.sha256(source).hexdigest()
        observed = hashlib.sha256(downloaded).hexdigest()
        verify(original == observed and source == downloaded, f"Diferencia al recuperar {key}")
        return {"objeto": key, "bytes": len(downloaded), "sha256_origen": original, "sha256_descarga": observed}

    def direct_download(self, server, key, source):
        # La llave sólo se lee en el cliente del proyecto efímero.
        command = 'mc alias set directo "http://$1:9000" ingesta-lab "$(cat /run/secrets/ingesta_password)" >/dev/null && exec mc cat "directo/$2"'
        raw = self.compose("exec", "-T", "cliente", "sh", "-ec", command, "sh", server, key, timeout=15).stdout
        return {"servidor": server, **self.integrity(key, source, raw)}

    def recovered_reads(self, payload, degraded, record):
        # Un nodo recién arrancado puede conocer sus discos antes de restablecer contacto con cada par.
        self.compose("exec", "-T", "cliente", "sh", "-ec",
                     'mc alias set reincorporado http://minio-3:9000 "$(cat /run/secrets/root_user)" "$(cat /run/secrets/root_password)" >/dev/null')
        view = wait_for(lambda: self.info(6, "reincorporado"), "seis discos desde minio-3", seconds=75)
        record("P4 · topología vista por minio-3", **view)
        checks = []
        deadline = time.monotonic() + 75
        for name, content in (("ventas.csv", payload), ("degradado.bin", degraded)):
            for server in SERVERS:
                for attempt in range(1, 9):
                    try:
                        check = self.direct_download(server, "bronze/" + name, content)
                    except (RuntimeError, subprocess.TimeoutExpired) as exc:
                        record("P4 · lectura directa pendiente", servidor=server, objeto=name, intento=attempt, error=str(exc))
                        if "Diferencia al recuperar" in str(exc) or time.monotonic() >= deadline or attempt == 8:
                            raise
                        time.sleep(3)
                    else:
                        checks.append(check)
                        break
        return checks

    def signed_request(self, method, key, identity, payload=None):
        username = "ingesta-lab" if identity == "ingesta" else (self.secrets / "root_user").read_text()
        password = (self.secrets / ("ingesta_password" if identity == "ingesta" else "root_password")).read_text()
        # curl recibe las credenciales por stdin y el contenido del objeto desde un archivo independiente.
        config = f'user = "{username}:{password}"\n'.encode()
        with tempfile.TemporaryDirectory(dir=self.secrets) as tmp:
            body = Path(tmp) / "respuesta"
            args = ["curl", "-q", "--config", "-", "--aws-sigv4", "aws:amz:us-east-1:s3", "--noproxy", "*",
                    "--silent", "--show-error", "--max-time", "12", "--request", method,
                    "--output", str(body), "--write-out", "%{http_code}"]
            if payload is not None:
                obj = Path(tmp) / "objeto"
                obj.write_bytes(payload)
                args.extend(["--header", "Content-Type: application/octet-stream", "--data-binary", "@" + str(obj)])
            proc = subprocess.run([*args, self.api + "/" + key], input=config, capture_output=True, check=True)
            status = int(proc.stdout)
            result = {"metodo": method, "objeto": key, "identidad": "ingesta-lab" if identity == "ingesta" else "administrador",
                      "http": status}
            if status >= 400:
                error = ElementTree.fromstring(body.read_bytes())
                result.update(codigo_s3=error.findtext("Code"), mensaje_s3=error.findtext("Message"),
                              request_id=error.findtext("RequestId"))
            return result

    def check_permissions(self, record):
        cfg = json.loads(self.mc("alias", "list", "ingesta", "--json").stdout)
        user = json.loads(self.mc("admin", "user", "info", "admin", "ingesta-lab", "--json").stdout)
        endpoint = cfg.get("URL", cfg.get("url"))
        verify(cfg["accessKey"] == user["accessKey"] == "ingesta-lab" and endpoint == "http://lb-minio:9000",
               "El alias del ensayo debe usar la identidad de ingesta y el balanceador")
        verify(user["policyName"] == "ingesta-bronze" and user["userStatus"] == "enabled", "Política inesperada")
        record("Identidad de ingesta", alias="ingesta", endpoint=endpoint, usuario=user["accessKey"],
               politica=user["policyName"], estado=user["userStatus"])
        for bucket in ("gold", "silver"):
            key = f"{bucket}/prohibido"
            payload = b"sin permiso"
            plain = self.mc("pipe", "ingesta/" + key, data=payload, check=False)
            put = self.signed_request("PUT", key, "ingesta", payload)
            lookup = self.signed_request("GET", key, "admin")
            record("Escritura restringida", bucket=bucket, comando="mc pipe ingesta/" + key,
                   retorno_mc=plain.returncode, stdout_mc=plain.stdout.decode().rstrip(),
                   stderr_mc=plain.stderr.decode().rstrip(), escritura=put, verificacion_administrativa=lookup)
            verify(plain.returncode != 0 and (put["http"], put.get("codigo_s3")) == (403, "AccessDenied")
                   and (lookup["http"], lookup.get("codigo_s3")) == (404, "NoSuchKey"),
                   f"La comprobación IAM de {key} no coincide con la denegación y ausencia esperadas")

    def container(self, server):
        cid = self.compose("ps", "-a", "-q", server).stdout.decode().strip()
        fmt = '{{.State.Status}}\n{{range .Mounts}}{{if eq .Type "volume"}}{{.Destination}} {{.Name}}{{println}}{{end}}{{end}}'
        raw = subprocess.check_output(["docker", "inspect", "--format", fmt, cid], text=True).splitlines()
        volumes = dict(row.split() for row in raw[1:] if row.startswith("/srv/minio/"))
        verify(set(volumes) == {"/srv/minio/disk1", "/srv/minio/disk2"}, f"Montajes inesperados para {server}")
        return {"servicio": server, "id_contenedor": cid, "estado": raw[0], "volumenes": volumes}

    def routing(self, phase, expected, record):
        for attempt in range(1, 6):
            tag = f"muestra={phase}-{attempt}-"
            statuses = []
            for i in range(6):
                try:
                    statuses.append(self.health(f"/minio/health/live?{tag}{i}")["http"])
                except urllib.error.HTTPError as exc:
                    statuses.append(exc.code)
            def matching_logs():
                raw = self.compose("logs", "--no-color", "--no-log-prefix", "lb-minio").stdout.decode()
                lines = [line for line in raw.splitlines() if f'"HEAD /minio/health/live?{tag}' in line]
                return lines if len(lines) >= 6 else None
            lines = wait_for(matching_logs, "seis registros HAProxy de la serie", seconds=6)
            routed = Counter(re.findall(r"minio_api/(minio-[123])", "\n".join(lines)))
            record("Distribución HAProxy", fase=phase, serie=attempt, http=statuses,
                   solicitudes_por_backend=dict(routed), registros=lines)
            if statuses == [200] * 6 and set(routed) == set(expected) and sum(routed.values()) == 6:
                return
            time.sleep(1)
        raise RuntimeError(f"HAProxy no alcanzó la distribución esperada durante {phase}")

    def quorums(self):
        read = self.health("/minio/health/cluster/read")
        write = self.health("/minio/health/cluster")
        verify(read.get("x-minio-read-quorum") == "4" and write.get("x-minio-write-quorum") == "4",
               "Las cabeceras de MinIO no confirman el quórum esperado")
        return {"lectura": read, "escritura": write}

    def screenshots(self, output, record):
        from playwright.sync_api import sync_playwright
        root_user = (self.secrets / "root_user").read_text()
        root_password = (self.secrets / "root_password").read_text()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=shutil.which("chromium"), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            page.set_default_timeout(12000)

            def capture(name, texts):
                for text in texts:
                    page.get_by_text(text, exact=True).filter(visible=True).first.wait_for()
                body = page.locator("body").inner_text()
                verify(all(s not in body for s in (root_user, root_password)), "La vista contiene una credencial")
                path = output / name
                page.screenshot(path=path)
                record("Captura de la consola autenticada", archivo=name, contenido=texts,
                       sha256=hashlib.sha256(path.read_bytes()).hexdigest())

            try:
                page.goto(self.console, wait_until="domcontentloaded")
                page.get_by_placeholder("Username").fill(root_user)
                page.get_by_placeholder("Password").fill(root_password)
                page.get_by_placeholder("Password").press("Enter")
                capture("consola.png", ["bronze", "silver", "gold"])
                object_browser = page.url
                page.get_by_text("Buckets", exact=True).filter(visible=True).first.click()
                page.wait_for_url("**/buckets")
                capture("buckets.png", ["Buckets", "bronze", "silver", "gold"])
                page.goto(object_browser, wait_until="domcontentloaded")
                page.get_by_text("bronze", exact=True).filter(visible=True).first.click()
                capture("objetos-bronze.png", ["ventas.csv", "degradado.bin", "recuperado.csv"])
            finally:
                browser.close()

    def run(self, record):
        self.compose("up", "-d", timeout=300)
        self.api = "http://" + self.compose("port", "lb-minio", "9000").stdout.decode().strip()
        self.console = "http://" + self.compose("port", "lb-minio", "9001").stdout.decode().strip()
        wait_for(lambda: self.health("/minio/health/cluster"), "escritura por HAProxy")
        nodes = [self.container(server) for server in SERVERS]
        verify(len({v for n in nodes for v in n["volumenes"].values()}) == 6, "Se esperaban seis volúmenes distintos")
        record("Despliegue", proyecto=self.project, api_efimera=self.api, consola_efimera=self.console, nodos=nodes,
               minio=self.compose("exec", "-T", SERVERS[0], "minio", "--version").stdout.decode().splitlines()[0],
               mc=self.mc("--version").stdout.decode().splitlines()[0],
               haproxy=self.compose("exec", "-T", "lb-minio", "haproxy", "-v").stdout.decode().splitlines()[0])
        pre = self.compose("exec", "-T", "cliente", "sh", "-ec",
                           'mc alias set previo http://lb-minio:9000 "$(cat /run/secrets/root_user)" "$(cat /run/secrets/root_password)" >/dev/null && mc ls --json previo')
        verify(not pre.stdout.strip(), "El ensayo requiere tres servidores con volúmenes nuevos")
        init = self.compose("exec", "-T", "-e", "MINIO_ENDPOINT=http://lb-minio:9000", "-e",
                            "MINIO_SECRETS_DIR=/run/secrets", "cliente", "sh", "/lab/bootstrap.sh")
        buckets = [json.loads(line)["key"].strip("/") for line in self.mc("ls", "--json", "admin").stdout.splitlines()]
        verify(set(buckets) == {"bronze", "silver", "gold"}, "El listado de buckets difiere del esperado")
        record("Creación de buckets", antes=[], despues=buckets, salida=init.stdout.decode().splitlines())
        baseline = wait_for(lambda: self.info(6), "seis discos en línea")
        verify(baseline["backend"]["standardSCParity"] == 2 and baseline["backend"]["totalDrivesPerSet"] == [6]
               and len(baseline["servidores"]) == 3 and all(s["estado"] == "online" for s in baseline["servidores"]),
               "El conjunto debe tener tres servidores con seis discos y EC:2")
        record("Estado nominal", **baseline, **self.quorums())
        payload = (ROOT / "datasets/source/ventas.csv").read_bytes()
        record("Lectura y escritura Bronze", identidad="ingesta-lab", fuente="datasets/source/ventas.csv",
               **self.transfer("ingesta/bronze/ventas.csv", payload))
        self.check_permissions(record)
        for peer in SERVERS:
            endpoints = []
            for target in SERVERS:
                if peer == target:
                    continue
                status = self.compose("exec", "-T", peer, "curl", "-fsS", "-o", "/dev/null", "-w", "%{http_code}",
                                      f"http://{target}:9000/minio/health/live").stdout.decode()
                verify(status == "200", f"Fallo de comunicación {peer} a {target}")
                endpoints.append({"destino": target, "http": int(status)})
            record("Comunicación entre nodos", origen=peer, destinos=endpoints,
                   lectura_directa=self.direct_download(peer, "bronze/ventas.csv", payload))
        self.routing("nominal", SERVERS, record)

        start, clock = utc(), time.monotonic()
        self.compose("stop", "-t", "4", "minio-3")
        stopped = self.container("minio-3")
        verify(stopped["estado"] == "exited", "El tercer contenedor debe estar detenido")
        record("P3 · detención controlada", inicio_utc=start, contenedor=stopped)
        reduced = wait_for(lambda: self.info(4), "detección del nodo detenido")
        verify(reduced["backend"]["offlineDisks"] == 2, "Se esperaban dos discos fuera de línea")
        self.routing("caida", SERVERS[:2], record)
        degraded = hashlib.shake_256(b"lago-distribuido/prueba-3").digest(1024 * 1024)
        record("P3 · nodo detenido", inicio_utc=start, **reduced, **self.quorums(), contenedor=stopped,
               anterior=self.download("ingesta/bronze/ventas.csv", payload),
               nuevo=self.transfer("ingesta/bronze/degradado.bin", degraded),
               duracion_s=round(time.monotonic() - clock, 3), estado="Ejecutada y aprobada")

        start, clock = utc(), time.monotonic()
        self.compose("start", "minio-3")
        record("P4 · arranque del mismo contenedor", inicio_utc=start)
        restored = wait_for(lambda: self.info(6), "reincorporación de seis discos")
        returning = self.container("minio-3")
        verify(returning == nodes[2], "La recuperación debe usar el mismo contenedor y los mismos volúmenes")
        verify(len(restored["servidores"]) == 3 and all(s["estado"] == "online" for s in restored["servidores"]),
               "Se esperaban los tres servidores en línea")
        self.routing("recuperacion", SERVERS, record)
        direct = self.recovered_reads(payload, degraded, record)
        record("P4 · nodo recuperado", inicio_utc=start, **restored, **self.quorums(), contenedor=returning,
               anterior=self.download("ingesta/bronze/ventas.csv", payload),
               durante_caida=self.download("ingesta/bronze/degradado.bin", degraded),
               lecturas_desde_cada_nodo=direct,
               posterior=self.transfer("ingesta/bronze/recuperado.csv", b"estado\nrecuperado\n"),
               duracion_s=round(time.monotonic() - clock, 3), estado="Ejecutada y aprobada")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="directorio vacío para el acta y las capturas")
    parser.add_argument("--sin-captura", action="store_true", help="ejecutar la validación S3 sin Playwright")
    args = parser.parse_args()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.output or ROOT / "evidence/moment-01/minio/runs" / stamp
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error("El destino ya contiene archivos. Elija un directorio vacío para conservar el historial.")
    target = output / "result.json"
    target.touch(exist_ok=False)
    started = time.monotonic()
    result = {"inicio_utc": utc(), "entorno": "Docker Compose, tres contenedores MinIO, seis volúmenes en un host y HAProxy",
              "comando": "python3 tests/minio/lab.py" + (" --sin-captura" if args.sin_captura else ""),
              "estado": "En curso", "funcional": "En curso", "capturas": "Pendientes", "eventos": []}

    def persist():
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(target)

    def record(step, **values):
        result["eventos"].append({"fecha_utc": utc(), "paso": step, **values})
        persist()
        print(step, flush=True)

    persist()
    try:
        with tempfile.TemporaryDirectory(prefix="lago-minio-") as tmp:
            lab = Lab(Path(tmp))
            try:
                try:
                    lab.run(record)
                    result["funcional"] = "Ejecutada y aprobada"
                except Exception as exc:
                    result.update(funcional="Ejecutada y fallida", error=str(exc))
                persist()
                if args.sin_captura:
                    result["capturas"] = "Omitidas por opción"
                elif any(e["paso"] == "Creación de buckets" for e in result["eventos"]):
                    try:
                        lab.screenshots(output, record)
                        result["capturas"] = "Aprobadas"
                    except Exception as exc:
                        result["capturas"] = "Incompletas"
                        record("Incidencia de captura", error=str(exc))
                if result["funcional"] == "Ejecutada y fallida":
                    raise RuntimeError(result["error"])
            finally:
                lab.compose("down", "--volumes", "--timeout", "4", timeout=100)
        result["estado"] = "Parcialmente ejecutada" if result["capturas"] == "Incompletas" else result["funcional"]
    except Exception as exc:
        if result["funcional"] == "En curso":
            result["funcional"] = "Ejecutada y fallida"
        result.update(estado="Ejecutada y fallida", error=str(exc))
        raise
    finally:
        result.update(fin_utc=utc(), duracion_segundos=round(time.monotonic() - started, 2))
        persist()
        print(target, flush=True)


if __name__ == "__main__":
    main()
