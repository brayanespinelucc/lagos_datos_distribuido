CREATE SCHEMA IF NOT EXISTS lago.bronze
WITH (location = 'local:///warehouse/bronze');

CREATE SCHEMA IF NOT EXISTS lago.silver
WITH (location = 'local:///warehouse/silver');

CREATE SCHEMA IF NOT EXISTS lago.gold
WITH (location = 'local:///warehouse/gold');

CREATE TABLE IF NOT EXISTS lago.bronze.archivos_csv (
    c1 varchar, c2 varchar, c3 varchar, c4 varchar
)
WITH (
    format = 'CSV',
    external_location = 's3://bronze/',
    skip_header_line_count = 1
);

CREATE OR REPLACE VIEW lago.bronze.clientes AS
SELECT c1 AS cliente_id, c2 AS segmento
FROM lago.bronze.archivos_csv
WHERE "$path" = 's3://bronze/clientes.csv';

CREATE OR REPLACE VIEW lago.bronze.categorias AS
SELECT c1 AS categoria_id, c2 AS categoria
FROM lago.bronze.archivos_csv
WHERE "$path" = 's3://bronze/categorias.csv';

CREATE OR REPLACE VIEW lago.bronze.productos AS
SELECT c1 AS producto_id, c2 AS categoria_id, c3 AS precio_unitario_cop
FROM lago.bronze.archivos_csv
WHERE "$path" = 's3://bronze/productos.csv';

CREATE OR REPLACE VIEW lago.bronze.sucursales AS
SELECT c1 AS sucursal_id, c2 AS region
FROM lago.bronze.archivos_csv
WHERE "$path" = 's3://bronze/sucursales.csv';

CREATE OR REPLACE VIEW lago.bronze.transacciones AS
SELECT c1 AS transaccion_id, c2 AS fecha, c3 AS cliente_id, c4 AS sucursal_id
FROM lago.bronze.archivos_csv
WHERE "$path" = 's3://bronze/transacciones.csv';

CREATE OR REPLACE VIEW lago.bronze.ventas AS
SELECT c1 AS venta_id, c2 AS transaccion_id, c3 AS producto_id, c4 AS cantidad
FROM lago.bronze.archivos_csv
WHERE "$path" = 's3://bronze/ventas.csv';

CREATE OR REPLACE VIEW lago.bronze.inventario AS
SELECT c1 AS fecha, c2 AS sucursal_id, c3 AS producto_id, c4 AS existencias
FROM lago.bronze.archivos_csv
WHERE "$path" = 's3://bronze/inventario.csv';

CREATE TABLE IF NOT EXISTS lago.silver.ventas (
    venta_id varchar,
    transaccion_id varchar,
    fecha date,
    cliente_id varchar,
    sucursal_id varchar,
    producto_id varchar,
    categoria varchar,
    cantidad integer,
    precio_unitario_cop bigint,
    importe_cop bigint
)
WITH (format = 'PARQUET', external_location = 's3://silver/ventas/');

CREATE TABLE IF NOT EXISTS lago.silver.inventario (
    fecha date,
    sucursal_id varchar,
    producto_id varchar,
    existencias integer
)
WITH (format = 'PARQUET', external_location = 's3://silver/inventario/');

CREATE TABLE IF NOT EXISTS lago.silver.rechazos (
    venta_id varchar,
    transaccion_id varchar,
    producto_id varchar,
    motivo varchar
)
WITH (format = 'PARQUET', external_location = 's3://silver/rechazos/');

CREATE TABLE IF NOT EXISTS lago.gold.ventas_diarias (
    fecha date,
    sucursal_id varchar,
    ventas_cop bigint,
    unidades bigint,
    transacciones bigint
)
WITH (format = 'PARQUET', external_location = 's3://gold/ventas_diarias/');

CREATE TABLE IF NOT EXISTS lago.gold.productos (
    producto_id varchar,
    categoria varchar,
    ventas_cop bigint,
    unidades bigint
)
WITH (format = 'PARQUET', external_location = 's3://gold/productos/');
