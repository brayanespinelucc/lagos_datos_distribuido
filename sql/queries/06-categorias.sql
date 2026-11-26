-- Participación de cada categoría en ventas
WITH totales AS (
    SELECT categoria, sum(ventas_cop) AS ventas_cop, sum(unidades) AS unidades
    FROM lago.gold.productos
    GROUP BY categoria
)
SELECT categoria, ventas_cop, unidades,
       round(100.0 * ventas_cop / sum(ventas_cop) OVER (), 2) AS participacion_pct
FROM totales
ORDER BY ventas_cop DESC, categoria;
