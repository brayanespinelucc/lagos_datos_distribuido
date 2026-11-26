#!/usr/bin/env python3
"""Prepara y provisiona las VM del Momento 1 desde un nodo Proxmox VE."""
import argparse
from collections import Counter
import csv
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys

HERE = Path(__file__).resolve().parent
UBUNTU = HERE.parent / "ubuntu"
NETWORK = HERE.parents[1] / "architecture" / "network"
ROLES = {"minio-lb": 1, "rke2-lb": 1, "minio": 3, "rke2-server": 1, "rke2-worker": 2}


def read_inventory():
    data = json.loads((HERE / "inventory.json").read_text())
    validate_inventory(data)
    return data


def validate_inventory(data):
    net = data["network"]
    lan, pods, services = [ipaddress.IPv4Network(net[key]) for key in ("cidr", "pod_cidr", "service_cidr")]
    if lan.overlaps(pods) or lan.overlaps(services) or pods.overlaps(services):
        raise ValueError("Los tres segmentos deben ser disjuntos")
    admin = ipaddress.IPv4Network(net["admin_cidr"])
    gateway = ipaddress.IPv4Address(net["gateway"])
    host = ipaddress.IPv4Address(net["proxmox_ip"])
    ipaddress.IPv4Address(net["dns"])
    if gateway not in lan or host not in lan or host == gateway or admin.prefixlen == 0:
        raise ValueError("Revisar el gateway, host de Proxmox y la red de gestión")
    machines = data["vms"]
    if Counter(vm["role"] for vm in machines) != ROLES:
        raise ValueError("Se requieren dos balanceadores, tres MinIO y tres nodos RKE2")
    for key in ("id", "ip", "hostname"):
        if len({vm[key] for vm in machines}) != len(machines):
            raise ValueError(f"Valor duplicado en {key}")
    serials = set()
    for vm in machines:
        ip = ipaddress.IPv4Address(vm["ip"])
        if ip not in lan or ip in {lan.network_address, lan.broadcast_address, gateway, host}:
            raise ValueError(f"Dirección inválida para {vm['hostname']}")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,61}[a-z0-9]", vm["hostname"]):
            raise ValueError("Hostname inválido")
        if not 100 <= vm["id"] <= 999999999 or min(vm[k] for k in ("vcpus", "memory_mib", "os_disk_gib")) <= 0:
            raise ValueError("ID o capacidad de VM inválidos")
        disks = vm["data_disks"]
        expected = 2 if vm["role"] == "minio" else 0
        if len(disks) != expected:
            raise ValueError(f"Cantidad de discos de datos incorrecta para {vm['hostname']}")
        for index, disk in enumerate(disks, 1):
            serial = disk["serial"]
            if disk["slot"] != f"scsi{index}" or disk["mount"] != f"/srv/minio/disk{index}":
                raise ValueError("Slot o destino de montaje imprevisto")
            if not re.fullmatch(r"[A-Za-z0-9]{1,12}", serial) or serial in serials or disk["size_gib"] < 1:
                raise ValueError("Serial XFS duplicado/inválido o capacidad insuficiente")
            serials.add(serial)


def groups(data):
    vms = data["vms"]
    members = {role: [vm["ip"] for vm in vms if vm["role"] == role] for role in ROLES}
    members.update(vms=[vm["ip"] for vm in vms], admin=[data["network"]["admin_cidr"]],
                   rke2=members["rke2-server"] + members["rke2-worker"])
    return members


def firewall(data, vm):
    members = groups(data)
    lines = ["# Generado a partir de architecture/network/communication.csv",
             "[OPTIONS]", "enable: 1", "policy_in: DROP", "policy_out: ACCEPT", "", "[RULES]"]
    with (NETWORK / "communication.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            if vm["ip"] not in members.get(row["destination"], []):
                continue
            for src in members[row["source"]]:
                for port in row["ports"].split("|"):
                    protocol = row["protocol"]
                    if protocol not in {"icmp", "tcp", "udp"} or (port and not 0 < int(port) <= 65535):
                        raise ValueError("Regla de firewall inválida")
                    rule = f"IN ACCEPT -source {src} -p {protocol}"
                    lines.append(f"{rule} -dport {port}" if port else rule)
    return "\n".join(lines) + "\n"


def cloud_config(data, vm, key):
    net = data["network"]
    config = json.loads((UBUNTU / "base-cloud-config.json").read_text())
    config.update(hostname=vm["hostname"], fqdn=f"{vm['hostname']}.{net['domain']}")
    config["users"][0]["ssh_authorized_keys"] = [key]
    hosts = ["127.0.0.1 localhost", "::1 localhost ip6-localhost ip6-loopback",
             f"{net['proxmox_ip']} pve.{net['domain']} pve"]
    for peer in data["vms"]:
        line = f"{peer['ip']} {peer['hostname']}.{net['domain']} {peer['hostname']}"
        if peer["role"] == "rke2-lb":
            line += " " + net["ingress_host"]
        hosts.append(line)
    config["write_files"].append({"path": "/etc/hosts", "permissions": "0644", "content": "\n".join(hosts) + "\n"})
    if vm["data_disks"]:
        config["packages"].append("xfsprogs")
        config["write_files"].extend([
            {"path": "/etc/lago/minio-disks.json", "permissions": "0644", "content": json.dumps(vm["data_disks"])},
            {"path": "/usr/local/sbin/lago-volumes", "permissions": "0755",
             "content": (UBUNTU / "prepare_volumes.py").read_text()},
        ])
        config["runcmd"].append(["/usr/local/sbin/lago-volumes", "--apply"])
    return "#cloud-config\n" + json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def read_public_key(path):
    fields = path.read_text().strip().splitlines()
    if len(fields) != 1:
        raise ValueError("Se requiere una única llave SSH pública de OpenSSH")
    parts = fields[0].split()
    if len(parts) < 2 or not parts[0].startswith(("ssh-ed25519", "ecdsa-sha2-", "ssh-rsa", "sk-")):
        raise ValueError("Formato de llave pública OpenSSH desconocido")
    subprocess.run(["ssh-keygen", "-l", "-f", str(path)], check=True, stdout=subprocess.DEVNULL)
    return " ".join(parts[:2])


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def artifacts(data, vm, key):
    cloud = cloud_config(data, vm, key)
    filename = f"lago-{vm['id']}-{digest(cloud)[:16]}.yaml"
    return filename, cloud, firewall(data, vm)


def write_new_or_equal(path, content, write=True):
    if path.is_symlink():
        raise ValueError(f"Ruta indirecta: {path}")
    if path.exists():
        if path.read_text() != content:
            raise ValueError(f"Archivo existente con contenido distinto: {path}")
        return
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as output:
            output.write(content)


def vm_args(data, vm, image, storage, snippet, marker):
    net = data["network"]
    prefix = ipaddress.IPv4Network(net["cidr"]).prefixlen
    args = ["qm", "create", str(vm["id"]), "--name", vm["hostname"], "--cores", str(vm["vcpus"]),
            "--memory", str(vm["memory_mib"]), "--ostype", "l26", "--cpu", "host", "--scsihw", "virtio-scsi-single",
            "--net0", f"virtio,bridge={net['bridge']},firewall=1", "--agent", "enabled=1", "--serial0", "socket",
            "--vga", "serial0", "--scsi0", f"{storage}:0,import-from={image}", "--ide2", f"{storage}:cloudinit",
            "--boot", "order=scsi0", "--ipconfig0", f"ip={vm['ip']}/{prefix},gw={net['gateway']}",
            "--nameserver", net["dns"], "--searchdomain", net["domain"], "--cicustom", f"user={snippet}",
            "--onboot", "1", "--tags", "lago-m1", "--description", marker]
    for disk in vm["data_disks"]:
        args.extend(["--" + disk["slot"], f"{storage}:{disk['size_gib']},serial={disk['serial']}"])
    return args


def plan(data):
    vms = data["vms"]
    return {"mode": "plan local sin operaciones sobre Proxmox", "image": data["image"], "network": data["network"],
            "totals": {"vms": len(vms), "vcpus": sum(vm["vcpus"] for vm in vms),
                       "memory_mib": sum(vm["memory_mib"] for vm in vms),
                       "os_disk_gib": sum(vm["os_disk_gib"] for vm in vms),
                       "data_disk_gib": sum(d["size_gib"] for vm in vms for d in vm["data_disks"])},
            "vms": [dict(vm, inbound_rules=firewall(data, vm).count("IN ACCEPT")) for vm in vms]}


def pve_get(endpoint, *args):
    raw = subprocess.check_output(["pvesh", "get", endpoint, *args, "--output-format", "json"], text=True)
    return json.loads(raw)


def size_gib(device_config):
    match = re.search(r"(?:^|,)size=([0-9]+(?:\.[0-9]+)?)([KMGTP])(?:,|$)", device_config)
    if not match:
        raise ValueError(f"Tamaño ausente en la configuración de disco: {device_config}")
    return float(match[1]) * 1024 ** ("KMGTP".index(match[2]) - 2)


def check_owned_vm(config, data, vm, marker, storage, snippet):
    net = data["network"]
    expected_ip = f"ip={vm['ip']}/{ipaddress.IPv4Network(net['cidr']).prefixlen},gw={net['gateway']}"
    if config.get("description", "").strip() != marker:
        raise ValueError(f"ID {vm['id']} ya ocupado o definición modificada; se conserva")
    expected = {"name": vm["hostname"], "memory": str(vm["memory_mib"]), "cores": str(vm["vcpus"]),
                "cicustom": f"user={snippet}", "nameserver": net["dns"], "searchdomain": net["domain"],
                "scsihw": "virtio-scsi-single"}
    for key, value in expected.items():
        if str(config.get(key)) != value:
            raise ValueError(f"Deriva en ID {vm['id']}, campo {key}")
    connection = set(config.get("net0", "").split(","))
    if set(config.get("ipconfig0", "").split(",")) != set(expected_ip.split(",")) or not {
            f"bridge={net['bridge']}", "firewall=1"} <= connection:
        raise ValueError(f"Deriva en la red de ID {vm['id']}")
    if not config.get("scsi0", "").startswith(storage + ":") or not config.get("ide2", "").startswith(storage + ":"):
        raise ValueError(f"Deriva en el almacenamiento de ID {vm['id']}")
    for disk in vm["data_disks"]:
        partition = config.get(disk["slot"], "")
        if (not partition.startswith(storage + ":") or f"serial={disk['serial']}" not in partition.split(",")
                or size_gib(partition) != disk["size_gib"]):
            raise ValueError(f"Deriva en el disco {disk['slot']} de ID {vm['id']}")
    if size_gib(config["scsi0"]) > vm["os_disk_gib"]:
        raise ValueError(f"El disco SO de ID {vm['id']} supera el inventario")


def require_pve():
    missing = [cmd for cmd in ("pveversion", "qm", "pvesh", "pvesm", "qemu-img") if not shutil.which(cmd)]
    if missing or not Path("/dev/kvm").exists() or not Path("/etc/pve").is_dir() or os.geteuid():
        raise ValueError("Este modo requiere un host Proxmox VE con KVM, /etc/pve y root; "
                         "herramientas ausentes: " + ", ".join(missing))


def apply(data, args, key):
    net = data["network"]
    node = socket.gethostname().split(".")[0]
    root = f"/nodes/{node}"
    if not Path("/sys/class/net", net["bridge"], "bridge").is_dir():
        raise ValueError(f"Falta el bridge Linux {net['bridge']}")
    if not int(pve_get("/cluster/firewall/options").get("enable", 0)):
        raise ValueError("La política de firewall de Datacenter debe estar habilitada")
    local_storage = {s["storage"]: s for s in pve_get(root + "/storage")}
    for name, content in [(args.storage, "images"), (args.snippets, "snippets")]:
        store = local_storage.get(name, {})
        if not store.get("active") or content not in store.get("content", "").split(","):
            raise ValueError(f"Storage inactivo o sin contenido {content}: {name}")
    image = args.image.resolve(strict=True)
    if not image.is_file() or "," in str(image):
        raise ValueError("Se requiere un archivo local sin comas en la ruta")
    pinned = data["image"]["sha256"]
    if args.sha256 and args.sha256.lower() != pinned:
        raise ValueError("El SHA-256 suministrado difiere de la edición fijada en el inventario")
    with image.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != pinned:
            raise ValueError("SHA-256 de la imagen incorrecto")
    metadata = json.loads(subprocess.check_output(["qemu-img", "info", "--output=json", str(image)], text=True))
    if metadata["format"] != "qcow2" or metadata.get("backing-filename"):
        raise ValueError("Se requiere la imagen QCOW2 de Ubuntu autocontenida")
    if metadata["virtual-size"] > min(vm["os_disk_gib"] for vm in data["vms"]) * 1024**3:
        raise ValueError("La imagen excede el disco de sistema más pequeño")
    occupied = {int(m["vmid"]): m for m in pve_get("/cluster/resources", "--type", "vm")}
    deployments = []
    for vm in data["vms"]:
        vmid = vm["id"]
        filename, cloud, fw = artifacts(data, vm, key)
        snippet = f"{args.snippets}:snippets/{filename}"
        path = Path(subprocess.check_output(["pvesm", "path", snippet], text=True).strip())
        fwpath = Path(f"/etc/pve/firewall/{vmid}.fw")
        signature = digest(json.dumps([vm, net, pinned, args.storage, snippet, digest(fw)], sort_keys=True))
        marker = f"lago-m1 {signature}"
        exists = vmid in occupied
        if exists:
            resource = occupied[vmid]
            if resource["type"] != "qemu" or resource["node"] != node:
                raise ValueError(f"ID {vmid} pertenece a otro recurso")
            check_owned_vm(pve_get(f"{root}/qemu/{vmid}/config"), data, vm, marker, args.storage, snippet)
        write_new_or_equal(path, cloud, write=False)
        write_new_or_equal(fwpath, fw, write=False)
        deployments.append((vm, exists, path, cloud, fwpath, fw, vm_args(data, vm, image, args.storage, snippet, marker)))
    if args.preflight_only:
        print(f"Preflight correcto para {node}. Máquinas revisadas: {len(deployments)}.")
        return
    for vm, exists, path, cloud, fwpath, fw, command in deployments:
        write_new_or_equal(path, cloud)
        write_new_or_equal(fwpath, fw)
        vmid = str(vm["id"])
        if not exists:
            subprocess.run(command, check=True)
        config = pve_get(f"{root}/qemu/{vmid}/config")
        if size_gib(config["scsi0"]) < vm["os_disk_gib"]:
            subprocess.run(["qm", "resize", vmid, "scsi0", f"{vm['os_disk_gib']}G"], check=True)
        state = pve_get(f"{root}/qemu/{vmid}/status/current")["status"]
        if state == "stopped":
            subprocess.run(["qm", "start", vmid], check=True)
        elif state != "running":
            raise ValueError(f"ID {vmid} en estado inesperado: {state}")
        print(f"VM {vmid} {vm['hostname']} configurada; comprobar cloud-init dentro del invitado.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    commands.add_parser("plan", help="inventario, recursos y reglas; no necesita Proxmox ni llaves")
    render = commands.add_parser("render", help="exporta cloud-init y firewall a un directorio de trabajo")
    render.add_argument("--ssh-key", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    install = commands.add_parser("apply", help="provisiona en un nodo PVE autorizado")
    install.add_argument("--ssh-key", type=Path, required=True)
    install.add_argument("--image", type=Path, required=True)
    install.add_argument("--sha256")
    install.add_argument("--storage", default="local-lvm")
    install.add_argument("--snippets", default="local")
    install.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    try:
        data = read_inventory()
        if args.mode == "plan":
            print(json.dumps(plan(data), indent=2, ensure_ascii=False))
            return
        if args.mode == "apply":
            require_pve()
        key = read_public_key(args.ssh_key)
        if args.mode == "render":
            for vm in data["vms"]:
                filename, cloud, fw = artifacts(data, vm, key)
                write_new_or_equal(args.output / filename, cloud)
                write_new_or_equal(args.output / f"{vm['id']}.fw", fw)
            print(f"Escritos o comprobados {2 * len(data['vms'])} archivos en {args.output}.")
            return
        with open("/run/lock/lago-m1-provision.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            apply(data, args, key)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
