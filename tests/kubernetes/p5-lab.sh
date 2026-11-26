#!/usr/bin/env bash
# Laboratorio dedicado. Toda la configuración privada vive en un temporal.
set -euo pipefail
umask 077
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
: "${P5_OUTPUT:?Indique un directorio nuevo para las evidencias}"
mkdir -p "$P5_OUTPUT"
out=$(cd "$P5_OUTPUT" && pwd)
[[ -z $(ls -A "$out") ]] || { echo 'El directorio de evidencia debe estar vacío.' >&2; exit 2; }
tmp=$(mktemp -d)
id=p5-$(openssl rand -hex 4)
kind_bin=${KIND_BIN:-kind}
export KUBECONFIG="$tmp/kubeconfig"
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
image=rancher/systemd-node:v0.0.8@sha256:bd3f36cfa953ea1c72e4c73e6d70fd964ebd32c1eabeacb69ac5497fc3dcf830
proxy=haproxy:3.0.11-alpine@sha256:e49b7beb96f4dba79f9a671515b469a6e516a2b88ff0681a820b184bba1effbd
node_image=kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f
server=$id-server
w1=$id-worker-1
w2=$id-worker-2
lb=$id-lb
net=$id
kind_created=0

remove_owned() {
  local ids name
  ids=$(docker ps -aq --filter "label=lago.p5=$id")
  for name in $ids; do docker rm -fv "$name" >/dev/null || true; done
  if docker network inspect "$id" --format '{{index .Labels "lago.p5"}}' 2>/dev/null | grep -Fxq "$id"; then
    docker network rm "$id" >/dev/null || true
  fi
}
cleanup() {
  remove_owned
  if [[ $kind_created == 1 ]]; then "$kind_bin" delete cluster --name "$id" >/dev/null || true; fi
  rm -rf -- "$tmp"
}
trap cleanup EXIT
ip_of() { docker inspect --format "{{(index .NetworkSettings.Networks \"$net\").IPAddress}}" "$1"; }
port_of() { docker port "$lb" "$1/tcp" | head -1 | cut -d: -f2; }

start_lb() {
  local mode=$1 a=$2 b=$3 c=$4
  python3 - "$mode" "$a" "$b" "$c" "$tmp/haproxy.cfg" <<'PY'
from pathlib import Path
import sys
mode,server,worker1,worker2,out=sys.argv[1:]
source=Path('infrastructure/load-balancers/kubernetes/haproxy.cfg').read_text()
source=source.replace('log /dev/log local0','log stdout format raw local0')
if mode=='kind':
    source=source.split('listen supervisor')[0]
for old,new in [('10.42.10.11','0.0.0.0'),('10.42.10.31',server),('10.42.10.32',worker1),('10.42.10.33',worker2)]:
    source=source.replace(old,new)
source+=f'''
listen p5-http
    bind :18080
    balance roundrobin
    option tcp-check
    server worker-1 {worker1}:30080 check
    server worker-2 {worker2}:30080 check

listen estado
    bind :18404
    mode http
    stats enable
    stats uri /estado
'''
Path(out).write_text(source)
PY
  cp "$tmp/haproxy.cfg" "$out/haproxy-$mode.cfg"
  # El UID de la imagen debe poder leer este archivo público de rutas.
  chmod 644 "$tmp/haproxy.cfg"
  local opts=()
  if [[ $mode == rke2 ]]; then opts+=(--ip 10.42.10.11 -p 127.0.0.1::9345 -p 127.0.0.1::443); fi
  docker run -d --name "$lb" --label "lago.p5=$id" --network "$net" "${opts[@]}" \
    -p 127.0.0.1::6443 -p 127.0.0.1::18080 -p 127.0.0.1::18404 \
    -v "$tmp/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro" "$proxy" >/dev/null
}
attempt_rke2() (
  set -eu
  docker network create --label "lago.p5=$id" --subnet 10.42.10.0/24 "$net" >/dev/null
  archive=${RKE2_ARCHIVE:-$tmp/rke2.linux-amd64.tar.gz}
  if [[ ! -f $archive ]]; then
    curl -fsSL --max-time 120 -o "$archive" 'https://github.com/rancher/rke2/releases/download/v1.35.8%2Brke2r1/rke2.linux-amd64.tar.gz'
  fi
  printf '%s  %s\n' 805f26f1e7e875b7721515d7a3e55b79b86124252a8c9191f5fc3f06523af26f "$archive" | sha256sum -c -
  start_lb rke2 10.42.10.31 10.42.10.32 10.42.10.33
  local names=("$server" "$w1" "$w2") hosts=(rke2-server rke2-worker-1 rke2-worker-2)
  local extra=()
  if [[ -d /lib/modules/$(uname -r) ]]; then extra+=(-v /lib/modules:/lib/modules:ro); fi
  for i in 0 1 2; do
    name=${names[i]}
    host=${hosts[i]}
    docker run -dt --privileged --cgroupns=private --tmpfs /run --tmpfs /run/lock \
      --network "$net" --ip "10.42.10.$((31+i))" --hostname "$host" --name "$name" \
      --label "lago.p5=$id" -e SYSTEMD_LOG_TARGET=console -v /var/lib/rancher/rke2 \
      -v /var/lib/kubelet "${extra[@]}" "$image" /usr/lib/systemd/systemd --unit=noop.target >/dev/null
    for unused in {1..12}; do
      if docker exec "$name" systemctl is-active --quiet noop.target; then break; fi
      [[ $(docker inspect -f '{{.State.Running}}' "$name") == true ]] || break
      sleep 2
    done
    docker exec "$name" systemctl is-active noop.target
    docker exec "$name" install -d -m 700 /etc/rancher/rke2
    docker exec -i "$name" tar xzf - -C /usr/local < "$archive"
    docker cp "infrastructure/kubernetes/nodes/$host.yaml" "$name:/etc/rancher/rke2/config.yaml"
    docker exec "$name" systemctl daemon-reload
  done
  docker exec "$server" sh -ec 'umask 077; openssl rand -hex 32 > /etc/rancher/rke2/agent-secret; mkdir -p /var/lib/rancher/rke2/server/manifests'
  docker cp infrastructure/kubernetes/traefik-values.yaml "$server:/var/lib/rancher/rke2/server/manifests/lago-traefik.yaml"
  docker exec "$server" systemctl start --no-block rke2-server
  for unused in {1..72}; do
    if docker exec "$server" sh -c 'test -s /var/lib/rancher/rke2/server/agent-token && test -s /etc/rancher/rke2/rke2.yaml'; then break; fi
    sleep 4
  done
  docker cp "$server:/etc/rancher/rke2/rke2.yaml" "$KUBECONFIG"
  kubectl config set-cluster default --server="https://127.0.0.1:$(port_of 6443)" --tls-server-name=lb-k8s >/dev/null
  for name in "$w1" "$w2"; do
    docker exec "$server" cat /var/lib/rancher/rke2/server/agent-token | docker exec -i "$name" sh -ec 'umask 077; cat > /etc/rancher/rke2/join-token'
    docker exec "$name" systemctl start --no-block rke2-agent
  done
  for unused in {1..70}; do
    if kubectl get node rke2-worker-1 rke2-worker-2 --request-timeout=3s >/dev/null 2>&1; then break; fi
    sleep 3
  done
  kubectl wait node/rke2-server node/rke2-worker-1 node/rke2-worker-2 --for=condition=Ready --timeout=150s
)
diagnostics() {
  local n
  for n in "$server" "$w1" "$w2"; do
    docker inspect "$n" --format '{{.Name}} {{.State.Status}} {{.State.ExitCode}}' || continue
    docker logs --tail 15 "$n" 2>&1 | tr -d '\r' || true
    # Publicar solo líneas de error operativo, evitando instrucciones de unión y credenciales.
    docker exec "$n" journalctl -u rke2-server -u rke2-agent -n 70 --no-pager -o cat 2>/dev/null |
      grep -Ei 'cgroup|permission denied|operation not permitted|failed to (mount|start)|snapshotter' |
      grep -Evi 'token|password|secret|bearer|K10[0-9a-f]{64}' | tail -12 || true
  done
}
date -u +%FT%TZ > "$out/inicio-utc.txt"
docker info --format '{{.ServerVersion}} {{json .SecurityOptions}} cgroup={{.CgroupDriver}}/{{.CgroupVersion}}' > "$out/docker.txt"
# Al ejecutar la función en un subshell independiente, errexit sigue activo en cada paso.
set +e
attempt_rke2 > "$out/arranque-rke2.txt" 2>&1
rc=$?
set -e
if [[ $rc == 0 ]]; then
  mode=rke2
  target=rke2-worker-1
  survivor=rke2-worker-2
  curl --noproxy '*' --fail --silent --show-error --cacert <(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d) \
    --resolve "lb-k8s:$(port_of 9345):127.0.0.1" "https://lb-k8s:$(port_of 9345)/cacerts" -o "$tmp/cacerts.pem"
  openssl x509 -in "$tmp/cacerts.pem" -noout -subject -fingerprint -sha256 > "$out/supervisor.txt"
else
  echo "RKE2 terminó con código $rc" >> "$out/arranque-rke2.txt"
  diagnostics > "$out/diagnostico-rke2.txt" 2>&1
  remove_owned
  mode=kind
  net=kind
  if ! command -v "$kind_bin" >/dev/null; then
    kind_bin="$tmp/kind"
    curl -fsSL --max-time 60 -o "$kind_bin" https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-linux-amd64
    sum=$(curl -fsSL --max-time 30 https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-linux-amd64.sha256sum)
    printf '%s  %s\n' "${sum%% *}" "$kind_bin" | sha256sum -c -
    chmod 700 "$kind_bin"
  fi
  "$kind_bin" version > "$out/version-kind.txt"
  kind_created=1
  "$kind_bin" create cluster --config tests/kubernetes/kind-p5.yaml --name "$id" --image "$node_image" --wait 180s --kubeconfig "$KUBECONFIG" > "$out/arranque-kind.txt" 2>&1
  server=$id-control-plane; w1=$id-worker; w2=$id-worker2
  target=$w1; survivor=$w2
  start_lb kind "$(ip_of "$server")" "$(ip_of "$w1")" "$(ip_of "$w2")"
  kubectl config set-cluster "kind-$id" --server="https://127.0.0.1:$(port_of 6443)" --tls-server-name=127.0.0.1 >/dev/null
fi
kubectl wait --for=condition=Ready node --all --timeout=120s > "$out/ready.txt"
kubectl get --raw='/readyz?verbose' > "$out/api-readyz.txt"
kubectl version -o json > "$out/version-api.json"
# Los backends de NodePort entran en servicio después de desplegar la aplicación testigo.
kubectl apply -f tests/kubernetes/aplicacion-p5.yaml > "$out/aplicar.txt"
kubectl -n lago-p5 rollout status deploy/testigo --timeout=180s >> "$out/aplicar.txt"
python3 tests/kubernetes/p5.py --output "$out" --mode "$mode" --lab "$id" --container "$w1" \
  --worker "$target" --survivor "$survivor" --http-port "$(port_of 18080)" --stats-port "$(port_of 18404)"
