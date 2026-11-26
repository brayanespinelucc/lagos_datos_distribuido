#!/usr/bin/env bash
# Solo crea o reconcilia los recursos del laboratorio. El certificado es interno.
set -euo pipefail
umask 077
base=$(cd -- "$(dirname -- "$0")" && pwd)
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/rke2/rke2.yaml}
kubectl=${KUBECTL:-/var/lib/rancher/rke2/bin/kubectl}
[[ -r $KUBECONFIG ]] || { echo "Se requiere un kubeconfig de laboratorio legible." >&2; exit 2; }
apply=("$kubectl" apply --server-side --field-manager=lago-m1 --validate=strict)
"${apply[@]}" -f "$base/manifests/00-namespace.yaml"
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
# --ignore-not-found solo devuelve vacío si el API responde 404; errores de acceso detienen el script.
present=$("$kubectl" -n lago-m1 get secret m1-ingress-tls --ignore-not-found -o name)
if [[ -n ${TLS_CERT_FILE:-} || -n ${TLS_KEY_FILE:-} ]]; then
  : "${TLS_CERT_FILE:?Indique ambos archivos TLS}" "${TLS_KEY_FILE:?Indique ambos archivos TLS}"
  cert=$TLS_CERT_FILE
  key=$TLS_KEY_FILE
elif [[ -z $present ]]; then
  cert=$tmp/tls.crt
  key=$tmp/tls.key
  openssl req -x509 -newkey rsa:2048 -nodes -days 90 -keyout "$key" -out "$cert" \
    -subj /CN=m1.lago.internal -addext 'subjectAltName=DNS:m1.lago.internal' 2>"$tmp/openssl.log"
else
  cert=''
fi
if [[ -n $cert ]]; then
  openssl x509 -in "$cert" -noout -checkhost m1.lago.internal | grep -q 'does match certificate' ||
    { echo 'El certificado debe cubrir m1.lago.internal.' >&2; exit 2; }
  "$kubectl" -n lago-m1 create secret tls m1-ingress-tls --cert="$cert" --key="$key" --dry-run=client -o yaml |
    "${apply[@]}" -f -
fi
for manifest in "$base"/manifests/[1-9]*.yaml; do
  "${apply[@]}" -f "$manifest"
done
