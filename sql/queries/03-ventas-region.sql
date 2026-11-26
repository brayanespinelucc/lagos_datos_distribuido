-- Ingresos por sucursal y región
SELECT s.sucursal_id, s.region, sum(v.ventas_cop) AS ventas_cop,
       sum(v.unidades) AS unidades, sum(v.transacciones) AS transacciones
FROM lago.gold.ventas_diarias v
JOIN lago.bronze.sucursales s ON s.sucursal_id = v.sucursal_id
GROUP BY s.sucursal_id, s.region
ORDER BY ventas_cop DESC, s.sucursal_id;
