# Secuencia de construcción y criterios de revisión

Cada bloque produce un artefacto inspeccionable y registra su verificación. La planificación académica se deriva del PDF de ocho páginas. Los resultados alcanzados y sus dependencias abiertas se consultan en el estado y la matriz. [Estado](../../PROJECT_STATE.md) · [Matriz](../../REQUIREMENTS_MATRIX.csv)

| Bloque | Trabajo y dependencia | Salida que permite revisarlo |
|---:|---|---|
| 0 | Leer PDF y figuras, analizar alternativas y recursos, conservar el encargo. | Matriz con páginas, lectura, sondeo, estrategia y caso de negocio. |
| 1 | Fijar inventario, arquitectura y organización del Git existente. | IP, roles, fuentes de los diagramas y decisiones versionadas. |
| 2 | Traducir inventario a Proxmox y Ubuntu. | Plan de provisión, personalización Cloud-init y prueba de pares en VM. |
| 3 | Preparar y ejecutar almacenamiento en los recursos disponibles. | Tres nodos identificados, IAM, buckets, lectura/escritura y hashes. |
| 4 | Configurar servidor, dos agentes y balanceadores. | Manifiestos, validación, comprobaciones de red y condiciones de nodos cuando existan. |
| 5 | Generar las fuentes, organizar la carga y transformar el lote. | DAG, Bronze/Silver/Gold, reportes de Spark y consultas Trino. |
| 6 | Catalogar los activos de las tres capas. | Diccionario, propietarios, clasificación y linaje de los transformados. |
| 7 | Recolectar series e identificar el origen de cada métrica. | Endpoints, reglas y tableros consultables. |
| 8 | Ensayar exactamente los seis escenarios de página 7. | Informe por caso con estado observado, restricciones y referencias. |
| 9 | Integrar exportaciones y documentos al portal. | Prueba de navegación, accesibilidad de descargas y copia sin conexión. |
| 10 | Consolidar documentos verificables. | Fuentes editables, DOCX, PDF y revisión visual. |
| 11 | Preparar explicación y material audiovisual. | Presentación y video reproducible con duración comprobada. |
| 12 | Auditar archivos, correspondencia de tecnologías y publicación. | Incumplimientos y causas. URL sólo si existe acceso comprobado. |
| 13 | Empaquetar preservando rutas, preparar el correo. | ZIP probado, manifiesto de hashes y borrador para el profesor. |

En la matriz, una celda vacía de evidencia indica ausencia de archivo que satisfaga el criterio. Los caminos son relativos al repositorio y varios caminos se separan con barra vertical. En la columna de página, las comas enumeran páginas físicas del PDF, numeradas desde 1. Una prueba puede tener evidencia parcial aunque el requisito global siga pendiente en el clúster exigido.
