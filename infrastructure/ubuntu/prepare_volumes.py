#!/usr/bin/env python3
"""Inicializa exclusivamente los discos identificados por el inventario de esta VM."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile

CONFIG = Path("/etc/lago/minio-disks.json")


def run(*args):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE).stdout


def matching_disk(spec, devices):
    matches = [d for d in devices if d["type"] == "disk" and d["serial"] == spec["serial"]]
    if len(matches) != 1:
        raise ValueError(f"Se esperaba un único disco con serial {spec['serial']}")
    disk = matches[0]
    if disk["size"] != spec["size_gib"] * 1024**3 or disk["ro"] or disk["rm"]:
        raise ValueError(f"Capacidad o atributos inesperados en {spec['serial']}")
    if disk.get("children") or disk["pttype"] or disk["type"] != "disk":
        raise ValueError(f"El dispositivo {disk['path']} contiene particiones o dependientes")
    mounts = {m for m in (disk["mountpoints"] or []) if m}
    if mounts - {spec["mount"]}:
        raise ValueError(f"Disco ocupado por otro montaje: {disk['path']}")
    return disk


def needs_format(spec, disk, signatures):
    if not signatures and not disk["fstype"] and not disk["uuid"]:
        return True
    if signatures == {"xfs"} and disk["fstype"] == "xfs" and disk["label"] == spec["serial"] and disk["uuid"]:
        return False
    raise ValueError(f"Firma ajena o ambigua en {disk['path']}; revisar fuera del instalador")


def fstab_entry(fstab, disk, destination):
    expected = "UUID=" + disk["uuid"] if disk["uuid"] else None
    found = False
    for line in fstab.splitlines():
        fields = line.split("#", maxsplit=1)[0].split()
        if len(fields) < 3:
            continue
        source, target, fs = fields[:3]
        if target == destination or source in {expected, disk["path"]}:
            if source != expected or target != destination or fs != "xfs" or found:
                raise ValueError(f"Entrada fstab incompatible con {destination}")
            found = True
    if found or expected is None:
        return ""
    return f"{expected} {destination} xfs defaults,nodev,nosuid 0 0\n"


def inspect(specs, fstab):
    fields = "PATH,TYPE,SIZE,RO,RM,SERIAL,PTTYPE,FSTYPE,LABEL,UUID,MOUNTPOINTS"
    devices = json.loads(run("lsblk", "--tree", "--bytes", "--json", "--output", fields))["blockdevices"]
    planned = []
    for spec in specs:
        disk = matching_disk(spec, devices)
        destination = Path(spec["mount"])
        if destination.resolve() != destination:
            raise ValueError(f"Punto de montaje indirecto: {destination}")
        mounted = subprocess.run(["findmnt", "-n", "-o", "UUID", "--mountpoint", str(destination)],
                                 text=True, stdout=subprocess.PIPE, check=False)
        if mounted.returncode == 0:
            if not disk["uuid"] or mounted.stdout.strip() != disk["uuid"]:
                raise ValueError(f"{destination} ya pertenece a otro dispositivo")
        elif mounted.returncode != 1 or (destination.exists() and (not destination.is_dir() or any(destination.iterdir()))):
            raise ValueError(f"Directorio ocupado o inaccesible: {destination}")
        signatures = json.loads(run("wipefs", "--no-act", "--json", "--output", "TYPE", disk["path"]))
        format_disk = needs_format(spec, disk, {row["type"] for row in signatures["signatures"]})
        fstab_entry(fstab, disk, str(destination))
        planned.append((spec, disk, format_disk, mounted.returncode == 0))
    return planned


def prepare(apply):
    specs = json.loads(CONFIG.read_text())
    fstab_path = Path("/etc/fstab")
    original = fstab_path.read_text()
    run("udevadm", "settle")
    disks = inspect(specs, original)
    additions = []
    for spec, disk, format_disk, mounted in disks:
        print(f"{spec['serial']} {disk['path']} -> {spec['mount']}: "
              f"formatear={format_disk} montado={mounted}", flush=True)
        if not apply:
            continue
        if format_disk:
            run("mkfs.xfs", "-L", spec["serial"], disk["path"])
            disk["uuid"] = run("blkid", "-p", "-s", "UUID", "-o", "value", disk["path"]).strip()
        if not disk["uuid"]:
            raise ValueError("UUID ausente")
        additions.append(fstab_entry(original, disk, spec["mount"]))
        Path(spec["mount"]).mkdir(mode=0o755, parents=True, exist_ok=True)
    if not apply:
        return
    if any(additions):
        if fstab_path.read_text() != original:
            raise ValueError("fstab cambió durante la revisión")
        with tempfile.NamedTemporaryFile(mode="w", dir=fstab_path.parent, delete=False) as tmp:
            tmp.write(original.rstrip("\n") + "\n" + "".join(additions))
            os.fchmod(tmp.fileno(), fstab_path.stat().st_mode & 0o777)
        os.replace(tmp.name, fstab_path)
        run("systemctl", "daemon-reload")
    for spec, disk, _, mounted in disks:
        if not mounted:
            run("mount", spec["mount"])
        if run("findmnt", "-n", "-o", "UUID", "--mountpoint", spec["mount"]).strip() != disk["uuid"]:
            raise ValueError(f"UUID inesperado tras montar {spec['mount']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="crear XFS y montar tras revisar los dos discos")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, "Se requiere root dentro de la VM de MinIO.\n")
    try:
        with open("/run/lock/lago-minio-volumes.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            prepare(args.apply)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Volumes: {exc}\n")
