-- Ventas, unidades y transacciones por día
SELECT fecha, sum(ventas_cop) AS ventas_cop, sum(unidades) AS unidades,
       sum(transacciones) AS transacciones
FROM lago.gold.ventas_diarias
GROUP BY fecha
ORDER BY fecha;
