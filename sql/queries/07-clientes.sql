-- Clientes con mayor valor de compra
SELECT v.cliente_id, c.segmento, count(DISTINCT v.transaccion_id) AS transacciones,
       sum(v.importe_cop) AS compras_cop
FROM lago.silver.ventas v
JOIN lago.bronze.clientes c ON c.cliente_id = v.cliente_id
GROUP BY v.cliente_id, c.segmento
ORDER BY compras_cop DESC, v.cliente_id
LIMIT 10;
