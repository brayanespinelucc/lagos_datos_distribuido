-- Actividad de clientes por segmento
SELECT c.segmento, count(DISTINCT c.cliente_id) AS registrados,
       count(DISTINCT v.cliente_id) AS compradores,
       coalesce(sum(v.importe_cop), 0) AS ventas_cop
FROM lago.bronze.clientes c
LEFT JOIN lago.silver.ventas v ON v.cliente_id = c.cliente_id
GROUP BY c.segmento
ORDER BY c.segmento;
