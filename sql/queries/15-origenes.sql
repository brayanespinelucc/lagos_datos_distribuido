-- Objetos de MinIO y filas leídas por Trino
WITH archivos AS (
    SELECT "$path" AS uri FROM lago.bronze.archivos_csv
    WHERE "$path" IN (
        's3://bronze/categorias.csv', 's3://bronze/clientes.csv', 's3://bronze/productos.csv',
        's3://bronze/sucursales.csv', 's3://bronze/transacciones.csv',
        's3://bronze/ventas.csv', 's3://bronze/inventario.csv'
    )
    UNION ALL SELECT "$path" FROM lago.silver.ventas
    UNION ALL SELECT "$path" FROM lago.silver.rechazos
    UNION ALL SELECT "$path" FROM lago.silver.inventario
    UNION ALL SELECT "$path" FROM lago.gold.ventas_diarias
    UNION ALL SELECT "$path" FROM lago.gold.productos
)
SELECT uri, count(*) AS filas
FROM archivos
GROUP BY uri
ORDER BY uri;
