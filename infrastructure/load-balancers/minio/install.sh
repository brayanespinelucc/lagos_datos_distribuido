#!/usr/bin/env bash
# Instalar exclusivamente en la VM lb-minio del inventario.
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == lb-minio ]] || { echo 'Ejecutar como root en lb-minio.' >&2; exit 2; }
base=$(cd -- "$(dirname -- "$0")" && pwd)
if ! command -v haproxy >/dev/null; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y haproxy
fi
haproxy -c -f "$base/haproxy.cfg"
dest=/etc/haproxy/haproxy.cfg
if ! cmp -s "$base/haproxy.cfg" "$dest"; then
    [[ ! -f $dest || -f $dest.antes-de-lago ]] || cp -p "$dest" "$dest.antes-de-lago"
    install -m 0644 "$base/haproxy.cfg" "$dest"
    systemctl reload-or-restart haproxy
fi
systemctl enable --now haproxy
systemctl is-active haproxy
