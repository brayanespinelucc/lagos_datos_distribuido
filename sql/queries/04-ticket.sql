-- Ticket promedio por sucursal
SELECT sucursal_id, count(DISTINCT transaccion_id) AS transacciones,
       sum(importe_cop) AS ventas_cop,
       round(sum(importe_cop) * 1.0 / count(DISTINCT transaccion_id), 2) AS ticket_medio_cop
FROM lago.silver.ventas
GROUP BY sucursal_id
ORDER BY ticket_medio_cop DESC, sucursal_id;
