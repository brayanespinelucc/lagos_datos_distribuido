# Manual de operación del Momento 3

El operador determina la salud de la plataforma siguiendo una operación de cliente hasta su resultado. El docente puede revisar las actas conservadas aunque el laboratorio original haya sido retirado. La guía exige CPU, memoria, disco y el estado de VM, Kubernetes, MinIO, Airflow y Trino. [Guía del profesor, páginas 6–8](../../Lago%20de%20Datos%20Distribuido.pdf) · [Índice de evidencias](../../EVIDENCE_INDEX.md)

## Secuencia de operación

| Orden | Comprobación | Criterio de trabajo |
|---|---|---|
| 1. Identificar el entorno | Inventario, zona horaria, versión, fecha y destino del balanceador | Puede atribuirse cada medida a un host, VM, contenedor, proceso o servicio concreto. |
| 2. Comprobar acceso | API de Kubernetes con TLS, estado de MinIO y una descarga de referencia | Se conserva el resultado de aplicación además de la conectividad de red. |
| 3. Revisar recursos | Consultar CPU, memoria utilizable, sistema de archivos y objetivos de Prometheus | Se identifican el intervalo, la unidad y la máquina medida. Si falta el exporter queda una observación de falta de datos. |
| 4. Revisar el lote | En Airflow, consultar la última corrida, sus cinco tareas y la huella del lote | Una ejecución completa tiene un identificador y estados verificables. Un disparo que sigue en cola requiere seguimiento. |
| 5. Revisar la consulta | En Trino, comprobar el coordinador y ejecutar una consulta corta sobre una tabla conocida | Distinguir una comprobación de disponibilidad del coordinador de una lectura real de MinIO. |
| 6. Cerrar el parte | Guardar acta, consultas y capturas. Anotar las dependencias no observadas | Cada afirmación incluye fuente y tiempos. Registrar el alcance antes de clasificar la disponibilidad. |

Para leer la recolección de Prometheus consulte `/api/v1/targets` y la consulta `up`. Una muestra 0 indica un scrape fallido de un objetivo configurado. Una serie ausente puede corresponder a un objetivo no descubierto. Los dashboards deben mostrar qué fuente produce la señal y qué periodo se seleccionó. El estado de un nodo Kubernetes se evalúa mediante su condición Ready y los efectos sobre las cargas y el Service. [Operación Kubernetes](../moment-01/rke2.md) · [Administración del almacenamiento](../moment-01/minio.md)

## Actuación ante una incidencia

1. Identifique el objetivo afectado y registre los tiempos UTC de la última operación correcta y del primer error observado.
2. Compare los indicadores del usuario y del componente. Si HAProxy acepta TCP y el servicio devuelve un error, conserve ambas observaciones. Revise endpoints, logs y dependencias antes de reiniciar.
3. Si un productor publica incompleto, preserve el lote original y compare `lote_sha256` entre origen, recibo de Bronze y validación. Inmovilice la publicación para los consumidores hasta corregir la discrepancia.
4. Aplique el procedimiento de recuperación del componente y registre el primer éxito posterior, la identidad de la instancia y una verificación de integridad.
5. Documente muestras fallidas además de las correctas, el número de muestras y su frecuencia. Un intervalo sin peticiones no permite calcular continuidad exacta del servicio.

El cierre de una incidencia requiere comprobar el mismo recorrido de negocio que falló. Las comprobaciones con pocos usuarios, un único host o un único control plane describen esa topología. [Manual de recuperación](../entrega/recuperacion.md) · [Manual de buenas prácticas](../entrega/buenas-practicas.md)
