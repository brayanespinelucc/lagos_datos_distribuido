# Manual de instalación

## Alcance y requisitos del ejecutor

El docente puede consultar el informe y el portal sin instalar software. Este manual se dirige a quien reproduce la infraestructura en un servidor remoto autorizado. Las rutas se expresan desde la raíz del repositorio. Las direcciones de las VM pertenecen al segmento de diseño `10.42.10.0/24`.

El aprovisionamiento requiere Proxmox VE con permisos de administración, un bridge `vmbr0`, almacenamiento compatible y una imagen cloud oficial de Ubuntu Server 24.04. Reserve memoria y espacio para el host además de las asignaciones de invitados. Compruebe la capacidad efectiva con el plan del proyecto. El laboratorio efímero por componentes se puede ejecutar en un runner remoto compatible.

Antes de ejecutar cambios, verifique la puerta de enlace y el DNS en `10.42.10.1`, la dirección de administración de Proxmox en `10.42.10.2` y el segmento de acceso administrativo previsto en el inventario. Adapte el inventario a la red autorizada y al almacenamiento disponible antes de generar las configuraciones.

## Revisar y preparar las ocho máquinas

Ejecute desde el checkout en el entorno remoto. Sustituya la ruta de la clave por una **clave pública** del operador. Use una carpeta de salida destinada al laboratorio.

```bash
python3 infrastructure/proxmox/provision.py plan
python3 infrastructure/proxmox/provision.py render \
  --ssh-key /ruta/operador.pub --output /tmp/lago-config
```

Revise el plan y cada configuración generada. Compruebe identificadores libres, direcciones exclusivas, gateway, discos, usuario de acceso y clave pública. Cada nodo MinIO necesita dos volúmenes de datos con montajes persistentes en `/srv/minio/disk1` y `/srv/minio/disk2`.

Descargue en Proxmox la imagen oficial de Ubuntu y su manifiesto de sumas. Valide la firma del manifiesto con las claves de Ubuntu. Copie el SHA-256 de la imagen exacta en la variable de la sesión. El hash identifica la imagen en el acta de instalación. [Imágenes cloud de Ubuntu Noble](https://cloud-images.ubuntu.com/noble/)

```bash
python3 infrastructure/proxmox/provision.py apply \
  --ssh-key /ruta/operador.pub \
  --image /var/lib/vz/template/iso/noble.img \
  --sha256 "$SHA256_IMAGEN"
```

El comando `apply` se ejecuta en el host destinado al proyecto con los permisos correspondientes. Compruebe el estado con `qm list`. Una vez iniciadas las VM, verifique `cloud-init status --wait`, `hostnamectl`, `ip -br address` y `timedatectl` en cada invitado. Compare las salidas con el inventario.

## Activar almacenamiento y acceso S3

En cada VM MinIO compruebe los montajes mediante `findmnt /srv/minio/disk1` y `findmnt /srv/minio/disk2`. Verifique por número de serie los discos de datos asignados en Proxmox. Cuando falte un montaje, resuelva la asociación del dispositivo antes de iniciar el servicio.

Utilice el binario fijado y un directorio restringido que contenga los archivos de credenciales. Los tres nodos deben compartir la configuración distribuida y recibir los secretos por un canal autorizado. Instale el servicio de cada nodo y, en `lb-minio`, despliegue el balanceador.

```bash
sudo infrastructure/minio/install-node.sh "$DIRECTORIO_SECRETOS" "$BINARIO_MINIO"
# En la VM lb-minio
sudo infrastructure/load-balancers/minio/install.sh
```

Compruebe la salud del clúster vía `10.42.10.10:9000` y la consola por el puerto 9001 de la red administrativa. Cree los buckets `bronze`, `silver` y `gold`. Ejecute la carga y descarga con una identidad destinada a la aplicación y verifique la coincidencia de los hashes. El anexo reúne el procedimiento de instalación, las comprobaciones IAM y las pruebas de caída y recuperación. [Manual de MinIO y HAProxy](minio.md)

## Instalar RKE2 y validar la ruta de control

Aplique primero el balanceador de Kubernetes en `lb-k8s`. El servidor escucha el registro RKE2 en 9345/TCP y la API en 6443/TCP. Prepare la identidad y el token según `docs/moment-01/rke2.md`. Prevea su distribución privada a los dos workers. Confirme que la fecha y hora estén sincronizadas.

```bash
# En lb-k8s
sudo infrastructure/load-balancers/kubernetes/install.sh
# Primero en rke2-server y después en cada worker
sudo infrastructure/kubernetes/install-node.sh
# En rke2-server, después de verificar los nodos
sudo infrastructure/kubernetes/deploy.sh
```

El criterio de instalación incluye un servidor y dos workers identificables en la salida de nodos, todos en estado Ready. Compruebe también los CIDR de pods y servicios y la resolución DNS desde una carga de trabajo. Verifique por separado el registro en 9345, la API en 6443 y las rutas de aplicaciones en los workers.

## Registrar la aceptación

Prepare un archivo de claves de host SSH verificadas por un canal distinto de la propia sesión SSH. El siguiente control recorre la malla completa de ocho VM. Utilice una identidad de operador privada y capture la salida en el directorio de evidencias de esa ejecución.

```bash
python3 infrastructure/proxmox/check_mesh.py \
  --identity /ruta/clave --known-hosts /ruta/known_hosts
```

1. Compare las ocho identidades con el inventario y registre los 56 pares origen–destino.
2. Capture el panel web MinIO y la salida de administración que muestra los tres nodos. Registre el nombre del objeto, el tamaño y ambos SHA-256.
3. Conserve el estado de los nodos y las respuestas de los dos balanceadores. Acompañe cada salida de la hora, el entorno y los puertos probados.
4. Registre los bloqueos de ejecución por componente y vincule cada resultado al requisito correspondiente en la matriz.

El procedimiento detallado de Ubuntu está en `docs/moment-01/proxmox-ubuntu.md`. Para reproducir el ensayo S3, un runner remoto puede ejecutar `python tests/minio/lab.py` con Docker Compose y acceso a las imágenes fijadas. La validación portátil de Kubernetes se inicia con `python tests/kubernetes/validate.py`. Consulte las condiciones de cada anexo antes de interpretar los resultados.
