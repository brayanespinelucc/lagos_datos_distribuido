#!/usr/bin/env python3
"""Compila las fuentes Markdown de M1 como Word y PDF e inspecciona la paginación.

Herramientas: Pandoc, LibreOffice (soffice), python-docx y PyMuPDF.
Todos los borradores se generan en un directorio temporal antes de la copia final.
"""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from zipfile import ZipFile

import docx
import pymupdf
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/moment-01"
SOURCE_DIRECTORIES = {"informe":"moment-01", "arquitectura":"moment-01", "instalacion":"moment-01",
    "administracion":"moment-01", "sustentacion":"moment-01", "informe-m2":"moment-02", "lago":"moment-02",
    "gobierno":"moment-02", "diccionario":"moment-02", "catalogo":"moment-02", "dag":"moment-02",
    "informe-m3":"moment-03", "operacion":"moment-03", "monitoreo":"moment-03", "recuperacion":"moment-03",
    "buenas-practicas":"moment-03", "pruebas":"moment-03", "informe-final":"final", "preguntas":"final"}
PROJECT = "Diseño e Implementación de una Plataforma Empresarial para un Lago de Datos Distribuido"
META = {
    "informe": ("Informe del Momento 1", "Resultados y alcance de la infraestructura base"),
    "arquitectura": ("Documento de arquitectura", "Componentes, dependencias y dominios de fallo"),
    "instalacion": ("Manual de instalación", "Preparación de las máquinas virtuales y puesta en servicio"),
    "administracion": ("Manual de administración", "Controles operativos, diagnóstico y recuperación"),
    "sustentacion": ("Guía de sustentación", "Recorrido para presentar y verificar el primer momento"),
    "informe-m2": ("Informe del Momento 2", "Ingesta, transformación, consulta y gobierno"),
    "lago": ("Manual del lago de datos", "Del primer archivo de ventas a los indicadores"),
    "gobierno": ("Manual de gobierno de datos", "Catálogo, responsables, clasificación y linaje"),
    "diccionario": ("Diccionario de datos", "Definición de campos y reglas por conjunto"),
    "catalogo": ("Catálogo de datos", "Localización y responsabilidades de los conjuntos"),
    "dag": ("Documentación del DAG", "Orquestación, dependencias y diagnóstico de la carga"),
    "informe-m3": ("Informe del Momento 3", "Monitoreo, operación y pruebas de recuperación"),
    "operacion": ("Manual de operación", "Secuencia de trabajo y conservación de evidencias"),
    "monitoreo": ("Manual de monitoreo", "Indicadores, dashboards y lectura de incidentes"),
    "recuperacion": ("Manual de recuperación", "Pérdida de nodos y verificación de los datos"),
    "buenas-practicas": ("Manual de buenas prácticas", "Controles de operación y calidad de la entrega"),
    "pruebas": ("Informe de las seis pruebas", "Resultados, precondiciones y procedimientos de repetición"),
    "informe-final": ("Informe técnico consolidado", "Diseño, implementación, resultados y límites de los tres momentos"),
    "preguntas": ("Banco de sustentación", "Sesenta preguntas con respuestas aplicadas al laboratorio"),
}
NAVY, TEAL, SLATE, DARK, LINE = "132D4C", "006D77", "4E6475", "1F3445", "C9D7DE"
PAPER_WIDTH = 6.8


def color(text):
    return RGBColor.from_string(text)


def xml_tag(name, **attributes):
    node = OxmlElement(f"w:{name}")
    for key, value in attributes.items():
        node.set(qn(f"w:{key}"), str(value))
    return node


def set_font(style, size, shade=DARK, bold=False, family="Open Sans"):
    style.font.name = family
    style.font.size = Pt(size)
    style.font.color.rgb = color(shade)
    style.font.bold = bold


def style_doc(document):
    section = document.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.left_margin = section.right_margin = Inches(0.85)
    section.top_margin, section.bottom_margin = Inches(0.92), Inches(0.83)
    section.header_distance, section.footer_distance = Inches(0.40), Inches(0.39)
    normal = document.styles["Normal"]
    set_font(normal, 10.7)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.14
    normal.paragraph_format.widow_control = True
    for name in ("Body Text", "First Paragraph", "Compact"):
        if name not in document.styles:
            continue
        style = document.styles[name]
        set_font(style, 10.7)
        style.paragraph_format.line_spacing = 1.14
        style.paragraph_format.space_after = Pt(6 if name != "Compact" else 3)
    for level in range(1, 5):
        if f"Heading {level}" not in document.styles:
            continue
        h = document.styles[f"Heading {level}"]
        set_font(h, {1: 21, 2: 17, 3: 12, 4: 11}[level], NAVY if level < 3 else TEAL, True)
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)
        h.paragraph_format.keep_with_next = True
    for name in ("Caption", "Image Caption", "Table Caption"):
        if name in document.styles:
            style = document.styles[name]
            set_font(style, 8.7, SLATE)
            style.font.italic = False
            style.paragraph_format.space_before = Pt(3)
            style.paragraph_format.space_after = Pt(6)
    for name in ("Verbatim Char", "Source Code"):
        if name in document.styles:
            style = document.styles[name]
            set_font(style, 8.4, NAVY, family="DejaVu Sans Mono")
            if style.type == WD_STYLE_TYPE.PARAGRAPH:
                style.paragraph_format.line_spacing = 1.07
                style.paragraph_format.space_before = Pt(4)
                style.paragraph_format.space_after = Pt(6)

    # Pandoc define algunos tamaños con ancho absoluto. Mantener la proporción original.
    for shape in document.inline_shapes:
        scale = min(1, Inches(PAPER_WIDTH - 0.05) / shape.width, Inches(5.0) / shape.height)
        shape.width, shape.height = round(shape.width * scale), round(shape.height * scale)
    for table in document.tables:
        column_widths = [col.width for col in table.columns]
        total = sum(w or 0 for w in column_widths)
        widths = [int(Inches(PAPER_WIDTH) * (w / total if total and w else 1/len(column_widths))) for w in column_widths]
        for col, width in zip(table.columns, widths):
            col.width = width
        for row_number, row in enumerate(table.rows):
            row._tr.get_or_add_trPr().append(xml_tag("cantSplit"))
            if row_number == 0:
                row._tr.get_or_add_trPr().append(xml_tag("tblHeader", val="true"))
            for i, cell in enumerate(row.cells):
                if i < len(widths):
                    cell.width = widths[i]
                cell._tc.get_or_add_tcPr().append(xml_tag("shd", fill=NAVY if row_number == 0 else ("EEF4F6" if row_number % 2 == 1 else "FFFFFF")))
                for p in cell.paragraphs:
                    p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(3)
                    p.paragraph_format.line_spacing = 1.05
                    for run in p.runs:
                        set_font(run, 9.1, "FFFFFF" if row_number == 0 else DARK, bold=row_number == 0)


def band(document, title, context):
    section = document.sections[0]
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    header.paragraph_format.tab_stops.add_tab_stop(Inches(PAPER_WIDTH), WD_TAB_ALIGNMENT.RIGHT)
    set_font(header.add_run("LAGO DE DATOS DISTRIBUIDO"), 8.5, NAVY, True)
    set_font(header.add_run("\t" + context), 8.5, TEAL, True)
    borders = xml_tag("pBdr")
    borders.append(xml_tag("bottom", val="single", color=LINE, sz="7", space="6"))
    header._p.get_or_add_pPr().append(borders)

    footer = section.footer.paragraphs[0]
    footer.paragraph_format.tab_stops.add_tab_stop(Inches(PAPER_WIDTH), WD_TAB_ALIGNMENT.RIGHT)
    set_font(footer.add_run(f"{title}  ·  Edición 0.1"), 8.3, SLATE)
    set_font(footer.add_run("\t"), 8.3, SLATE)
    field = xml_tag("fldSimple", instr="PAGE")
    footer._p.append(field)


def add_cover(document, title, subtitle, context, sections, page_numbers):
    first = document.element.body[0]
    contents = [p for p in document.paragraphs if p.text.strip()]
    if not contents:
        raise ValueError(f"Fuente vacía para {title}")
    contents[0].paragraph_format.page_break_before = True

    def insert(value, size, shade, bold=False, before=0, after=0):
        p = document.add_paragraph()
        first.addprevious(p._p)
        p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(before), Pt(after)
        p.paragraph_format.line_spacing = 1.03
        set_font(p.add_run(value), size, shade, bold)
        return p

    insert("PROYECTO DE AULA   /   " + context, 10, TEAL, True, before=17, after=10)
    insert(title, 31, NAVY, True, after=6)
    insert(subtitle, 14.3, TEAL, after=16)
    insert(PROJECT + ".", 11.4, DARK, after=13)
    insert("Proyecto de aula   ·   Ingeniería de datos", 9.5, SLATE, after=4)
    insert("Entrega académica   ·   Noviembre de 2026", 9.5, SLATE, after=4)
    insert("Versión documental   0.1  ·  Entrega académica", 9.5, SLATE, after=17)
    insert("Contenido", 13, NAVY, True, after=6)
    for heading in sections:
        number = str(page_numbers.get(heading, ""))
        row = insert(f"{heading}\t{number}", 9.9, DARK, after=4)
        row.paragraph_format.tab_stops.add_tab_stop(Inches(PAPER_WIDTH), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def heading_pages(pdf_path, headings):
    with pymupdf.open(pdf_path) as pdf:
        pages = [normalize(page.get_text()) for page in pdf]
    result = {}
    for heading in headings:
        key = normalize(heading)
        for number, page in enumerate(pages[1:], start=2):
            if key in page:
                result[heading] = number
                break
        else:
            raise ValueError(f"Encabezado ausente en {pdf_path.name}: {heading}")
    return result


def make_doc(source, target, stage, page_numbers=None):
    title, subtitle = META[target.stem]
    raw = source.read_text(encoding="utf-8")
    raw = re.sub(r"^# [^\n]+\n", "", raw, count=1)
    # Usa el PNG hermano cuando una figura vectorial cuenta con las dos exportaciones.
    raw = re.sub(r"(!\[[^\]]*\]\()([^ )]+)\.svg(\))", lambda m:
                 m[1] + m[2] + (".png" if (source.parent / (m[2] + ".png")).exists() else ".svg") + m[3],
                 raw)
    command = ["pandoc", "--from", "gfm", "--to", "docx", "--no-highlight", "--resource-path",
               str(source.parent) + ":" + str(ROOT), "--metadata", "lang=es", "-o", str(stage)]
    subprocess.run(command, cwd=source.parent, input=raw, text=True, check=True)
    document = docx.Document(stage)
    headings = [p.text for p in document.paragraphs if p.style.name == "Heading 2"]
    if not headings or len(set(headings)) != len(headings):
        raise ValueError(f"Revise los encabezados ## de {source}")
    style_doc(document)
    context = {"moment-01":"MOMENTO 1", "moment-02":"MOMENTO 2", "moment-03":"MOMENTO 3",
               "final":"SUSTENTACIÓN Y ENTREGA"}[SOURCE_DIRECTORIES[target.stem]]
    band(document, title, context)
    add_cover(document, title, subtitle, context, headings, page_numbers or {})
    properties = document.core_properties
    properties.title, properties.subject = title, PROJECT
    properties.author, properties.keywords = "Proyecto de aula", "Lago de datos, infraestructura, Momento 1"
    document.save(target)
    return headings


def export_pdfs(stems, directory, profile):
    command = ["soffice", "-env:UserInstallation=" + profile.as_uri(), "--headless",
               "--convert-to", "pdf:writer_pdf_Export", "--outdir", str(directory)]
    subprocess.run(command + [str(directory / (s + ".docx")) for s in stems], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
    for stem in stems:
        if not (directory / (stem + ".pdf")).is_file():
            raise RuntimeError(f"LibreOffice no generó {stem}.pdf")


def validate(directory, stems):
    records = {}
    for stem in stems:
        path = directory / (stem + ".pdf")
        with ZipFile(path.with_suffix(".docx")) as archive:
            if archive.testzip() or "word/document.xml" not in archive.namelist():
                raise ValueError(f"DOCX inválido: {stem}")
        with pymupdf.open(path) as pdf:
            if len(pdf) < 2:
                raise ValueError(f"Documento sin desarrollo: {stem}")
            for i, page in enumerate(pdf):
                # Excluye encabezado y pie para detectar hojas vacías con estos elementos.
                words = page.get_text("words", clip=pymupdf.Rect(44, 57, 570, 735))
                if not words and not page.get_images():
                    raise ValueError(f"Página sin contenido: {stem}, p. {i+1}")
                if any(w[2] > page.rect.width+0.5 or w[0] < 0 for w in page.get_text("words")):
                    raise ValueError(f"Texto fuera de página: {stem}, p. {i+1}")
            records[stem] = {"paginas_pdf": len(pdf), "docx_integro": True, "pdf_con_contenido_en_cada_pagina": True}
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documentos", nargs="*", help="Nombres sin extensión. Por omisión se generan todos.")
    parser.add_argument("--output", type=Path, help="Reúne todos los documentos en esta ruta; por omisión se clasifican en la carpeta de cada momento.")
    parser.add_argument("--report", type=Path, help="Guarda un registro JSON de las verificaciones.")
    args = parser.parse_args()
    keys = list(dict.fromkeys(args.documentos or META))
    if any(key not in META for key in keys):
        parser.error("Documentos válidos: " + ", ".join(META))
    originals = {"lago": "moment-02/manual.md", "recuperacion": "entrega/recuperacion.md",
                 "buenas-practicas": "entrega/buenas-practicas.md"}
    sources = {name: ROOT / "docs" / originals.get(name, SOURCE_DIRECTORIES[name] + "/" + name + ".md") for name in keys}
    if not args.documentos:
        keys = [name for name in keys if sources[name].is_file()]
    with tempfile.TemporaryDirectory(prefix="lago-documentos-") as temp:
        tmp = Path(temp)
        headings = {}
        for stem in keys:
            headings[stem] = make_doc(sources[stem], tmp / (stem + ".docx"), tmp / "base.docx")
        profile = (tmp / "profile").resolve()
        export_pdfs(keys, tmp, profile)
        page_map = {stem: heading_pages(tmp / (stem + ".pdf"), headings[stem]) for stem in keys}
        for stem in keys:
            make_doc(sources[stem], tmp / (stem + ".docx"), tmp / "base.docx", page_map[stem])
        export_pdfs(keys, tmp, profile)
        records = validate(tmp, keys)
        for stem in keys:
            if heading_pages(tmp / (stem + ".pdf"), headings[stem]) != page_map[stem]:
                raise ValueError(f"El índice de {stem} cambió al paginar")
            output = args.output.resolve() if args.output else ROOT / "docs" / SOURCE_DIRECTORIES[stem] / "entrega"
            output.mkdir(parents=True, exist_ok=True)
            for ext in (".pdf", ".docx"):
                shutil.copyfile(tmp / (stem + ext), output / (stem + ext))
            records[stem]["secciones_con_indice"] = len(headings[stem])
    report = {"metodo": "ZIP de Word, reapertura PDF, numeración de índice y detección de páginas vacías y texto fuera del papel", "documentos": records}
    result = json.dumps(report, indent=2, ensure_ascii=False)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
