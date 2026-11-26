-- Líneas exactamente repetidas en Bronze
SELECT venta_id, transaccion_id, producto_id, cantidad, count(*) AS apariciones
FROM lago.bronze.ventas
GROUP BY venta_id, transaccion_id, producto_id, cantidad
HAVING count(*) > 1
ORDER BY venta_id, transaccion_id;
