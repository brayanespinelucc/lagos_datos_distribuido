# Instrucciones de trabajo

Este repositorio sostiene una entrega universitaria remota. Lee el PDF original, `PROJECT_STATE.md` y `REQUIREMENTS_MATRIX.csv` antes de modificar el laboratorio. `PROJECT_MASTER_PROMPT.md` conserva literalmente el encargo adjunto. La instrucción posterior del estudiante fija el punto de partida en el GitHub conectado, con `main` como base como rama principal. Al reanudar, el estudiante amplió el alcance a los tres momentos, la auditoría y los entregables finales. El PDF del profesor prevalece en los requisitos académicos.

## Arquitectura y convenciones

- Conserva la fuente de verdad de las ocho VM en `infrastructure/proxmox/inventory.json`. La red objetivo es privada. Registra por separado las direcciones observadas en laboratorios efímeros.
- Usa Ubuntu Server 24.04 LTS en las VM objetivo, dos balanceadores HAProxy, tres nodos MinIO con dos discos por nodo y un servidor RKE2 con dos workers. Un único servidor físico, un único control plane y cada VM de balanceo constituyen puntos de fallo.
- Mantén `bronze`, `silver` y `gold` en minúscula como nombres S3. Reserva el procesamiento de fuentes comerciales sintéticas para el segundo momento.
- Desarrolla y valida en el entorno remoto. Usa GitHub como repositorio de trabajo y conserva la preparación para GitLab, requisito académico. Evita generar costos y activar facturación.
- Usa Python 3, rutas relativas a la raíz y versiones de artefactos identificables. Conserva plantillas editables junto a PDFs, diagramas y pruebas. Escribe los documentos y mensajes para evaluación en español.

## Evidencia y aceptación

1. Ubica cada cambio en un requisito de la matriz, con su página, criterio, estado y limitación. Las recomendaciones del docente conservan su carácter de recomendación.
2. Ejecuta primero las pruebas sin efectos sobre servicios externos. Los comandos de despliegue requieren un objetivo explícito. Un ensayo destructivo sobre infraestructura compartida necesita autorización para ese objetivo. En laboratorios propios usa recursos efímeros exclusivos.
3. Distingue despliegue en VM, servicio en contenedor, pruebas contra API real, comprobaciones estáticas y simulaciones. Identifica la procedencia de una captura y el alcance técnico de cada evidencia. Una condición Ready debe venir de Kubernetes.
4. Mantén fuera del control de versiones las claves SSH privadas, credenciales S3, tokens RKE2, kubeconfigs y ficheros de entorno reales. Incluye en el portal solo recursos preparados para evaluación y somete los enlaces y descargas a prueba. El correo se conserva como borrador.
5. Al cerrar un bloque actualiza `PROJECT_STATE.md`, `EVIDENCE_INDEX.md`, `ARCHITECTURE_DECISIONS.md` y la matriz. Registra el comando y el resultado observado, comprueba hashes y abre el paquete desde una extracción limpia.
