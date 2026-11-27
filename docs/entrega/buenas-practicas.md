# Manual de buenas prácticas

## Criterios de operación


## Responsabilidades y comprobaciones

| Responsable | Acción operativa | Evidencia de que se aplicó |
|---|---|---|
| Administrador de infraestructura | Mantener inventario con VMID, IP, montajes y dominio de fallo. Identificar el host único y las dependencias de cada balanceador. | Plan, diagrama y consulta real del hipervisor, con fecha y versión. [Inventario](../../infrastructure/proxmox/inventory.json) |
| Administrador de MinIO | Entregar a cada aplicación los permisos de sus buckets y operaciones. Guardar secretos en el canal privado del despliegue. | Códigos S3 de las operaciones permitidas y prohibidas, y comprobación administrativa de las claves de prueba. [Política de ingesta](../../infrastructure/minio/ingesta-bronze.json) |
| Operador RKE2 | Conservar kubeconfig, claves y token en archivos restringidos. En un cambio, validar primero los manifiestos y después el despliegue real con sus condiciones y endpoints. | `kubectl get nodes`, rollout, estado de pods y respuesta real de la aplicación. [Manual de RKE2](../moment-01/rke2.md) |
| Ingeniería de datos | Conservar la fuente, su esquema, granularidad, unidad monetaria y huella. Asignar un identificador al lote. | CSV de entrada, recibo, conciliación y motivos de rechazo vinculados por hash. [Manual del lago](../moment-02/manual.md) |
| Responsable de gobierno | Versionar propietario, descripción, clasificación y linaje junto al esquema. Cuando cambie un campo, avisar a los responsables de sus consumidores. | Registro de metadatos y dependencias para cada activo publicado. Una exportación debe identificarse por su alcance. |
| Operaciones | Etiquetar las métricas por objetivo, entorno y fecha. Separar indicadores de disponibilidad y de integridad. | Consulta, intervalo UTC, etiquetas, valores y captura coincidentes. [Manual de operación](../moment-03/operacion.md) |
| Responsable de la entrega | Revisar la copia que abrirá el profesor, buscar secretos, probar enlaces y comprobar hashes después de descargar el ZIP. | Acceso de lectura, commit, paquete fechado y manifiesto verificable. [Ruta de GitLab](gitlab.md) |

Al ampliar el laboratorio, reserve copias fuera del único host y acuerde retenciones según el valor de cada fuente. Compruebe la restauración con datos conocidos. Documente qué tareas se completaron, qué permanece pendiente y qué dato permitiría cerrar cada condición.
