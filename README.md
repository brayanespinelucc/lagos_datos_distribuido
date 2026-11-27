# Lago de datos distribuido

Proyecto universitario de una empresa comercial que necesita conciliar ventas e inventario. El lote conserva los CSV originales en Bronze, publica Parquet depurado en Silver y agrega indicadores en Gold. La entrega incluye el código, los datos sintéticos y las evidencias que permiten al profesor revisar cada resultado sin mantener activos los laboratorios.

**Descargue y extraiga el ZIP completo. Abra `index.html` para consultar los tres momentos, los resultados SQL, el catálogo, los documentos y las evidencias.** El directorio `proyecto/` del ZIP contiene las fuentes reproducibles. [Descargar ZIP](https://raw.githubusercontent.com/brayanespinelucc/lagos_datos_distribuido/refs/heads/entrega/bloque-0-momento-1/entrega/lago-datos-distribuido.zip) · [Guía docente](docs/entrega/guia-docente.md) · [Índice de evidencias](EVIDENCE_INDEX.md) · [Matriz de 83 requisitos](REQUIREMENTS_MATRIX.csv)

| Momento | Resultado documentado | Dónde verificarlo |
|---|---|---|
| 1 · Infraestructura | MinIO con tres contenedores y seis volúmenes. HAProxy, permisos IAM, transferencia, fallo y recuperación verificados. RKE2 v1.35.8+rke2r1 alcanzó un servidor y dos workers Ready en un runner Linux. La topología de ocho VM Ubuntu en Proxmox permanece preparada. | [MinIO](docs/moment-01/minio.md) · [RKE2](docs/moment-01/rke2.md) · [Inventario Proxmox](infrastructure/proxmox/inventory.json) |
| 2 · Lago y gobierno | Spark 4.0.1 en modo local procesó 251 filas de ventas. Se aceptaron 247, se separó un duplicado y se rechazaron tres. Se conciliaron 875 unidades y 33.589.000 COP. Trino 477 ejecutó 15 consultas sobre MinIO. El catálogo describe 12 datasets, 48 campos y 15 relaciones. | [Conciliación Spark](evidence/moment-02/spark/conciliacion.json) · [P2](evidence/moment-02/trino/p2.json) · [Índice SQL](results/sql/index.json) · [Diccionario](evidence/moment-02/datahub/diccionario.csv) |
| 3 · Operación | Las actas de cada prueba distinguen el servicio, el entorno, el resultado y sus límites. El portal incluye simulaciones didácticas identificadas y acceso a las observaciones originales. | [Pruebas y evidencias](EVIDENCE_INDEX.md) · [Operación](docs/moment-03/operacion.md) · [Recuperación](docs/entrega/recuperacion.md) |

## Reproducir y verificar

1. Para reconstruir el portal use Python 3.12 y ejecute `python3 scripts/build_portal.py public` en la raíz. Abra `public/index.html`. Para Word y PDF ejecute `python3 scripts/build_documents.py` con Pandoc, LibreOffice, python-docx y PyMuPDF.
2. Para desplegar la infraestructura consulte los manuales y utilice los equipos y las identidades privadas del entorno de destino. Las direcciones del inventario son privadas. [Arquitectura](docs/moment-01/arquitectura.md) · [Instalación](docs/moment-01/instalacion.md) · [Administración](docs/moment-01/administracion.md)
3. Para reproducir un lote siga las etapas y las dependencias del DAG. Los archivos físicos, las consultas y sus salidas están en `datasets/`, `sql/queries/` y `results/sql/`. [Manual del lago](docs/moment-02/manual.md) · [DAG](services/airflow/dags/lago_medallion.py) · [Consultas](docs/moment-02/consultas.md)
4. Para revisar la integridad del archivo descargado, ejecute `sha256sum -c SHA256SUMS` desde el directorio que contiene el ZIP y su manifiesto. [SHA-256 del ZIP](entrega/SHA256SUMS)

La rama de entrega se mantiene en GitHub. El repositorio incluye la configuración de GitLab CI y el procedimiento para importarlo y publicar GitLab Pages en una cuenta autorizada. [Preparación de GitLab](docs/entrega/gitlab.md) · [Estado y próximas actividades](PROJECT_STATE.md)
