#!/usr/bin/env bash
set -euo pipefail
dest=${1:?Indique la carpeta de herramientas fuera del repositorio}
mkdir -p "$dest"
cd "$dest"
curl -fsSL --retry 3 -o envtest.tar.gz https://github.com/kubernetes-sigs/controller-tools/releases/download/envtest-v1.35.0/envtest-v1.35.0-linux-amd64.tar.gz
echo '130369c16f076e724d089189afaede960316f5f5dea6cf57be7a4fc6f09c77342893192509790e4056e116e232dff832ed863f5bd55dcb55d38f3ab834828a11  envtest.tar.gz' | sha512sum -c -
tar -xzf envtest.tar.gz
