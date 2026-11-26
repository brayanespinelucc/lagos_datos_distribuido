#!/usr/bin/env bash
# Ejecutar dentro de una de las tres VM nuevas y dedicadas.
set -euo pipefail
umask 077
base=$(cd -- "$(dirname -- "$0")" && pwd)
node=$(hostname -s)
case "$node" in
  rke2-server) role=server ;;
  rke2-worker-1|rke2-worker-2) role=agent ;;
  *) echo "Este host no figura en el inventario RKE2: $node" >&2; exit 2 ;;
esac
# shellcheck disable=SC1091
source /etc/os-release
[[ $EUID == 0 && $ID == ubuntu && $VERSION_ID == 24.04 && $(uname -m) == x86_64 ]] ||
  { echo 'Se requiere root dentro de Ubuntu Server 24.04 amd64.' >&2; exit 2; }
[[ -d /run/systemd/system && $(wc -l </proc/swaps) -eq 1 ]] ||
  { echo 'Verifique systemd y desactive swap en estas VM dedicadas antes de instalar.' >&2; exit 2; }
node_ip=$(awk '$1 == "node-ip:" {print $2}' "$base/nodes/$node.yaml")
ip -4 -o addr show | awk '{split($4,a,"/");print a[1]}' | grep -Fxq "$node_ip" ||
  { echo "La VM no posee la IP del inventario: $node_ip" >&2; exit 2; }
conf=/etc/rancher/rke2
if [[ $role == agent ]]; then
  token=$conf/join-token
  [[ -s $token && $(stat -c '%u:%a' "$token") == 0:600 ]] &&
    grep -Eq '^K10[0-9a-f]{64}::' "$token" ||
    { echo "Instale el token seguro de agente en $token (root, 0600)." >&2; exit 2; }
fi
if [[ -e $conf/config.yaml ]] && ! cmp -s "$base/nodes/$node.yaml" "$conf/config.yaml"; then
  echo "Configuración previa diferente en $conf/config.yaml. Revísela antes de continuar." >&2; exit 2
fi
version=v1.35.8+rke2r1
release=v1.35.8%2Brke2r1
existing=$(command -v rke2 || true)
if [[ -n $existing ]] && ! "$existing" --version | grep -Fq "$version ("; then
  echo 'Hay otra versión de RKE2. Las actualizaciones requieren respaldo y procedimiento propio.' >&2; exit 2
fi
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
if [[ -z $existing ]]; then
  cd "$tmp"
  curl -fLsS --retry 3 --proto '=https' -o install.sh "https://raw.githubusercontent.com/rancher/rke2/$release/install.sh"
  curl -fLsS --retry 3 --proto '=https' -O "https://github.com/rancher/rke2/releases/download/$release/rke2.linux-amd64.tar.gz"
  echo '2d24db2184dd6b1a5e281fa45cc9a8234c889394721746f89b5fe953fdaaf40a  install.sh' | sha256sum -c -
  echo '805f26f1e7e875b7721515d7a3e55b79b86124252a8c9191f5fc3f06523af26f  rke2.linux-amd64.tar.gz' >sha256sum-amd64.txt
  sha256sum -c sha256sum-amd64.txt
  INSTALL_RKE2_METHOD=tar INSTALL_RKE2_TYPE="$role" INSTALL_RKE2_VERSION="$version" INSTALL_RKE2_ARTIFACT_PATH="$tmp" sh install.sh
fi
install -d -m 0700 "$conf"
install -m 0600 "$base/nodes/$node.yaml" "$conf/config.yaml"
if [[ $role == server ]]; then
  if [[ ! -s $conf/agent-secret ]]; then
    openssl rand -hex 32 >"$tmp/agent-secret"
    install -m 0600 "$tmp/agent-secret" "$conf/agent-secret"
  fi
  addons=/var/lib/rancher/rke2/server/manifests
  install -d -m 0755 "$addons"
  install -m 0644 "$base/traefik-values.yaml" "$addons/lago-traefik.yaml"
elif [[ $node == rke2-worker-2 ]]; then
  install -d -m 0750 -o 65532 -g 65532 /var/lib/lago/m1-registro
fi
systemctl enable --now "rke2-$role"
systemctl is-active "rke2-$role"
