#!/bin/sh
# Se copia exclusivamente al nodo systemd desechable, con su propio espacio de montajes.
set -eu
mount --make-rshared /
if [ "$(stat -f -c %T /sys/fs/bpf)" != bpf_fs ]; then
  mount -t bpf -o nosuid,nodev,noexec bpf /sys/fs/bpf
fi
mount --make-shared /sys/fs/bpf
