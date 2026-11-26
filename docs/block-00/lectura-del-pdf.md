# Lectura del documento del profesor

El archivo original contiene ocho páginas de tamaño carta. Su SHA-256 es `733d22aed967778381b07fbd1e15a5284f275cd8abd15b9ab7f04579e881b532`. Para extraer el texto se utilizó Poppler. Se inspeccionaron por separado los dos diagramas incrustados. El primero establece la topología física y virtual. El segundo precisa dónde concluye el flujo de datos mínimo. [PDF original](../../Lago%20de%20Datos%20Distribuido.pdf)

| Página | Información examinada y efecto en la implementación |
|---|---|
| 1 | El objetivo integra virtualización, almacenamiento, orquestación, procesamiento, gobierno y monitoreo con software abierto. El diagrama muestra un servidor físico, Proxmox, una VM de balanceo para cada clúster, tres nodos de objetos y un master con dos workers. Los seis servicios de Kubernetes se relacionan con el almacenamiento de objetos. La tabla inicia las tecnologías obligatorias y permite HAProxy o NGINX. |
| 2 | Se completan las tecnologías obligatorias, incluidas GitLab y Python 3. La tabla fija seis servicios mínimos dentro de Kubernetes y su función. El reparto inicial Airflow/Spark en worker 1 y Trino/DataHub/Prometheus/Grafana en worker 2 se presenta como recomendación. |
| 3 | Se admite que Kubernetes reprograme los pods. Momento 1 equivale a 30 %. Pide Proxmox, VM, red y comunicación entre todas. Para MinIO exige consola, buckets, usuarios, políticas, transferencia y comunicación entre nodos. Para RKE2 exige master, workers unidos y todos Ready. |
| 4 | Completa M1 con dos balanceadores operativos, seis documentos/productos gráficos y las demostraciones de Proxmox, MinIO, transferencias, Kubernetes y comunicación. Momento 2 equivale a 35 %. Requiere DAG funcional de ingesta, transformación por Spark y consultas Trino sobre MinIO. |
| 5 | DataHub debe registrar datasets, metadatos, diccionario, propietarios, clasificación y linaje. El diagrama enlaza las fuentes con Airflow, Bronze, Spark, Silver, Spark, Gold, Trino y el resultado de la consulta SQL. |
| 6 | M2 pide manuales del lago y gobierno, diccionario, catálogo, documentación de DAG y código en GitLab. La sustentación abarca ejecución del DAG, carga, transformación, consulta y visualización de catálogo y linaje. Momento 3 equivale a 35 %. Exige Prometheus, Grafana y comienza los indicadores mínimos de CPU, memoria y disco. |
| 7 | Completa los indicadores con estados de VM, Kubernetes, MinIO, Airflow y Trino. Fija seis pruebas de operación y recuperación, cuatro manuales y una sustentación integral que justifique decisiones. |
| 8 | Consolida arquitectura, instalación, administración, lago, gobierno, operación, monitoreo, diccionario, catálogo, código en GitLab, DAG Airflow, scripts Python y video de 15–20 minutos. Recuperación y buenas prácticas siguen vigentes por la página 7. |

La matriz agrupa una vez cada producto repetido en páginas distintas y conserva todas las referencias. Las acciones operativas y las demostraciones se mantienen en filas diferentes, porque el profesor solicita tanto el servicio como la capacidad de mostrarlo. Los pesos 30/35/35 proceden del enunciado. Los criterios de aceptación concretos, tamaños de muestra, puertos, paridad y pruebas de integridad son decisiones del proyecto. El profesor no asigna porcentajes a cada fila. [Matriz de trazabilidad](../../REQUIREMENTS_MATRIX.csv)

## Diferencias y ampliaciones del encargo

| Aspecto | Tratamiento |
|---|---|
| Repositorio | El PDF exige GitLab en las páginas 2, 6 y 8. Se sigue la instrucción de comenzar desde el GitHub ya conectado y se mantiene GitLab como criterio de entrega independiente. |
| Consulta y gobierno | El último nodo de la figura de la página 5 es el resultado SQL. El prompt añade DataHub al recorrido. Se publica linaje y metadatos en una rama de gobierno y se conserva la consulta Trino como salida analítica. |
| Recuperación de un worker | P5 en la página 7 exige apagar el worker y analizar el clúster. Un cordon o drain acredita mantenimiento programado. Para registrar P5 completa se requiere observar pérdida real del nodo y sus consecuencias. |
| Demostración remota | Portal, ZIP, capturas, presentación, guion y correo son formas de entregar y explicar el trabajo solicitadas por el estudiante. Web, comprobación estática y simulaciones se identifican por su procedencia. El video de 15–20 minutos sí figura en el PDF. |
| Nombres y ubicación | Las capas se escriben Bronze, Silver y Gold en el enunciado. Los identificadores de bucket se escriben en minúscula según convenciones S3. IP, tallas, cantidades de discos y productos comerciales sintéticos son decisiones de implementación. |

## Seis comprobaciones exigidas

| ID | Condición que debe observarse | Evidencia mínima para revisar |
|---|---|---|
| M3-P1 | Ingesta automática mediante Airflow | Identificador del DAG run y objetos creados por la ejecución |
| M3-P2 | Consulta con Trino sobre el lago | SQL, identificador del coordinador, filas y contraste |
| M3-P3 | Pérdida de un nodo MinIO | Estado base, caída identificada, discos y lecturas/escrituras durante el evento |
| M3-P4 | Recuperación del mismo nodo MinIO | Reincorporación con sus volúmenes, acciones posteriores y hashes |
| M3-P5 | Pérdida de un worker Kubernetes | Estado anterior, transición del nodo, resultado de sus pods y disponibilidad |
| M3-P6 | Métricas visibles en Grafana | Dashboard real, datasource, intervalo temporal y estado de servicios |

Los IDs anteriores son estables. El estado y los enlaces a archivos observados se consultan en la matriz para evitar que una repetición de la prueba deje desactualizadas varias copias del resultado. [Matriz](../../REQUIREMENTS_MATRIX.csv) · [Evidencias](../../EVIDENCE_INDEX.md)
