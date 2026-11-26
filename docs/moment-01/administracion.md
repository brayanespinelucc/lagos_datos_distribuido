# Manual de administración de infraestructura

Este manual corresponde al Momento 1, páginas 3 y 4 de la guía. El operador atiende el host físico, los balanceadores, el conjunto MinIO y los nodos RKE2 como dominios de fallo distintos. Las direcciones de las VM corresponden al diseño. Los puertos publicados en loopback por un laboratorio efímero se consultan en el acta de esa ejecución. [Arquitectura](arquitectura.md) · [Plan e instalación](instalacion.md) · [Inventario](../../infrastructure/proxmox/inventory.json)

## Al inicio de la jornada

| Dónde | Consulta de lectura | Qué comprobar |
|---|---|---|
| Proxmox | `qm list`, `pvesm status`, `ip -brief address show vmbr0` | Comparar VMID, nombres y número de invitados con el inventario. Confirmar almacenamiento disponible y bridge activo. |
| Cada VM Ubuntu | `hostnamectl`, `ip -br address`, `timedatectl`, `systemctl --failed` | Host, IP, hora y unidades fallidas. En cada VM MinIO comparar ambos montajes con el identificador de su disco. |
| Balanceadores | `systemctl is-active haproxy`, `haproxy -c -f /etc/haproxy/haproxy.cfg`, `journalctl -u haproxy --since today` | Comprobar sintaxis y estado del servicio. Validar además una operación de cliente por cada punto de acceso. |
| Administrador S3 | `mc admin info ALIAS`, `mc ls ALIAS` | Deben verse los tres servidores, los seis discos y los buckets bronze, silver y gold. ALIAS es un perfil privado preconfigurado de mc. |
| Operador RKE2 | `kubectl get nodes -o wide`, `kubectl get pods -A -o wide`, `kubectl get --raw='/readyz?verbose'` | Contrastar las tres condiciones Ready con las IP y los roles esperados. Revisar reinicios, pods pendientes y últimos eventos. |

Las VM del inventario se comprueban con 56 trayectos dirigidos entre ocho invitados. El proyecto conserva una sonda SSH que acepta una clave de operador y un archivo de huellas de host. Su resultado debe incluir origen y destino por trayecto. [Procedimiento de aprovisionamiento y verificación](proxmox-ubuntu.md)

## Accesos y cambios

- Use una identidad de operador para Proxmox y el kubeconfig de administración guardado con modo 0600. La cuenta de carga a Bronze es `ingesta-lab`. Los agentes RKE2 se unen con el token seguro distribuido por un canal privado. Registre en las actas los roles y el resultado de cada operación. [Instalación RKE2](rke2.md)
- Antes de cambiar HAProxy, conserve la configuración vigente, valide el fichero candidato con `haproxy -c`, recargue la unidad y consulte la API y su ruta de aplicación. Si la recarga falla, restaure la copia anterior y compruebe de nuevo ambos recorridos. [HAProxy para objetos](../../infrastructure/load-balancers/minio/haproxy.cfg) · [HAProxy para Kubernetes](../../infrastructure/load-balancers/kubernetes/haproxy.cfg)
- Para investigar un error de escritura, conserve identidad, bucket, clave de prueba, operación firmada, HTTP y código S3. Pida al administrador un HEAD o GET de la misma clave. El caso ensayado dio `403 AccessDenied` para Silver y Gold y `404 NoSuchKey` en la consulta administrativa. [Acta de IAM y almacenamiento](../../evidence/moment-01/minio/validacion/result.json)
- Una consulta de salud solo acredita el recurso consultado. Complete el diagnóstico descargando un objeto con SHA-256 conocido o solicitando la aplicación detrás del Service según el componente afectado. [Procedimiento MinIO](minio.md) · [Ensayo Kubernetes](rke2.md)

## Cierre del turno

Registre versión o digest de cada componente intervenido, hora UTC, estado previo, acción, resultado y evidencia asociada. Si el mismo equipo representa varios nodos en un ensayo, especifique si son contenedores o procesos. Conserve las rutas de las copias de seguridad y la fecha de su última prueba de restauración en el registro privado del operador. [Manual de recuperación](../entrega/recuperacion.md) · [Índice de evidencias](../../EVIDENCE_INDEX.md)
