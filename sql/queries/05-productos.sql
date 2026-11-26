-- Diez productos de mayor facturación
SELECT producto_id, categoria, unidades, ventas_cop,
       round(100.0 * ventas_cop / sum(ventas_cop) OVER (), 2) AS porcentaje_del_total
FROM lago.gold.productos
ORDER BY ventas_cop DESC, producto_id
LIMIT 10;
