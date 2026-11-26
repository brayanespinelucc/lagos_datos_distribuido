-- Variación semanal de ventas
WITH semanas AS (
    SELECT date_trunc('week', fecha) AS inicio_semana, sum(ventas_cop) AS ventas_cop
    FROM lago.gold.ventas_diarias
    GROUP BY 1
), comparacion AS (
    SELECT inicio_semana, ventas_cop, lag(ventas_cop) OVER (ORDER BY inicio_semana) AS semana_anterior_cop
    FROM semanas
)
SELECT inicio_semana, ventas_cop, semana_anterior_cop,
       round(100.0 * (ventas_cop - semana_anterior_cop) / nullif(semana_anterior_cop, 0), 2) AS variacion_pct
FROM comparacion
ORDER BY inicio_semana;
