#!/bin/sh
# Ejecutar desde un cliente de confianza. mc conserva los alias sólo donde indique MC_CONFIG_DIR.
set -eu
: "${MINIO_ENDPOINT:?falta el endpoint del balanceador}"
: "${MINIO_SECRETS_DIR:?falta el directorio de secretos}"
: "${MC_CONFIG_DIR:?falta el directorio privado para los alias de mc}"
umask 077
mkdir -p "$MC_CONFIG_DIR"
policy=$(dirname "$0")/ingesta-bronze.json
mc alias set admin "$MINIO_ENDPOINT" "$(cat "$MINIO_SECRETS_DIR/root_user")" "$(cat "$MINIO_SECRETS_DIR/root_password")" >/dev/null
for bucket in bronze silver gold; do
    mc mb --ignore-existing "admin/$bucket"
done
mc admin policy create admin ingesta-bronze "$policy"
mc admin user add admin ingesta-lab "$(cat "$MINIO_SECRETS_DIR/ingesta_password")"
mc admin policy attach admin ingesta-bronze --user ingesta-lab
mc alias set ingesta "$MINIO_ENDPOINT" ingesta-lab "$(cat "$MINIO_SECRETS_DIR/ingesta_password")" >/dev/null
