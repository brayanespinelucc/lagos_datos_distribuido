# Índice de evidencias

## Momento 1 · Proxmox y Ubuntu

| Evidencia | Obtención y alcance | Requisitos |
|---|---|---|
| [Validación portátil](evidence/moment-01/proxmox/validacion.json) | `2026-11-26T09:37:11+00:00`. Ejecución de `plan` y `render` en Codex Cloud, validación de ocho configuraciones con el esquema de Canonical y once pruebas aprobadas. Registra también los prerrequisitos ausentes en el host. | M1-PVE, M1-UBU, M1-VM, M1-RED, M1-COM, M1-DOC-IP, M1-DOC-INST, M1-DEMO-PVE, M1-DEMO-COM |

SHA-256 del acta `9583513b3bcc03c72683d2518eb7d014ad123a5a7976f0359a415a81e4c41620`. El acta contiene los hashes de las fuentes probadas. Las verificaciones de arranque, acceso real a Proxmox y conectividad de los 56 pares de VM continúan pendientes. [Procedimiento reproducible](docs/moment-01/proxmox-ubuntu.md)

## Momentos 1 y 3 · MinIO y HAProxy

| Evidencia | Obtención y resultado | Requisitos |
|---|---|---|
| [Acta completa](evidence/moment-01/minio/validacion/result.json) | Ejecución en Docker del 26 de noviembre de 2026. Tres contenedores MinIO, seis volúmenes de datos y un balanceador. Incluye creación de buckets, identidad de ingesta, códigos de `mc` y S3, ausencia comprobada como administrador, comunicación y registros HTTP por backend. | M1-S3, M1-BUCKET, M1-USER, M1-IAM, M1-IO, M1-PEERS, M1-LBS3, M1-DEMO-BUCKET, M1-DEMO-IO |
| [P3 y P4 en el acta](evidence/moment-01/minio/validacion/result.json) | Los eventos «P3 · nodo detenido» y «P4 · nodo recuperado» conservan inventarios, cabeceras de quórum, duraciones y hashes de origen y descarga. Ambas pruebas aprobadas en el laboratorio de contenedores. | M3-P3, M3-P4 |
| [Consola](evidence/moment-01/minio/validacion/consola.png) · [Buckets](evidence/moment-01/minio/validacion/buckets.png) · [Contenido de Bronze](evidence/moment-01/minio/validacion/objetos-bronze.png) | Tres capturas reales de Chromium a 1440 × 900 tras autenticar al administrador. Se pueden consultar sin credenciales. | M1-WEB, M1-DEMO-WEB, M1-BUCKET, M1-IO |
| [Comprobaciones de configuración](evidence/moment-01/minio/preparacion.json) | Cuatro pruebas unitarias del criterio IAM, sintaxis de los scripts, comprobación de HAProxy y SHA-256 del ejecutable MinIO extraído de la imagen fijada. | M1-IAM, M1-LBS3, M1-DOC-INST |
| [Acta fallida original](evidence/moment-01/minio/result.json) | La aserción buscaba literalmente «Access Denied» en la salida de `mc`. Se conservó el archivo original byte por byte. Su SHA-256 es `9ec4476f26bc684388ba8d6b6c1ccedd04fd8c74ba5340fd88f7a37f49af6a65`. | M1-IAM |
| [Montajes](evidence/moment-01/minio/ensayos/montajes/result.json) · [Reincorporación inicial](evidence/moment-01/minio/ensayos/reincorporacion-inicial/result.json) · [Espera administrativa](evidence/moment-01/minio/ensayos/espera-administrativa/result.json) | Ensayos intermedios fallidos. Documentan el conteo inicial de montajes auxiliares, la lectura prematura desde el nodo que regresaba y un tiempo de espera del cliente administrativo demasiado corto durante la transición. | M1-S3, M3-P3, M3-P4 |

Las fechas UTC, los IDs de petición S3, la identidad del contenedor y los nombres de los volúmenes se conservan en el acta. Para comprobar la integridad desde la raíz del repositorio use `sha256sum -c evidence/moment-01/minio/SHA256SUMS`. [Manifiesto SHA-256](evidence/moment-01/minio/SHA256SUMS) · [Manual y análisis](docs/moment-01/minio.md)
