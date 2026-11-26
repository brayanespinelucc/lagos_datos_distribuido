#!/usr/bin/env python3
"""Comprueba por SSH la resolución de nombres y los 56 trayectos ICMP del laboratorio."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from provision import read_inventory


def peers_for(vms, source):
    return [vm for vm in vms if vm["id"] != source["id"]]


def probe(source, peers, identity, known_hosts):
    # El inventario se valida antes de construir la lista de argumentos remotos.
    pairs = "\n".join(f"{vm['hostname']} {vm['ip']}" for vm in peers)
    script = """while read -r peer target; do
    observed=$(getent ahostsv4 "$peer" | awk 'NR==1 {print $1}')
    if ping -n -c 1 -W 2 "$target" >/dev/null 2>&1; then result=ok; else result=error; fi
    printf '%s %s %s\\n' "$peer" "${observed:-ausente}" "$result"
done <<'PEERS'
""" + pairs + "\nPEERS\n"
    command = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=5",
               "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={known_hosts}",
               "-i", str(identity), "operador@" + source["ip"], "sh", "-s"]
    try:
        proc = subprocess.run(command, text=True, input=script, capture_output=True, timeout=75)
    except subprocess.TimeoutExpired:
        return {}, "SSH excedió el tiempo de espera"
    if proc.returncode != 0:
        return {}, proc.stderr.strip() or f"SSH código {proc.returncode}"
    return {name: (resolved, ping) for name, resolved, ping in (line.split() for line in proc.stdout.splitlines())}, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", required=True, type=Path)
    parser.add_argument("--known-hosts", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.identity, args.known_hosts):
        if not path.is_file():
            parser.error(f"Falta el archivo {path}")
    vms = read_inventory()["vms"]
    report = {"start_utc": datetime.now(timezone.utc).isoformat(), "checks": []}
    for vm in vms:
        peers = peers_for(vms, vm)
        observations, error = probe(vm, peers, args.identity.resolve(), args.known_hosts.resolve())
        for peer in peers:
            observed, ping = observations.get(peer["hostname"], (None, None))
            report["checks"].append({"from": vm["hostname"], "to": peer["hostname"], "expected_ip": peer["ip"],
                                     "observed_ip": observed, "ping": ping, "ssh_error": error,
                                     "pass": observed == peer["ip"] and ping == "ok"})
    report["end_utc"] = datetime.now(timezone.utc).isoformat()
    report["passed"] = sum(row["pass"] for row in report["checks"])
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] == len(report["checks"]) else 1


if __name__ == "__main__":
    sys.exit(main())
