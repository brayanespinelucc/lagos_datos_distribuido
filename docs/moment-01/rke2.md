# Kubernetes, HAProxy y caída de un worker

## Instalación en la topología académica

El servidor RKE2 contiene etcd y la API. Los dos agentes ejecutan cargas de usuario. Las cuatro direcciones de esta tabla pertenecen al inventario de Ubuntu en Proxmox. [Configuración de nodos](../../infrastructure/kubernetes/nodes) · [Configuración de HAProxy](../../infrastructure/load-balancers/kubernetes/haproxy.cfg)

| Equipo | Dirección de inventario | Función |
|---|---|---|
| lb-k8s | 10.42.10.11 | 6443/TCP para la API, 9345/TCP para registro y 80/443 para el Ingress |
| rke2-server | 10.42.10.31 | etcd, API, controladores y scheduler |
| rke2-worker-1 | 10.42.10.32 | Kubelet y cargas del grupo de ingeniería |
| rke2-worker-2 | 10.42.10.33 | Kubelet y cargas del grupo de analítica |

1. En la VM dedicada `lb-k8s`, ejecute `sudo infrastructure/load-balancers/kubernetes/install.sh`. El archivo de rutas incluye comprobaciones TCP de los cuatro servicios.
2. En `rke2-server`, ejecute `sudo infrastructure/kubernetes/install-node.sh`. El instalador verifica el SHA-256 del paquete RKE2 v1.35.8+rke2r1 y crea el secreto de agente con acceso exclusivo de root.
3. Transfiera el contenido de `/var/lib/rancher/rke2/server/agent-token` por un canal administrativo autenticado al archivo `/etc/rancher/rke2/join-token` en cada worker, propietario root y modo 0600. El prefijo del token seguro incorpora la huella de la CA. Ejecute el mismo instalador en cada worker. Conserve los tokens y el kubeconfig fuera de las evidencias.
4. En el servidor, ejecute `sudo infrastructure/kubernetes/deploy.sh` y `sudo infrastructure/kubernetes/verify-live.sh`. El segundo comando consulta el API, la condición Ready, el Deployment, el StatefulSet y la ruta HTTPS del Ingress. El volumen local de registro requiere el segundo worker.
5. Para consultar la API por HAProxy desde un equipo de administración, use una copia privada del kubeconfig cuya URL de servidor sea `https://10.42.10.11:6443`. Conserve su CA y autenticación. La dirección del balanceador figura en los SAN del certificado RKE2.

## Ensayo P5 en contenedores desechables

El ejecutor crea una red y tres nodos de laboratorio. Por orden intenta RKE2 con la imagen systemd que usa el proyecto Rancher y después Kind si el arranque de RKE2 falla. En RKE2 se reutilizan los YAML originales del servidor, de ambos workers y de Traefik. En el puente Docker de capa 2, un HelmChartConfig específico del ensayo selecciona el backend host-gw de Flannel sobre eth0. Canal instala rutas a los CIDR remotos por la dirección del nodo vecino. La plantilla de las VM conserva el backend predeterminado. En Kind se conservan los CIDR, el rol de cada nodo y las etiquetas de los workers. El balanceador reenvía el acceso autenticado al API. Para el ensayo HTTP se añade un frontend dedicado que conduce al mismo Service NodePort por ambos workers. Kind carece del supervisor RKE2 de registro en 9345. [Orquestador](../../tests/kubernetes/p5-lab.sh) · [Configuración de Kind](../../tests/kubernetes/kind-p5.yaml)

Desde la raíz del repositorio, en un ejecutor Linux dedicado con Docker, kubectl y Python 3, use un directorio de evidencia nuevo. El flujo de GitHub usa un runner estándar del repositorio público y publica los archivos incluso si falla el ensayo.

```bash
export P5_OUTPUT="$(mktemp -d)"
tests/kubernetes/p5-lab.sh
```

El Deployment de prueba tiene dos réplicas y preferencia de distribución por hostname. Cada respuesta de `/identidad` incluye el nombre del pod y el nodo que realmente la produjo. Un Service NodePort en 30080 admite tráfico por ambos workers. El frontend de HAProxy usa round-robin y registra sesiones por backend. En RKE2 también se publica p5.lago.internal mediante Traefik y se prueban los frontends de Ingress en HTTP y HTTPS con un certificado interno de laboratorio. El backend al que HAProxy abre la conexión y el pod final pueden diferir porque el Service aplica la política de tráfico `Cluster`. [Aplicación de prueba](../../tests/kubernetes/aplicacion-p5.yaml)

El ejecutor coteja la identidad Docker con las etiquetas de su propio laboratorio y con el nombre del nodo antes de realizar el apagado. Registra la siguiente secuencia con tiempos UTC y conserva las respuestas HTTP en JSON Lines.

| Fase | Observación y criterio |
|---|---|
| Antes | Tres condiciones Ready verdaderas, una réplica en cada worker, EndpointSlices, acceso al kubelet y seis trayectos TCP dirigidos. Se intercambian peticiones por IP de pod y se consulta el Service por DNS. Una serie de peticiones debe aumentar los contadores de ambos backends. |
| Caída | Se detiene un solo contenedor y se verifica su estado Docker. Se espera Ready False o Unknown y la exclusión del backend por HAProxy. El monitor HTTP continúa durante la detección. |
| Reprogramación | Ambas réplicas deben estar listas en el superviviente y al menos un UID debe ser nuevo. Se comprueba que los dos endpoints están listos y que la petición llega al superviviente. La aplicación tolera durante 15 segundos los taints de nodo inalcanzable o no preparado, además del tiempo que tarde Kubernetes en detectar el fallo. |
| Recuperación | Se arranca el mismo contenedor, se comprueban el UID original del nodo, los tres Ready, ambos backends, el kubelet y el servicio. Se registran las asignaciones que decida el scheduler. Las réplicas sanas pueden permanecer en el superviviente. |

Las muestras HTTP son discretas. Una serie sin fallos solo acredita disponibilidad durante las peticiones observadas. Un servicio que sigue respondiendo tampoco acredita por sí solo que el scheduler haya repuesto la réplica. La comprobación correlaciona la identidad de cada pod, sus condiciones y los endpoints. [Código de observación y recuperación](../../tests/kubernetes/p5.py)


## Comprobación de la API en Codex

El entorno rootless dispone de kube-apiserver v1.35.0, etcd y HAProxy 3.0.11. En el ensayo local, kubectl validó el certificado, obtuvo la lista de readiness a través de HAProxy, aplicó la aplicación de prueba y consultó el inventario. La API devolvió cero nodos y cero pods. La captura se obtuvo de esa respuesta mediante Chromium y kubectl proxy. [Acta local](../../evidence/moment-01/kubernetes/p5/codex/api/api.json) · [Captura de readiness](../../evidence/moment-01/kubernetes/p5/codex/api/api-readyz.png)

Para repetir únicamente esta comprobación, use los binarios de envtest y de HAProxy disponibles en el equipo de ensayo.

```bash
python3 tests/kubernetes/admission.py /ruta/al/envtest \
  --haproxy /ruta/al/haproxy --output /ruta/nueva/evidencia-api
```
