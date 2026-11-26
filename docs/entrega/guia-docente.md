# Guía de consulta para el profesor

El material está organizado en los tres momentos de la guía. El caso comercial utiliza datos sintéticos y expresa las ventas en pesos colombianos. Para una revisión rápida, abra una figura, localice un criterio en la matriz y siga el enlace hasta la salida original del ensayo. Los archivos estáticos se pueden consultar después del cierre de los laboratorios. [Requisitos del profesor](../../Lago%20de%20Datos%20Distribuido.pdf) · [Matriz de trazabilidad](../../REQUIREMENTS_MATRIX.csv) · [Índice de evidencias](../../EVIDENCE_INDEX.md)

| Momento y peso | Documentos de entrada | Comprobación que puede hacer el lector |
|---|---|---|
| Infraestructura · 30 % | [Arquitectura](../moment-01/arquitectura.md) · [Diagrama](../../architecture/diagrams/arquitectura.png) · [Instalación](../moment-01/instalacion.md) · [Administración](../moment-01/administracion.md) | Comparar los ocho equipos del inventario con la red propuesta. En las actas consultar el quórum de MinIO, la integridad de objetos y la condición de los nodos RKE2 efectivamente ejecutados. |
| Lago y gobierno · 35 % | [Manual del lago y del DAG](../moment-02/manual.md) · [Flujo](../../architecture/diagrams/flujo.png) · [DAG de Airflow](../../services/airflow/dags/lago_medallion.py) | Conciliar 251 líneas de entrada con 247 aceptadas, un duplicado y tres rechazadas. Seguir un dato de negocio desde su CSV hasta Parquet, SQL y su registro de metadatos. |
| Monitoreo y pruebas · 35 % | [Operación](../moment-03/operacion.md) · [Recuperación](recuperacion.md) · [Buenas prácticas](buenas-practicas.md) | Comparar marcas UTC, fuente y respuesta de cliente de cada ensayo. Confirmar en qué entorno se midió cada recurso. |

## Sustentación y entrega

Los materiales de narración, las figuras de arquitectura y las salidas originales se pueden revisar por separado. La fuente del DAG y los scripts permanecen junto a sus configuraciones en el repositorio. La matriz e índice identifican las limitaciones de cada actividad y el origen de las evidencias. [Guion de sustentación](../../video/guion.md) · [Procedimiento para GitLab](gitlab.md) · [Manual de RKE2](../moment-01/rke2.md) · [Manual de MinIO](../moment-01/minio.md)
