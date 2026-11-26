#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == lb-k8s ]] || { echo 'Ejecute como root en lb-k8s.' >&2; exit 2; }
ip -o -4 addr | awk '{split($4,a,"/");print a[1]}' | grep -Fxq '10.42.10.11' ||
  { echo 'La IP de lb-k8s debe ser 10.42.10.11.' >&2; exit 2; }
base=$(cd -- "$(dirname -- "$0")" && pwd)
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y haproxy
haproxy -c -f "$base/haproxy.cfg"
dest=/etc/haproxy/haproxy.cfg
if ! cmp -s "$base/haproxy.cfg" "$dest"; then
  [[ ! -f $dest || -f "$dest.antes-de-lago" ]] || cp -p "$dest" "$dest.antes-de-lago"
  install -m 0644 "$base/haproxy.cfg" "$dest"
  systemctl reload-or-restart haproxy
fi
systemctl enable --now haproxy
systemctl is-active haproxy
