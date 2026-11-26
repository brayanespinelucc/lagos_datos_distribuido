#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/rke2/rke2.yaml}
k=${KUBECTL:-/var/lib/rancher/rke2/bin/kubectl}
"$k" get --raw='/readyz?verbose'
"$k" wait --for=condition=Ready --timeout=3m node/rke2-server node/rke2-worker-1 node/rke2-worker-2
"$k" get nodes -o wide
"$k" -n lago-m1 rollout status deployment/portada --timeout=4m
"$k" -n lago-m1 rollout status statefulset/registro --timeout=4m
"$k" -n lago-m1 get pods,pvc,ingress -o wide
"$k" -n lago-m1 exec registro-0 -- cat /registro/huella.txt
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
if [[ -n ${TLS_CA_FILE:-} ]]; then
  ca=$TLS_CA_FILE
else
  "$k" -n lago-m1 get secret m1-ingress-tls -o 'jsonpath={.data.tls\.crt}' | base64 -d >"$tmp/ca.pem"
  ca=$tmp/ca.pem
fi
curl --fail --silent --show-error --max-time 10 --noproxy '*' --cacert "$ca" \
  --resolve m1.lago.internal:443:10.42.10.11 https://m1.lago.internal/ | grep -F 'Servicio de verificación'
