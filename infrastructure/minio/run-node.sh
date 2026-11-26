#!/bin/sh
set -eu
MINIO_ROOT_USER=$(cat "$CREDENTIALS_DIRECTORY/root_user")
MINIO_ROOT_PASSWORD=$(cat "$CREDENTIALS_DIRECTORY/root_password")
export MINIO_ROOT_USER MINIO_ROOT_PASSWORD
exec /usr/local/bin/minio server --address :9000 --console-address :9001 \
    'http://minio-{1...3}:9000/srv/minio/disk{1...2}'
