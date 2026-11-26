-- Conciliación del lote en las tres capas
WITH crudas AS (
    SELECT count(*) AS recibidas,
           count(*) - count(DISTINCT ROW(venta_id, transaccion_id, producto_id, cantidad)) AS duplicadas
    FROM lago.bronze.ventas
), depuradas AS (
    SELECT count(*) AS aceptadas, sum(cantidad) AS unidades, sum(importe_cop) AS importe_cop
    FROM lago.silver.ventas
), rechazadas AS (
    SELECT count(*) AS rechazadas FROM lago.silver.rechazos
), publicadas AS (
    SELECT sum(unidades) AS unidades_gold, sum(ventas_cop) AS importe_gold_cop
    FROM lago.gold.ventas_diarias
)
SELECT recibidas, aceptadas, duplicadas, rechazadas, unidades, importe_cop,
       unidades_gold, importe_gold_cop,
       recibidas = aceptadas + duplicadas + rechazadas AS conteo_concilia,
       unidades = unidades_gold AND importe_cop = importe_gold_cop AS importes_concilian
FROM crudas CROSS JOIN depuradas CROSS JOIN rechazadas CROSS JOIN publicadas;
