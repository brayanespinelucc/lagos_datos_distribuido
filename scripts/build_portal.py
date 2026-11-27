#!/usr/bin/env python3
"""Construye una copia estática y autónoma del portal académico."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile
from urllib.parse import urlparse

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
PUBLIC_ROOTS = (
    "docs/block-00", "docs/moment-01", "docs/moment-02", "docs/moment-03", "docs/final", "docs/entrega",
    "architecture", "evidence", "presentation", "video", "monitoring", "sql/queries",
    "results/sql", "results/catalog", "services/airflow/dags", "services/monitoring",
)
MEDIA_LIMIT = 24 * 1024 * 1024
EXTENSIONS = {
    ".md", ".txt", ".csv", ".tsv", ".json", ".log", ".svg", ".png", ".jpg",
    ".dot", ".mmd", ".conf", ".cfg", ".yml", ".yaml", ".pdf", ".docx", ".sha256",
    ".sql", ".srt", ".vtt", ".pptx", ".mp4", ".py", ".jsonl",
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
    "docs/final/entrega/informe-final.pdf": "Informe técnico consolidado",
    "presentation/sustentacion.pdf": "Presentación de sustentación",
    "presentation/sustentacion.pptx": "Presentación editable",
    "video/sustentacion.mp4": "Video de sustentación",
    "video/guion.md": "Guion de la sustentación", "video/storyboard.csv": "Secuencia de escenas",
    "video/subtitulos.srt": "Subtítulos en español",
}
TEXT_PREVIEW = {".md", ".txt", ".sha256", ".csv", ".tsv", ".json", ".log", ".cfg", ".yaml", ".yml", ".conf", ".dot", ".mmd", ".sql", ".py", ".srt", ".vtt"}


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
    if path.parts[0] == "datasets":
        return "Datos"
    if path.parts[0] in {"presentation", "video"}:
        return "Sustentación"
    if path.parts[0] == "monitoring":
        return "Monitoreo"
    if path.parts[0] == "sql" or path.parts[:2] == ("results", "sql"):
        return "SQL"
    if path.parts[:2] == ("results", "catalog"):
        return "Gobierno"
    if path.parts[0] == "services":
        return "Procesamiento"
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


def read_json(root, path, fallback):
    target = root / path
    return json.loads(target.read_text(encoding="utf-8")) if target.is_file() else fallback


def lake_files(root, lake):
    for table in lake.get("tables", []):
        for item in table.get("files", []):
            rel = Path(item["path"])
            if rel.is_absolute() or ".." in rel.parts or rel.parts[:1] != ("datasets",):
                raise ValueError(f"Ruta de dataset no válida: {rel}")
            file = root / rel
            if not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(root):
                raise ValueError(f"Falta archivo físico del lago: {rel}")
            if item.get("sha256") and hashlib.sha256(file.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError(f"Huella de dataset distinta del manifiesto: {rel}")
            yield file


def sql_index(root):
    index = read_json(root, "results/sql/index.json", {})
    for query in index.get("queries", []):
        rel = Path(query["csv"])
        if rel.is_absolute() or ".." in rel.parts or rel.parts[:2] != ("results", "sql"):
            raise ValueError(f"Ruta de resultado SQL no válida: {rel}")
        if not (root / rel).is_file():
            continue
        with (root / rel).open(encoding="utf-8-sig", newline="") as stream:
            table = csv.DictReader(stream)
            query["columns"] = table.fieldnames or []
            query["preview"] = []
            for row in table:
                query["preview"].append(row)
                if len(query["preview"]) >= 40:
                    break
    return index


def build(root, staging, video_url=None):
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
    for named in ("README.md", "PROJECT_STATE.md", "ARCHITECTURE_DECISIONS.md", "EVIDENCE_INDEX.md", "Lago de Datos Distribuido.pdf"):
        if (root / named).is_file():
            files.add(root / named)
    for base in PUBLIC_ROOTS:
        files.update(files_in(root, base, EXTENSIONS))
    lake = read_json(root, "results/lake.json", {"tables":[]})
    files.update(lake_files(root, lake))
    catalog = []
    for file in sorted(files):
        if file.stat().st_size > MEDIA_LIMIT:
            if file.suffix.lower() == ".mp4":
                continue
            raise ValueError(f"Archivo superior al límite de publicación: {file.relative_to(root)}")
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
    model = {
        "requirements": requirements, "inventory": inventory, "files": catalog, "lake": lake,
        "sql": sql_index(root), "catalog": read_json(root, "evidence/moment-02/datahub/catalog.json", {}),
        "videoUrl": video_url,
        "metrics": read_json(root, "evidence/moment-03/monitoreo/p6.json", {}),
    }
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
    parser.add_argument("--video-url", help="URL HTTPS de una copia del video ya publicada y verificada")
    args = parser.parse_args()
    if args.video_url and (urlparse(args.video_url).scheme != "https" or not urlparse(args.video_url).hostname):
        parser.error("El enlace al video debe ser una URL HTTPS válida.")
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
        count = build(REPO, staging, args.video_url)
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
