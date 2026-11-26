-- Diez referencias con menor existencia y sus ventas históricas
WITH vendido AS (
    SELECT sucursal_id, producto_id, sum(cantidad) AS unidades_vendidas
    FROM lago.silver.ventas GROUP BY sucursal_id, producto_id
), inventario AS (
    SELECT fecha, sucursal_id, producto_id, existencias,
           row_number() OVER (PARTITION BY sucursal_id, producto_id ORDER BY fecha DESC) AS orden
    FROM lago.silver.inventario
)
SELECT i.fecha, i.sucursal_id, i.producto_id, i.existencias,
       coalesce(v.unidades_vendidas, 0) AS unidades_vendidas_lote
FROM inventario i
LEFT JOIN vendido v ON v.sucursal_id = i.sucursal_id AND v.producto_id = i.producto_id
WHERE i.orden = 1
ORDER BY i.existencias, unidades_vendidas_lote DESC, i.sucursal_id, i.producto_id
LIMIT 10;
