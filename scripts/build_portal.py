#!/usr/bin/env python3
"""Construye una copia estática y autónoma del portal académico."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

REPO = Path(__file__).resolve().parents[1]
MATRIX = "REQUIREMENTS_MATRIX.csv"
INVENTORY = "infrastructure/proxmox/inventory.json"
MARKER = ".portal-generado"
GENERATED = ("index.html", "assets", "archivos", MARKER)
MATRIX_COLUMNS = {
    "id", "pagina_pdf", "momento", "requisito", "tecnologia", "obligatoriedad",
    "metodo_implementacion", "criterio_aceptacion", "archivo_asociado",
    "evidencia_asociada", "estado", "limitaciones", "observaciones",
}
PUBLIC_ROOTS = ("docs/block-00", "docs/moment-01", "architecture", "evidence")
EXTENSIONS = {
    ".md", ".txt", ".csv", ".tsv", ".json", ".log", ".svg", ".png", ".jpg",
    ".dot", ".mmd", ".conf", ".cfg", ".yml", ".yaml", ".pdf", ".docx", ".sha256",
}
CODE_EXT = EXTENSIONS | {".py", ".sh", ".service", ".template", ".tmpl", ".rules", ".ini", ".toml", ".j2"}
TITLES = {
    MATRIX: "Matriz de trazabilidad",
    INVENTORY: "Inventario de las máquinas virtuales",
    "ARCHITECTURE_DECISIONS.md": "Decisiones de arquitectura",
    "EVIDENCE_INDEX.md": "Índice de evidencias",
    "arquitectura": "Arquitectura de la plataforma", "red": "Topología de red",
    "flujo": "Flujo del lago de datos", "informe": "Informe del Momento 1",
    "administracion": "Manual de administración", "instalacion": "Manual de instalación",
    "sustentacion": "Guía de sustentación",
}
TEXT_PREVIEW = {".md", ".txt", ".sha256", ".csv", ".tsv", ".json", ".log", ".cfg", ".yaml", ".yml", ".conf", ".dot", ".mmd"}


def files_in(root, folder, extensions):
    base = root / folder
    if not base.exists():
        return
    for file in sorted(base.rglob("*")):
        rel = file.relative_to(root)
        if any(part.startswith(".") or part in {"__pycache__", "node_modules", "work"} for part in rel.parts):
            continue
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(root):
            continue
        if file.suffix.lower() in extensions:
            yield file


def title(path, text):
    if path.as_posix() in TITLES:
        return TITLES[path.as_posix()]
    if path.suffix == ".md" and text:
        for line in text.splitlines()[:12]:
            if line.startswith("# "):
                return line[2:].strip()
    return TITLES.get(path.stem, path.stem.replace("_", " ").replace("-", " ").capitalize())


def classify(path):
    if path.parts[0] == "evidence":
        return "Evidencia"
    if path.parts[:2] == ("architecture", "diagrams"):
        return "Diagrama"
    if path.parts[0] in {"architecture", "infrastructure"}:
        return "Infraestructura"
    if path.parts[:2] == ("docs", "block-00") or path.as_posix() == MATRIX:
        return "Bloque 0"
    return "Documento"


def record(staging, rel, category):
    file = staging / "archivos" / rel
    extension = rel.suffix.lower()
    raw = file.read_bytes()
    preview = raw[:24000].decode("utf-8", errors="replace") if extension in TEXT_PREVIEW else ""
    return {
        "path": rel.as_posix(), "url": "archivos/" + rel.as_posix(),
        "title": title(rel, preview), "kind": category, "format": extension[1:].upper(),
        "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "preview": preview, "truncated": bool(preview) and len(raw) > 24000,
    }


def configuration_archive(root, out):
    # Únicamente código de infraestructura versionable. Secretos y estados locales quedan fuera.
    files = []
    for base in ("infrastructure", "tests/minio", "tests/infra", "tests/kubernetes"):
        files.extend(files_in(root, base, CODE_EXT))
    if not files:
        return False
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(files):
            relative = file.relative_to(root).as_posix()
            member = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            member.external_attr = (0o755 if file.suffix in {".sh", ".py"} else 0o644) << 16
            archive.writestr(member, file.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    return True


def build(root, staging):
    with (root / MATRIX).open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        if set(rows.fieldnames or ()) != MATRIX_COLUMNS:
            raise ValueError(f"Encabezados inesperados en {MATRIX}: {rows.fieldnames}")
        requirements = list(rows)
    if not requirements or len({r["id"] for r in requirements}) != len(requirements):
        raise ValueError("La matriz debe incluir requisitos con identificadores únicos.")
    inventory = json.loads((root / INVENTORY).read_text(encoding="utf-8"))
    if not inventory.get("vms") or "network" not in inventory:
        raise ValueError(f"Inventario incompleto: {INVENTORY}")

    shutil.copyfile(root / "portal/index.html", staging / "index.html")
    shutil.copytree(root / "portal/assets", staging / "assets")
    (staging / "archivos").mkdir()
    files = {root / MATRIX, root / INVENTORY}
    for named in ("ARCHITECTURE_DECISIONS.md", "EVIDENCE_INDEX.md"):
        if (root / named).is_file():
            files.add(root / named)
    for base in PUBLIC_ROOTS:
        files.update(files_in(root, base, EXTENSIONS))
    catalog = []
    for file in sorted(files):
        rel = file.relative_to(root)
        target = staging / "archivos" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
        catalog.append(record(staging, rel, classify(rel)))

    bundle = Path("configuracion-momento-1.zip")
    if configuration_archive(root, staging / "archivos" / bundle):
        asset = record(staging, bundle, "Infraestructura")
        asset["title"] = "Configuración y pruebas del Momento 1"
        catalog.append(asset)
    model = {"requirements": requirements, "inventory": inventory, "files": catalog}
    # Se usa un script externo clásico para que la consulta por file:// no necesite fetch ni CORS.
    (staging / "assets/data.js").write_text(
        "window.LAGO = " + json.dumps(model, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    (staging / MARKER).write_text("portal-estatico-v1\n", encoding="utf-8")
    return len(catalog)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destino", type=Path, help="Directorio para la salida estática")
    args = parser.parse_args()
    dest = args.destino.resolve()
    if args.destino.is_symlink() or dest == REPO or dest in REPO.parents:
        parser.error("Ruta de salida incompatible con el repositorio.")
    for reserved in ("portal", "scripts", "docs", "architecture", "infrastructure", "tests", "evidence", ".git"):
        if dest.is_relative_to(REPO / reserved):
            parser.error(f"La salida no puede escribirse dentro de {reserved}/.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (not dest.is_dir() or (
        any(dest.iterdir()) and (not (dest / MARKER).is_file() or
                                 (dest / MARKER).read_text() != "portal-estatico-v1\n")
    )):
        parser.error("La salida debe estar vacía o ser una copia generada por este comando.")
    with tempfile.TemporaryDirectory(prefix=".portal-build-", dir=dest.parent) as tmp:
        staging = Path(tmp)
        count = build(REPO, staging)
        dest.mkdir(exist_ok=True)
        for name in GENERATED:
            target = dest / name
            if target.is_symlink():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
            (staging / name).replace(target)
    print(f"Portal construido: {dest} ({count} archivos consultables).")


if __name__ == "__main__":
    main()
