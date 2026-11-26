#!/usr/bin/env bash
# Instalar en una sola VM del inventario. Los montajes XFS llegan desde cloud-init.
set -euo pipefail
fail() { echo "$*" >&2; exit 1; }
[[ $# == 2 ]] || fail 'Uso: install-node.sh DIRECTORIO_SECRETOS BINARIO_MINIO'
[[ $EUID == 0 && $(hostname -s) =~ ^minio-[123]$ ]] || fail 'Ejecutar como root en minio-1, minio-2 o minio-3.'
base=$(cd -- "$(dirname -- "$0")" && pwd)
secret_dir=$1
binary=$2
for item in root_user root_password; do
    [[ -f "$secret_dir/$item" && -s "$secret_dir/$item" ]] || fail "Falta $item"
done
[[ -f "$binary" ]] || fail 'Falta el binario del inventario.'
sum=8d5c4d6041d643230ccb4ca88682c2f7109d4cf4205f279aa60b9c6694552e53
[[ $(sha256sum -- "$binary" | cut -d' ' -f1) == "$sum" ]] || fail 'SHA-256 del binario MinIO incorrecto.'
first_uuid=
for mount in /srv/minio/disk{1,2}; do
    [[ $(findmnt -nr -M "$mount" -o FSTYPE) == xfs ]] || fail "Falta el montaje XFS $mount"
    volume_uuid=$(findmnt -nr -M "$mount" -o UUID)
    [[ -n $volume_uuid && $volume_uuid != "$first_uuid" ]] || fail 'Se requieren dos XFS con UUID distintos.'
    first_uuid=$volume_uuid
    if [[ $(stat -c %U "$mount") != minio && -n $(find "$mount" -mindepth 1 -maxdepth 1 -print -quit) ]]; then
        fail "El volumen $mount contiene datos ajenos al servicio."
    fi
done
getent group minio >/dev/null || groupadd --system minio
id minio >/dev/null 2>&1 || useradd --system --gid minio --home-dir /var/lib/lago-minio --shell /usr/sbin/nologin minio
chown minio:minio /srv/minio/disk{1,2}
install -d -m 0700 /etc/lago/minio
install -d -m 0755 /usr/local/libexec
changed=0
copy_changed() {
    local src=$1 dest=$2 mode=$3 stage
    if cmp -s -- "$src" "$dest"; then chmod "$mode" "$dest"; return; fi
    stage=$(mktemp "${dest}.XXXXXX")
    install -m "$mode" -- "$src" "$stage"
    mv -f -- "$stage" "$dest"
    changed=1
}
copy_changed "$secret_dir/root_user" /etc/lago/minio/root_user 0600
copy_changed "$secret_dir/root_password" /etc/lago/minio/root_password 0600
copy_changed "$binary" /usr/local/bin/minio 0755
copy_changed "$base/run-node.sh" /usr/local/libexec/lago-minio 0755
copy_changed "$base/lago-minio.service" /etc/systemd/system/lago-minio.service 0644
systemctl daemon-reload
systemctl enable lago-minio
if [[ $changed == 1 ]] && systemctl is-active --quiet lago-minio; then
    systemctl restart lago-minio
else
    systemctl start lago-minio
fi
