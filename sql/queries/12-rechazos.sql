-- Motivos de rechazo en la transformación
SELECT motivo, count(*) AS lineas_rechazadas
FROM lago.silver.rechazos
GROUP BY motivo
ORDER BY motivo;
