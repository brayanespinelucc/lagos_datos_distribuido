-- Existencias al último corte por sucursal
WITH ultimo AS (
    SELECT fecha, sucursal_id, producto_id, existencias,
           row_number() OVER (PARTITION BY sucursal_id, producto_id ORDER BY fecha DESC) AS orden
    FROM lago.silver.inventario
)
SELECT sucursal_id, max(fecha) AS fecha_corte, count(*) AS referencias,
       sum(existencias) AS existencias, count_if(existencias = 0) AS referencias_agotadas
FROM ultimo
WHERE orden = 1
GROUP BY sucursal_id
ORDER BY sucursal_id;
