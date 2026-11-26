"""Transformación del comercio sintético. Cada ruta de salida es un dataset Parquet."""
from pathlib import Path
from pyspark.sql import SparkSession

SOURCE = {
    "clientes": "cliente_id STRING, segmento STRING",
    "categorias": "categoria_id STRING, categoria STRING",
    "productos": "producto_id STRING, categoria_id STRING, precio_unitario_cop STRING",
    "sucursales": "sucursal_id STRING, region STRING",
    "transacciones": "transaccion_id STRING, fecha STRING, cliente_id STRING, sucursal_id STRING",
    "ventas": "venta_id STRING, transaccion_id STRING, producto_id STRING, cantidad STRING",
    "inventario": "fecha STRING, sucursal_id STRING, producto_id STRING, existencias STRING",
}


def transform(bronze: Path, staging: Path):
    spark = (SparkSession.builder.appName("lago-ventas-medallion")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.shuffle.partitions", "2")
             .config("spark.ui.enabled", "false").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    try:
        for table, schema in SOURCE.items():
            frame = (spark.read.schema(schema).option("header", True)
                     .option("mode", "FAILFAST").option("enforceSchema", False)
                     .option("ignoreLeadingWhiteSpace", True).option("ignoreTrailingWhiteSpace", True)
                     .csv(str(bronze / f"{table}.csv")))
            frame.createOrReplaceTempView(f"src_{table}")
        sales = spark.sql("""
            WITH unicas AS (SELECT DISTINCT * FROM src_ventas),
            ids AS (SELECT *, count(*) OVER (PARTITION BY venta_id) AS versiones FROM unicas),
            lineas AS (
              SELECT v.venta_id, v.transaccion_id, try_cast(t.fecha AS DATE) AS fecha,
                     t.cliente_id, t.sucursal_id, v.producto_id, c.categoria,
                     try_cast(v.cantidad AS INT) AS cantidad,
                     try_cast(p.precio_unitario_cop AS BIGINT) AS precio_unitario_cop,
                     CASE
                       WHEN v.venta_id IS NULL THEN 'id_nulo'
                       WHEN versiones > 1 THEN 'id_con_conflicto'
                       WHEN v.producto_id IS NULL THEN 'producto_nulo'
                       WHEN p.producto_id IS NULL THEN 'producto_desconocido'
                       WHEN try_cast(v.cantidad AS INT) IS NULL OR try_cast(v.cantidad AS INT) <= 0
                         THEN 'cantidad_no_positiva'
                       WHEN t.transaccion_id IS NULL OR try_cast(t.fecha AS DATE) IS NULL
                         THEN 'transaccion_invalida'
                       WHEN cli.cliente_id IS NULL OR s.sucursal_id IS NULL OR c.categoria IS NULL
                         THEN 'dimension_incompleta'
                       WHEN try_cast(p.precio_unitario_cop AS BIGINT) IS NULL OR
                            try_cast(p.precio_unitario_cop AS BIGINT) < 0 THEN 'precio_invalido'
                     END AS motivo
              FROM ids v LEFT JOIN src_transacciones t ON t.transaccion_id = v.transaccion_id
              LEFT JOIN src_productos p ON p.producto_id = v.producto_id
              LEFT JOIN src_categorias c ON c.categoria_id = p.categoria_id
              LEFT JOIN src_clientes cli ON cli.cliente_id = t.cliente_id
              LEFT JOIN src_sucursales s ON s.sucursal_id = t.sucursal_id
            )
            SELECT *, cantidad * precio_unitario_cop AS importe_cop FROM lineas
        """).cache()
        sales.createOrReplaceTempView("clasificadas")
        spark.sql("SELECT venta_id,transaccion_id,fecha,cliente_id,sucursal_id,producto_id,categoria,"
                  "cantidad,precio_unitario_cop,importe_cop FROM clasificadas WHERE motivo IS NULL"
                  ).createOrReplaceTempView("validas")
        outputs = {
            "silver/ventas": "SELECT * FROM validas ORDER BY venta_id",
            "silver/rechazos": "SELECT venta_id,transaccion_id,producto_id,motivo FROM clasificadas WHERE motivo IS NOT NULL ORDER BY venta_id",
            "silver/inventario": """SELECT CAST(fecha AS DATE) AS fecha, sucursal_id, producto_id,
                    CAST(existencias AS INT) AS existencias FROM src_inventario
                    ORDER BY fecha,sucursal_id,producto_id""",
            "gold/ventas_diarias": """SELECT fecha,sucursal_id,sum(importe_cop) AS ventas_cop,
                    sum(cantidad) AS unidades,count(DISTINCT transaccion_id) AS transacciones
                    FROM validas GROUP BY fecha,sucursal_id ORDER BY fecha,sucursal_id""",
            "gold/productos": """SELECT producto_id,categoria,sum(importe_cop) AS ventas_cop,
                    sum(cantidad) AS unidades FROM validas GROUP BY producto_id,categoria ORDER BY producto_id""",
        }
        for relative, query in outputs.items():
            target = staging / relative
            spark.sql(query).coalesce(1).write.mode("errorifexists").parquet(str(target))
        return {"motor": "Apache Spark", "version": spark.version, "master": spark.sparkContext.master,
                "application_id": spark.sparkContext.applicationId}
    finally:
        spark.stop()
