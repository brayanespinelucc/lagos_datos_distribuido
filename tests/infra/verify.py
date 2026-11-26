#!/usr/bin/env python3
"""Verificación portátil del aprovisionamiento Proxmox/Ubuntu y emisión de un acta JSON."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from jsonschema import Draft4Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "infrastructure/proxmox"))
import provision

SCHEMA_URL = "https://raw.githubusercontent.com/canonical/cloud-init/24.1.3/cloudinit/config/schemas/schema-cloud-config-v1.json"
SCHEMA_SHA256 = "555f432090c19553dab5d03a2f643444f95bf418f2dd0ec3ceb9bf1c18f071ce"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(schema_path):
    if sha256(schema_path) != SCHEMA_SHA256:
        raise ValueError("El archivo recibido difiere del esquema oficial fijado de cloud-init 24.1.3.")
    schema = json.loads(schema_path.read_bytes())
    Draft4Validator.check_schema(schema)
    validator = Draft4Validator(schema)
    tool = [sys.executable, str(provision.HERE / "provision.py")]
    plan = json.loads(subprocess.check_output([*tool, "plan"], cwd=ROOT))
    guests = []
    with TemporaryDirectory() as temp:
        key, out = Path(temp) / "ensayo", Path(temp) / "config"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "ensayo", "-f", str(key)], check=True)
        subprocess.run([*tool, "render", "--ssh-key", str(key) + ".pub", "--output", str(out)],
                       cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        for vm in plan["vms"]:
            file, = out.glob(f"lago-{vm['id']}-*.yaml")
            header, body = file.read_text().split("\n", 1)
            if header != "#cloud-config":
                raise ValueError(f"Cabecera cloud-init inválida para {vm['hostname']}")
            config = json.loads(body)
            validator.validate(config)
            if config["hostname"] != vm["hostname"]:
                raise ValueError(f"Hostname inesperado para VM {vm['id']}")
            firewall = out / f"{vm['id']}.fw"
            rules = sum(row.startswith("IN ACCEPT ") for row in firewall.read_text().splitlines())
            if rules != vm["inbound_rules"]:
                raise ValueError(f"El firewall renderizado difiere del plan para la VM {vm['id']}")
            guests.append({"id": vm["id"], "hostname": vm["hostname"], "ip_propuesta": vm["ip"],
                           "cloud_init": "esquema aprobado", "reglas_entrada": rules, "sha256_firewall": sha256(firewall)})
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_provision.py")
    log = io.StringIO()
    tests = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    try:
        provision.require_pve()
        host_status = "Prerrequisitos locales presentes. Aplicación y comprobación de las VM pendientes."
    except ValueError as exc:
        host_status = str(exc)
    sources = ["infrastructure/proxmox/inventory.json", "infrastructure/proxmox/provision.py",
               "infrastructure/proxmox/check_mesh.py", "infrastructure/ubuntu/base-cloud-config.json",
               "infrastructure/ubuntu/prepare_volumes.py", "architecture/network/communication.csv",
               "architecture/diagrams/red.svg", "tests/infra/test_provision.py", "tests/infra/verify.py"]
    return {
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entorno": platform.freedesktop_os_release()["PRETTY_NAME"],
        "python": platform.python_version(), "jsonschema": version("jsonschema"),
        "comando": "python3 tests/infra/verify.py --schema <copia de cloud-init 24.1.3>",
        "esquema": {"url": SCHEMA_URL, "sha256": SCHEMA_SHA256},
        "resultado_portatil": "aprobado" if tests.wasSuccessful() else "fallido",
        "pruebas": {"total": tests.testsRun, "fallos": len(tests.failures), "errores": len(tests.errors),
                    "omitidas": len(tests.skipped), "salida": log.getvalue().splitlines()},
        "recursos_propuestos": plan["totals"], "configuraciones": guests,
        "hipervisor": {"comprobacion_local": host_status, "vm_desplegadas_en_esta_prueba": 0,
                       "pares_icmp_ejecutados": 0, "pares_previstos": len(guests) * (len(guests) - 1)},
        "sha256_entradas": {p: sha256(ROOT / p) for p in sources}
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True, type=Path, help="Copia local de la versión fijada de Canonical")
    args = parser.parse_args()
    report = verify(args.schema)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["resultado_portatil"] == "aprobado" else 1)
