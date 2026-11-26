-- Controles de integridad de las ventas Silver
SELECT count(*) AS filas, count(DISTINCT venta_id) AS ventas_unicas,
       count_if(cantidad <= 0 OR cantidad IS NULL) AS cantidades_invalidas,
       count_if(importe_cop <> cantidad * precio_unitario_cop OR importe_cop IS NULL) AS importes_invalidos,
       count_if(fecha IS NULL OR cliente_id IS NULL OR producto_id IS NULL) AS claves_incompletas
FROM lago.silver.ventas;
