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

## Momentos 1 y 3 · RKE2, HAProxy y P5

| Evidencia | Obtención y alcance | Requisitos |
|---|---|---|
| [Admisión previa](evidence/moment-01/kubernetes/admision.json) · [Balanceador previo](evidence/moment-01/kubernetes/balanceador.json) | Actas históricas. La primera registró recursos ante kube-apiserver y etcd, con cero nodos. La segunda ensayó los cuatro listeners de HAProxy con endpoints TCP locales. | M1-K8S, M1-LBK8S |
| [Docker y Kind](evidence/moment-01/kubernetes/p5/codex/docker-kind.json) · [RKE2 en systemd](evidence/moment-01/kubernetes/p5/codex/rke2.json) · [RKE2 directo](evidence/moment-01/kubernetes/p5/codex/rke2-server.json) · [Snapshotter native](evidence/moment-01/kubernetes/p5/codex/rke2-native.json) · [K3d](evidence/moment-01/kubernetes/p5/codex/k3d.json) | Docker rootless en Codex. Kind requirió delegación de cgroups. Systemd terminó con código 255. RKE2 directo registró un error al montar overlay y con native terminó sin readiness. K3d creó tres contenedores y el servidor quedó en reinicio. | M1-K8S, M1-READY |
| [API local tras HAProxy](evidence/moment-01/kubernetes/p5/codex/api/api.json) · [kubectl](evidence/moment-01/kubernetes/p5/codex/api/kubectl-api.txt) · [captura](evidence/moment-01/kubernetes/p5/codex/api/api-readyz.png) | API Kubernetes v1.35.0 con TLS, etcd y HAProxy 3.0.11 en procesos locales. Se observó readiness y se admitieron los recursos de P5. Inventario de cero nodos y cero pods. | M1-LBK8S |
| [Primer ensayo en GitHub](evidence/moment-01/kubernetes/p5/ensayos/45851500040/p5.json) · [salida de kubectl](evidence/moment-01/kubernetes/p5/ensayos/45851500040/kubectl-antes.txt) | RKE2 v1.35.8+rke2r1, tres nodos Ready y dos réplicas Running. El acceso entre IP de pod venció y el ensayo terminó antes de detener el worker. | M1-K8S, M1-CP, M1-WORKERS, M1-READY, M1-LBK8S, M1-DEMO-K8S, M3-P5 |

## Momento 2 · procesamiento, SQL y catálogo

| Componente | Resultado | Evidencia |
|---|---|---|
| Spark y Medallion | 251 filas de venta, 247 aceptadas, un duplicado y tres rechazos. 875 unidades y 33.589.000 COP. Spark 4.0.1 en local[2] con almacenamiento S3 verificado. | [Motor](evidence/moment-02/spark/ejecucion.json) · [Conciliación](evidence/moment-02/spark/conciliacion.json) |
| Trino y P2 | Quince consultas ejecutadas en Trino 477 sobre MinIO, con ID de consulta y CSV. P2 aprobada en el laboratorio Docker. | [Acta](evidence/moment-02/trino/p2.json) · [CSV de resultados](results/sql/index.json) · [Captura](evidence/moment-02/trino/consulta-p2.png) |
| Gobierno de datos | Exportación del catálogo de 12 activos físicos con 48 campos y 15 relaciones. | [Catálogo](evidence/moment-02/datahub/catalog.json) · [Diccionario](evidence/moment-02/datahub/diccionario.csv) |


**P5 ejecutada con fallo.** En el último pipeline se observaron apagado, reprogramación y retorno del mismo worker a Ready. HAProxy mantuvo su backend DOWN al vencer el plazo. [Acta](evidence/moment-01/kubernetes/p5/ensayos/45887973767/p5.json) · [kubectl durante la reprogramación](evidence/moment-01/kubernetes/p5/ensayos/45887973767/kubectl-reprogramado.txt) · [Procedencia y SHA-256 del artefacto](evidence/moment-01/kubernetes/p5/ensayos/45887973767/procedencia.json)
