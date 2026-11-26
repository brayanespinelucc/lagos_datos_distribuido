# Manual del lago de datos y del DAG de Airflow

## Del cierre comercial al indicador

La empresa del caso recibe siete fuentes sintéticas que describen sucursales, clientes, categorías, productos, inventario, transacciones y ventas. Una venta representa una línea de transacción. Su importe en pesos colombianos se obtiene multiplicando unidades por precio unitario del producto. El manifiesto identifica la semilla, las filas y el SHA-256 de cada CSV. El perfil pequeño utiliza la semilla 42. [Caso de negocio](../block-00/caso-de-negocio.md) · [Manifiesto del lote](../../datasets/source/lote.json) · [Arquitectura del flujo](../../architecture/diagrams/flujo.png)

| Capa | Unidad almacenada | Verificación para el operador |
|---|---|---|
| Bronze | Siete CSV conservados por nombre y un recibo local de ingesta | Comparar cabeceras, filas y SHA-256 con el manifiesto. Confirmar si el recibo registra S3. |
| Silver | Parquet de ventas aceptadas, ventas rechazadas e inventario | Revisar motivos de rechazo y recuperar el ID de la línea en Bronze para investigar. |
| Gold | Parquet de ventas por fecha y sucursal, y de ventas por producto y categoría | Conciliar importes y unidades con Silver respetando el nivel de agregación. Un cliente puede participar en varias transacciones. |

## Reproducir un lote

Ejecute las órdenes desde la raíz en un entorno remoto con Java 17 o posterior, Python y las dependencias del proyecto. Para probar únicamente los archivos locales, use un directorio nuevo. Para reproducir S3, prepare los tres buckets y proporcione a la tarea un archivo privado `LAGO_S3_ENV` con el endpoint accesible desde el ejecutor y una identidad habilitada para las operaciones de esa etapa. La configuración de boto3 utiliza SigV4 y direccionamiento por ruta. [Dependencias](../../requirements/lake.txt) · [Ingesta y controles](../../scripts/lake_pipeline.py)

```bash
export LAGO_DATA_ROOT="$(mktemp -d)"
python3 scripts/generate_data.py --output "$LAGO_DATA_ROOT/source"
python3 scripts/lake_pipeline.py ingest --data-root "$LAGO_DATA_ROOT"
python3 scripts/lake_pipeline.py transform --data-root "$LAGO_DATA_ROOT"
python3 scripts/lake_pipeline.py validate --data-root "$LAGO_DATA_ROOT"
```

En `bronze/ingesta.json` compruebe la huella del lote. En `run/spark.json` constan motor, aplicación y modo de ejecución. `run/quality.json` contiene las cuentas y `run/lake.json` las conciliaciones. El publicador de catálogo usa el mismo directorio con la etapa `catalog`, después de validar. El proceso toma un bloqueo local por directorio. Para un despliegue con ejecutores en varios hosts, decida dónde se coordina la escritura del lote. [Transformación Spark](../../services/spark/transform.py) · [Salida conservada](../../results/lake.json)

## Operar el DAG lago_medallion

El DAG tiene una sola corrida activa y una tarea activa a la vez. Su expresión `0 6 * * *` usa UTC, equivalente a la 1:00 a. m. en Colombia. `catchup=False` evita la creación automática de intervalos históricos. Las tareas disponen de dos reintentos con demora inicial de 30 segundos y retroceso exponencial. El límite del DAG es de una hora y el de cada tarea es de 25 minutos. [Fuente del DAG](../../services/airflow/dags/lago_medallion.py)

| Tarea | Entrada | Resultado que debe quedar |
|---|---|---|
| generate_sources | Semilla y tamaño de muestra | Siete CSV y lote.json en source |
| ingest_bronze | CSV y huellas | Copia íntegra de los siete ficheros y recibo de Bronze |
| transform_silver_gold | Recibo del lote y CSV verificados | Cinco tablas Parquet y registro del motor Spark |
| validate_quality | Entradas y resultados | Conteos y medidas reconciliados en quality.json y lake.json |
| publish_catalog | Lote validado | Catálogo exportado y publicación del archivo de control en Gold cuando hay S3 |

En el worker de Airflow, configure `LAGO_REPO_ROOT`, `LAGO_DATA_ROOT` y `LAGO_PYTHON`. El último apunta al Python que carga Spark, PyArrow y boto3. La conexión Airflow `lago_minio` acepta usuario, secreto y `extra.endpoint_url` cuando no se emplea el archivo privado de almacenamiento. El operador debe poder consultar los logs de las cinco tareas. En un laboratorio compartido genere un identificador de corrida nuevo para seguir el mismo lote en toda la demostración.

```bash
airflow dags list
airflow dags list-import-errors
airflow dags trigger lago_medallion
airflow dags list-runs -d lago_medallion
airflow tasks states-for-dag-run lago_medallion <run_id>
```

Reemplace `<run_id>` por el identificador devuelto por Airflow. Antes de relanzar una tarea, revise el primer error y la huella del manifiesto. Una fuente cambiada exige un nuevo lote. Un fallo transitorio permite reintentar la tarea afectada después de restablecer sus dependencias.

## Resultado de referencia y consulta

En el acta de Spark 4.0.1 el motor usó `local[2]`. De 251 líneas de entrada, 247 fueron válidas, una fue un duplicado exacto y tres quedaron rechazadas. Los motivos fueron producto nulo, producto desconocido y cantidad no positiva. Las ventas aceptadas sumaron 875 unidades y 33.589.000 COP. La conciliación registra verificación de S3. [Acta del motor](../../evidence/moment-02/spark/ejecucion.json) · [Acta de conciliación](../../evidence/moment-02/spark/conciliacion.json)

Trino 477 usa el catálogo `lago`, el conector Hive, un metastore de archivos y acceso nativo a S3. Confirme con `SHOW CATALOGS`, `SHOW SCHEMAS FROM lago` y `SHOW TABLES FROM lago.gold` qué tablas externas están registradas antes de sumar. En el informe de la consulta conserve el identificador de Trino, la sentencia y los resultados. Un modo de lectura local y un modo entre contenedores pueden requerir endpoints distintos. [Configuración de Trino](../../services/trino/compose.yaml) · [Catálogo Hive](../../services/trino/catalog/lago.properties) · [Índice de evidencias](../../EVIDENCE_INDEX.md)
