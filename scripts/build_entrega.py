#!/usr/bin/env python3
"""Empaqueta el portal offline, las fuentes versionadas y un manifiesto SHA-256."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('src', 'href') and value and value.startswith('./'):
                self.paths.append(value[2:])


def digest(content):
    return hashlib.sha256(content).hexdigest()


def build(portal, out):
    data = (portal/'assets/data.js').read_text()
    model = json.loads(data.removeprefix('window.LAGO = ').rstrip().removesuffix(';'))
    for file in model['files']:
        target = portal/file['url']
        if not target.resolve().is_relative_to(portal.resolve()) or digest(target.read_bytes()) != file['sha256']:
            raise ValueError(f"Recurso incorrecto: {file['path']}")
    parser = Resources()
    parser.feed((portal/'index.html').read_text())
    if not all((portal/name).is_file() for name in parser.paths):
        raise ValueError('Recurso inicial ausente')
    tracked = subprocess.check_output(['git','ls-files','-z'], cwd=ROOT).decode().split('\0')
    inputs = {p.relative_to(portal).as_posix(): p for p in portal.rglob('*')
              if p.is_file() and not p.is_symlink() and not p.name.startswith('.')}
    for name in tracked:
        if not name or name.startswith('entrega/') or name.startswith('public/'):
            continue
        path = ROOT/name
        if path.is_file() and not path.is_symlink():
            inputs['proyecto/'+name] = path
    out.mkdir(parents=True, exist_ok=True)
    target = out/'lago-datos-distribuido.zip'
    with tempfile.TemporaryDirectory(dir=out) as staging:
        temp = Path(staging)/target.name
        manifest = []
        with ZipFile(temp,'w',compression=ZIP_DEFLATED,compresslevel=6) as z:
            for name,p in sorted(inputs.items()):
                content=p.read_bytes()
                z.writestr(name,content)
                manifest.append(f'{digest(content)}  {name}')
            z.writestr('MANIFIESTO-SHA256.txt','\n'.join(manifest)+'\n')
        with ZipFile(temp) as z:
            if z.testzip() or 'index.html' not in z.namelist() or 'proyecto/README.md' not in z.namelist():
                raise ValueError('El ZIP no supera la comprobación interna')
            for line in z.read('MANIFIESTO-SHA256.txt').decode().splitlines():
                expected,name=line.split('  ',1)
                if digest(z.read(name))!=expected:
                    raise ValueError(name)
        temp.replace(target)
    (out/'SHA256SUMS').write_text(f'{digest(target.read_bytes())}  {target.name}\n')
    print(f'{len(inputs)} archivos con SHA-256, {len(model["files"])} recursos del portal, {target.stat().st_size} bytes')


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('portal',type=Path)
    cli.add_argument('--output',type=Path,default=ROOT/'entrega')
    args=cli.parse_args()
    build(args.portal.resolve(),args.output.resolve())
