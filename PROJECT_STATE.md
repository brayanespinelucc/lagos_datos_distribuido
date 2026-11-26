# Estado del proyecto

## Próxima actividad

**Momento 1 · RKE2 y su balanceador Kubernetes.** Contrastar las evidencias existentes de admisión de manifiestos y de HAProxy con los criterios del servidor, los dos workers y el estado Ready. Registrar qué se validó en el entorno disponible y qué requiere el clúster objetivo. [Admisión](evidence/moment-01/kubernetes/admision.json) · [Balanceador Kubernetes](evidence/moment-01/kubernetes/balanceador.json)

**Punto de control de esta ejecución.** Docker 29.9.2 funciona en modo rootless con controlador cgroup `none`. El contenedor de systemd de las pruebas oficiales de RKE2 terminó con código 255. Kind devolvió código 1 y solicitó delegación de cgroups. Se continúa con un ejecutor remoto para intentar la topología de tres nodos y P5. [RKE2](evidence/moment-01/kubernetes/p5/codex/rke2.json) · [Docker y Kind](evidence/moment-01/kubernetes/p5/codex/docker-kind.json)

El primer runner público levantó RKE2 v1.35.8+rke2r1 con un control plane y dos workers Ready. El supervisor y la API respondieron por HAProxy, y el Deployment presentó dos pods Running en workers distintos. La conexión directa entre las IP de pod agotó su tiempo antes de ordenar el apagado. La repetición prepara Canal con rutas host-gw en el puente L2 dedicado. [Acta del ensayo inicial](evidence/moment-01/kubernetes/p5/ensayos/45851500040/p5.json)

El segundo pipeline conservó tres nodos Ready, dos pods y dos endpoints. Canal figuró 0/3 en la consulta del DaemonSet y el balanceador presentó backends inestables. Se prepara un último ensayo acotado con propagación de montajes dentro de los nodos desechables y captura de los registros del CNI. La entrega urgente continúa en paralelo con las evidencias de los momentos 2 y 3. [Segundo ensayo](evidence/moment-01/kubernetes/p5/ensayos/45852407871/p5.json)

## Último componente terminado en este entorno

**MinIO y HAProxy.** Se corrigió el falso fallo de IAM. La versión ensayada de `mc` devolvió código 1 y el mensaje `Insufficient permissions to access this path`. La política autoriza operaciones en Bronze. Con la misma identidad, `ingesta-lab`, se cargó y descargó el CSV en Bronze, y los PUT firmados en Silver y Gold devolvieron `403 AccessDenied`. El administrador recibió `404 NoSuchKey` al consultar las dos claves. Se preservó el acta del fallo inicial. [Acta aprobada](evidence/moment-01/minio/validacion/result.json) · [Acta histórica](evidence/moment-01/minio/result.json)

Se ejecutaron tres contenedores MinIO, seis volúmenes de datos y un balanceador HAProxy sobre un único host. Los seis trayectos entre nodos devolvieron HTTP 200. P3 conservó cuatro discos, lectura y escritura durante la caída de un nodo. P4 reintegró el mismo contenedor y sus volúmenes, recuperó los seis discos y comprobó los hashes de ambos objetos desde cada servidor. En las fases estables el balanceador distribuyó seis peticiones en proporciones 2/2/2, 3/3/0 y 2/2/2. La consola quedó documentada con tres capturas. Los instaladores para las VM objetivo están preparados y su ejecución en Proxmox queda pendiente. [Manual de MinIO y HAProxy](docs/moment-01/minio.md) · [Evidencias y hashes](evidence/moment-01/minio/SHA256SUMS)

El commit `857b5ab` conserva el laboratorio, los instaladores, los manuales y las evidencias. Al reanudar se comprobaron los nueve archivos del manifiesto y se conciliaron las actas aprobadas con las filas de trazabilidad correspondientes.

## Componente anterior

**Validación portátil del aprovisionamiento Proxmox VE y Ubuntu Server 24.04.** Se reutilizaron el inventario, el aprovisionador y la suite del componente. El generador produjo ocho definiciones cloud-init y ocho archivos de firewall. La regla `sudo` de la plantilla se corrigió al contrastarla con el esquema de Canonical 24.1.3. El inventario rechaza ahora direcciones de red y de difusión para gateway, DNS e hipervisor. Pasaron las 11 pruebas, incluidas la concordancia entre inventario, figura y configuración de red, la repetición del render y las salvaguardas de discos.

El plan asigna 26 vCPU, 50 GiB de RAM y 380 GiB de discos virtuales. Las VM desplegadas en esta prueba y los pares medidos fueron cero. El ejecutor carece de KVM y Proxmox. El manifiesto de la imagen de Ubuntu respondió HTTP 403 desde el entorno. En un host compatible quedan pendientes la verificación de la imagen firmada, el arranque de las ocho VM y la medición de los 56 trayectos. El despliegue está preparado y su comprobación operativa permanece abierta. [Acta](evidence/moment-01/proxmox/validacion.json) · [Manual](docs/moment-01/proxmox-ubuntu.md)

## Continuidad

- El commit `dbc27f4` conserva el primer avance de Bloque 0 y Momento 1 sobre `e2afb46` de `main`. El PDF tiene ocho páginas y el prompt adjunto se conserva íntegro en `PROJECT_MASTER_PROMPT.md`.
- El commit `019deed` guarda los archivos que ya existían al reanudar esta ejecución, incluidas configuraciones, datasets, resultados, portal, documentos y guion. La matriz conserva sus 83 requisitos. Para el alcance de cada evidencia consulte el acta del componente.
- El objetivo completo incluye los tres momentos, las seis pruebas y la entrega académica final. GitHub sigue siendo el repositorio de trabajo y GitLab el destino académico. El alumno autorizó el acceso público por enlace al portal. Las siguientes ejecuciones se realizan por componente y reutilizan las dependencias y los resultados disponibles.
