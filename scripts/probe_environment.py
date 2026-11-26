#!/usr/bin/env python3
"""Registra capacidades observadas. Las pruebas activas se ejecutan solo al solicitarlas."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {
    "python3": ["--version"], "pip3": ["--version"], "git": ["--version"],
    "docker": ["--version"], "podman": ["--version"], "kubectl": ["version", "--client"],
    "helm": ["version", "--short"], "rke2": ["--version"], "kind": ["version"],
    "pveversion": [], "qm": ["help"], "kvm": ["--version"], "qemu-system-x86_64": ["--version"],
    "cloud-init": ["--version"], "java": ["-version"], "javac": ["-version"],
    "node": ["--version"], "npm": ["--version"], "go": ["version"],
    "haproxy": ["-v"], "minio": ["--version"], "mc": ["--version"],
    "make": ["--version"], "dot": ["-V"], "pandoc": ["--version"],
    "pdftotext": ["-v"], "pdftoppm": ["-v"], "pdfinfo": ["-v"], "libreoffice": ["--version"],
    "ffmpeg": ["-version"], "ffprobe": ["-version"], "espeak": ["--version"],
    "espeak-ng": ["--version"], "chromium": ["--version"],
}
PACKAGES = ["PyYAML", "jsonschema", "python-docx", "python-pptx", "reportlab",
            "pypdf", "Pillow", "playwright", "matplotlib", "pyarrow", "pyspark"]


def run(args, timeout=12):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                                cwd=ROOT, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        lines = (result.stdout.strip() or result.stderr.strip()).splitlines()
        return {"codigo": result.returncode, "salida": lines[:3]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"codigo": None, "salida": [type(exc).__name__]}


def file_value(path):
    return path.read_text().strip() if path.is_file() else None


def https_status(url):
    try:
        with urlopen(url, timeout=10) as response:
            return response.status
    except HTTPError as exc:
        return exc.code
    except OSError as exc:
        return type(exc).__name__


def diagnose(active):
    disk = shutil.disk_usage(ROOT)
    probe = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sistema": platform.freedesktop_os_release().get("PRETTY_NAME"),
        "arquitectura": platform.machine(), "kernel": platform.release(),
        "uid_efectivo": os.geteuid(), "cpu_visibles": os.cpu_count(),
        "cpu_afinidad": len(os.sched_getaffinity(0)),
        "cgroup_cpu_max": file_value(Path("/sys/fs/cgroup/cpu.max")),
        "cgroup_memoria_max_bytes": file_value(Path("/sys/fs/cgroup/memory.max")),
        "memoria_host_kib": int(Path("/proc/meminfo").read_text().splitlines()[0].split()[1]),
        "almacenamiento": {"total_bytes": disk.total, "libre_bytes": disk.free},
        "pid1": file_value(Path("/proc/1/comm")), "dispositivo_kvm": Path("/dev/kvm").exists(),
        "sudo_disponible": bool(shutil.which("sudo")),
        "herramientas_en_path": {}, "paquetes_python": {},
        "persistencia": "Procesos y discos del laboratorio limitados a la sesión. La conservación se realiza por Git y archivos exportados.",
    }
    for command, flags in COMMANDS.items():
        probe["herramientas_en_path"][command] = run([command, *flags]) if shutil.which(command) else None
    for package in PACKAGES:
        try:
            probe["paquetes_python"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            probe["paquetes_python"][package] = None
    if active:
        tests = probe["pruebas_activas"] = {}
        endpoint = ["docker", "--host=unix:///var/run/docker.sock"]
        if shutil.which("docker"):
            tests["docker_server"] = run(endpoint + ["info", "--format", "{{.ServerVersion}} {{json .SecurityOptions}}"])
            tests["docker_compose"] = run(endpoint + ["compose", "version"])
            tests["imagen_local_hola"] = run(endpoint + ["image", "inspect", "hello-world:latest", "--format", "{{json .RepoDigests}}"])
            tests["contenedor_efimero"] = run(endpoint + ["run", "--rm", "--pull=never", "--network", "none",
                                                        "--read-only", "--cap-drop", "ALL", "hello-world:latest"])
        tests["https"] = {url: https_status(url) for url in ["https://pypi.org/simple/", "https://gitlab.com/"]}
        tests["git_main"] = run(["git", "ls-remote", "origin", "refs/heads/main"])
        with socket.socket() as listener, socket.socket() as client:
            listener.settimeout(4)
            client.settimeout(4)
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            client.connect(listener.getsockname())
            connection, _ = listener.accept()
            with connection:
                client.sendall(b"lago")
                tests["tcp_loopback"] = connection.recv(4) == b"lago"
        tests["archivo_descargable"] = "Ver manifiesto y prueba de integridad del paquete del corte."
    return probe


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--active", action="store_true", help="Probar red, Git y una imagen local aislada")
    args = parser.parse_args()
    json.dump(diagnose(args.active), sys.stdout, indent=2, ensure_ascii=False)
    print()
