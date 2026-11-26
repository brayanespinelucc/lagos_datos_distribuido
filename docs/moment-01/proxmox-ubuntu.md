# Aprovisionamiento de Proxmox VE y Ubuntu Server

## Resultado del ensayo

Se comprobaron las definiciones de **ocho VM**. El generador produjo ocho configuraciones cloud-init y ocho archivos de firewall. Las ocho configuraciones pasaron el esquema publicado de cloud-init 24.1.3. Las once pruebas del componente pasaron en Codex Cloud. El primer ensayo detectó que esta versión del esquema esperaba la regla `sudo` del operador en una cadena. La plantilla corregida conserva la misma regla de acceso. [Acta de validación](../../evidence/moment-01/proxmox/validacion.json)

El entorno de ejecución carece de `/dev/kvm`, `/etc/pve`, `qm` y `pvesh`. El arranque de Ubuntu, el funcionamiento del firewall en el hipervisor y la comunicación entre las VM quedan pendientes de observación en un host Proxmox. La prueba portátil usó una llave temporal para renderizar las configuraciones. Al finalizar, se retiraron la llave y los archivos temporales.

## Inventario y red propuestos

| Función | VM e IP | Capacidad por VM |
|---|---|---|
| Balanceador MinIO | 110, lb-minio, 10.42.10.10 | 1 vCPU, 1 GiB RAM, 16 GiB de SO |
| Balanceador Kubernetes | 111, lb-k8s, 10.42.10.11 | 1 vCPU, 1 GiB RAM, 16 GiB de SO |
| Almacenamiento | 121–123, minio-1 a minio-3, 10.42.10.21–23 | 2 vCPU, 4 GiB RAM, 20 GiB de SO y dos discos de 20 GiB |
| Control plane | 131, rke2-server, 10.42.10.31 | 4 vCPU, 8 GiB RAM, 40 GiB de SO |
| Workers | 132, rke2-worker-1, 10.42.10.32 y 133, rke2-worker-2, 10.42.10.33 | Worker 1 con 6 vCPU y 12 GiB RAM. Worker 2 con 8 vCPU y 16 GiB RAM. Cada uno usa 64 GiB de SO. |

Las asignaciones suman 26 vCPU, 50 GiB de RAM y 380 GiB de discos virtuales. El host necesita capacidad adicional para sus procesos, imágenes y copias. El bridge privado `vmbr0` conecta el segmento `10.42.10.0/24`. El diseño reserva `.1` para la puerta de enlace y el resolutor DNS, `.2` para Proxmox y `10.42.10.0/29` para la gestión. Cloud-init configura la resolución de los nombres internos en cada invitado. [Inventario](../../infrastructure/proxmox/inventory.json) · [Topología propuesta](../../architecture/diagrams/red.svg) · [Matriz de comunicación](../../architecture/network/communication.csv)

## Reproducir la verificación portátil

Desde la raíz del repositorio se necesitan Python 3.12, `ssh-keygen` y `jsonschema`. La versión usada figura en `requirements/verification.txt`. Para consultar la evidencia bastan el acta y el manual. El siguiente procedimiento permite volver a producirla en un entorno remoto. Conserva el esquema en la caché. El verificador coteja el SHA-256 antes de usarlo. [Esquema oficial de Canonical](https://raw.githubusercontent.com/canonical/cloud-init/24.1.3/cloudinit/config/schemas/schema-cloud-config-v1.json)

```bash
CACHE_INFRA=${TMPDIR:-/tmp}/lago-verificacion-infra
mkdir -p "$CACHE_INFRA"
ESQUEMA="$CACHE_INFRA/cloud-init-24.1.3.json"
if [ ! -s "$ESQUEMA" ]; then
  curl -fLsS https://raw.githubusercontent.com/canonical/cloud-init/24.1.3/cloudinit/config/schemas/schema-cloud-config-v1.json \
    -o "$ESQUEMA.parcial" && mv "$ESQUEMA.parcial" "$ESQUEMA"
fi
python3 tests/infra/verify.py --schema "$ESQUEMA" > "$CACHE_INFRA/validacion.json"
```

El programa ejecuta los comandos públicos `plan` y `render`, contrasta cada configuración con el esquema y cuenta sus reglas de entrada. Las pruebas comprueban también el direccionamiento del comando `qm`, su correspondencia con el diagrama, los seis discos de datos, los 56 pares dirigidos previstos, la repetición del render y la conservación de ficheros ajenos. Los hashes de entrada permiten identificar la revisión técnica probada. [Verificador](../../tests/infra/verify.py) · [Pruebas](../../tests/infra/test_provision.py)

## Despliegue en el host remoto y comprobación de invitados

1. El operador del hipervisor identifica el enlace físico y comprueba el bridge, el router, el DNS y los storages disponibles. El storage de discos debe aceptar `images` y el de personalización debe aceptar `snippets`. Revisa el firewall de Datacenter y el acceso de administración desde la red privada. El ejemplo de bridge permite adaptar el nombre del enlace físico desde la consola del host. [Ejemplo de bridge](../../architecture/network/vmbr0.interfaces.example) · [Guía de Proxmox](https://pve.proxmox.com/pve-docs/pve-admin-guide.html)
2. La edición, el nombre y el SHA-256 de la imagen Noble están fijados en el inventario. El operador verifica la firma de `SHA256SUMS` con las claves de Ubuntu y compara la imagen con el manifiesto firmado. En este ensayo la consulta HTTP del manifiesto devolvió 403. Queda pendiente cotejar esa edición con el manifiesto firmado en el host de despliegue. El aprovisionador vuelve a calcular el SHA-256 de la imagen local. [Índice oficial de imágenes Ubuntu](https://cloud-images.ubuntu.com/releases/)
3. Con `SSH_PUBLICA` apuntando a una llave pública y `IMAGEN_NOBLE` apuntando al archivo local verificado, ejecuta las comprobaciones siguientes en el host. Los ejemplos usan `local-lvm` para discos y `local` para snippets. La opción `--preflight-only` comprueba recursos existentes, ocupación de ID y coincidencia de la configuración antes de crear VM.

```bash
python3 infrastructure/proxmox/provision.py plan
python3 infrastructure/proxmox/provision.py apply --storage local-lvm --snippets local \
  --ssh-key "$SSH_PUBLICA" --image "$IMAGEN_NOBLE" --preflight-only
```

4. Tras un preflight satisfactorio, la misma invocación de `apply` sin `--preflight-only` crea e inicia las VM. Una repetición comprueba la marca de procedencia y los recursos existentes. El operador debe investigar cualquier conflicto de ID o de fichero que se registre. Conserva el listado de `qm list` y la salida de `pveversion`. [Aprovisionador](../../infrastructure/proxmox/provision.py) · [Referencia de qm](https://pve.proxmox.com/pve-docs/qm.1.html)
5. En cada invitado, comprueba `cloud-init status --wait`, `hostnamectl --static`, `cat /etc/os-release`, `ip -4 addr`, `ip route` y `timedatectl`. En los tres nodos de almacenamiento, contrasta los seriales de `lsblk -o NAME,SERIAL,SIZE,FSTYPE,MOUNTPOINTS` y los UUID de los dos montajes XFS del inventario. El inicializador identifica ambos discos antes de preparar un volumen. Una firma existente ajena impide continuar. [Inicializador de discos](../../infrastructure/ubuntu/prepare_volumes.py)
6. Con las claves de host verificadas y acceso SSH como `operador` a las ocho VM, ejecuta el comando siguiente desde la red de gestión. El archivo de salida contiene la IP esperada y observada, el resultado de ICMP y los errores SSH por cada par. Un resultado completo exige 56 pares aprobados.

```bash
python3 infrastructure/proxmox/check_mesh.py \
  --identity "$IDENTIDAD_SSH" --known-hosts "$HOSTS_VERIFICADOS" > malla-observada.json
```

Los pasos de aceptación en el host y en los invitados proporcionan la evidencia operativa requerida por las páginas 3 y 4 del PDF. [Sonda de conectividad](../../infrastructure/proxmox/check_mesh.py)
