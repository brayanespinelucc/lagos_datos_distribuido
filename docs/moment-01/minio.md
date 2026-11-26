# MinIO y HAProxy · instalación, operación y recuperación

## Laboratorio reproducible

Tres contenedores ejecutan tres procesos MinIO. Cada proceso usa dos volúmenes de datos Compose. Los seis montajes de datos se identifican por las rutas /srv/minio/disk1 y /srv/minio/disk2 de cada servidor. La imagen declara además dos montajes auxiliares fuera del conjunto. Los seis volúmenes de datos pertenecen a un conjunto de erasure coding con paridad estándar `EC:2`. Los volúmenes residen en el sistema de archivos de un solo host. La variable `MINIO_CI_CD=1` permite esa disposición en el ensayo. El balanceador HAProxy ofrece la API S3 en su puerto 9000 y la consola en 9001. Docker publica ambos en puertos efímeros de loopback. Perder el host o el único balanceador afecta el acceso al conjunto. [Compose e imágenes fijadas por digest](../../infrastructure/minio/compose.yaml) · [Configuración de HAProxy](../../infrastructure/load-balancers/minio/haproxy.cfg)

Para reproducir el ensayo completo, desde la raíz del repositorio y con Python, Docker Compose, curl con SigV4, Chromium y Playwright disponibles, ejecute lo siguiente. `--sin-captura` permite repetir sólo los ensayos funcionales. Cada invocación crea un proyecto Docker aislado, genera credenciales de uso temporal, crea los buckets vacíos y retira exclusivamente sus contenedores y volúmenes al terminar. Escribe los eventos progresivamente en un directorio nuevo bajo `evidence/moment-01/minio/runs/`. `--output` permite elegir otro directorio vacío. Las evidencias archivadas se consultan sin iniciar los servicios.

```bash
python3 -m unittest discover -s tests/minio -p test_iam.py -v
python3 tests/minio/lab.py
```

El laboratorio usa MinIO compilado desde el commit `0d7408fc9969caf07de6a8c3a84f9fbb10a6739e`, el cliente `mc` del 16 de abril de 2025 y HAProxy 3.0.11. [Prueba ejecutable](../../tests/minio/lab.py) · [Referencia de erasure coding de la revisión usada](https://github.com/minio/minio/blob/0d7408fc9969caf07de6a8c3a84f9fbb10a6739e/docs/erasure/README.md)

## Identidad, política y diagnóstico

El administrador crea `bronze`, `silver` y `gold` y asocia la política `ingesta-bronze` a `ingesta-lab`. La política permite listar Bronze y leer y escribir sus objetos. La ausencia de permisos para Silver y Gold impide escribir en esos buckets. La prueba contrasta el usuario habilitado y su política con el identificador de acceso y el endpoint del alias `ingesta`. Las claves de los alias quedan en el almacenamiento temporal del cliente. [Bootstrap](../../infrastructure/minio/bootstrap.sh) · [Política IAM](../../infrastructure/minio/ingesta-bronze.json)

El acta histórica conservó el fallo de la aserción. El nuevo ensayo repitió la operación `mc pipe ingesta/gold/prohibido` con la misma versión del cliente. Su código de salida fue 1. El mensaje real fue «Insufficient permissions to access this path». El código anterior buscaba literalmente «Access Denied» en la salida de `mc`. La API S3 devuelve ese mensaje al cliente HTTP y el código estructurado `AccessDenied`. El cliente `mc` presenta su propia redacción. [Acta histórica](../../evidence/moment-01/minio/result.json)

La corrección conserva la política. Para cada bucket protegido registra `stdout`, `stderr` y el retorno del cliente. A continuación firma un `PUT` del mismo objeto con la misma identidad y comprueba **HTTP 403 y código S3 `AccessDenied`**. Un `GET` firmado con la cuenta administrativa debe devolver **HTTP 404 y `NoSuchKey`** para la misma clave en el bucket ya creado. Una firma errónea, una llave desconocida o un bucket inexistente hacen fallar la prueba. La lectura y escritura positivas de `ventas.csv` en Bronze verifican la identidad desde el balanceador. [Pruebas de regresión](../../tests/minio/test_iam.py)

## Interpretación del ensayo de disponibilidad

- **Antes del fallo.** `mc admin info --json` identifica los tres servidores y los seis discos. El ensayo comprueba los seis trayectos dirigidos entre los tres nodos, verifica HTTP 200 y descarga el mismo CSV desde cada servidor. Para medir la distribución por HAProxy, cada solicitud HEAD lleva una etiqueta que se contrasta con el backend de su registro de acceso.
- **P3, pérdida de un nodo.** El laboratorio detiene exclusivamente el contenedor `minio-3` y conserva sus volúmenes. Registra la topología, las respuestas de los endpoints de salud de lectura y escritura, los destinos de HAProxy y la descarga del CSV original. Después escribe y descarga un objeto binario reproducible de 1 MiB mientras el nodo sigue detenido. Con seis unidades y paridad dos, quedan cuatro unidades disponibles tras perder ese nodo.
- **P4, reincorporación.** Se inicia el mismo contenedor con los mismos dos volúmenes. Para aceptar la recuperación se exige la vista de seis discos desde el servicio y desde el nodo reincorporado, las dos lecturas por cada uno de los tres servidores y una nueva escritura y descarga por el balanceador. El SHA-256 se calcula sobre los bytes originales y sobre los bytes descargados. Durante esta verificación se conserva el objeto escrito durante la caída.
- **Alcance temporal.** Los tiempos del acta incluyen comandos, sondeos y transferencias. Las muestras permiten evaluar las fases estable, degradada y recuperada. No se midió un SLA ni el tiempo máximo de interrupción desde clientes con tráfico continuo. El estado de todos los fragmentos físicos en cada disco requeriría una inspección adicional. [Referencia de HAProxy](https://docs.haproxy.org/3.0/configuration.html)

## Resultados observados

La ejecución del 26 de noviembre de 2026 comenzó a las 08:20:17 y terminó a las 08:21:54, hora de Colombia (UTC−5). El acta registra las marcas originales en UTC. La restauración utilizó el mismo identificador de contenedor y los mismos dos volúmenes de `minio-3`. [Acta funcional completa](../../evidence/moment-01/minio/validacion/result.json)

| Fase | Discos en línea | Quórum anunciado de lectura / escritura | Solicitudes HTTP 200 por backend (nodos 1 / 2 / 3) | Operación observada |
|---|---:|---|---|---|
| Nominal | 6 de 6 | 4 / 4 | 2 / 2 / 2 | Se recuperaron los 6.573 bytes originales de `ventas.csv` por el balanceador y desde cada nodo. Los seis trayectos dirigidos entre nodos devolvieron HTTP 200. |
| P3 · Nodo 3 detenido | 4 de 6 | 4 / 4 | 3 / 3 / 0 | Se leyó el CSV preexistente y se escribió y descargó `degradado.bin` de 1.048.576 bytes. La secuencia de comprobaciones duró 46,600 s. |
| P4 · Nodo 3 reincorporado | 6 de 6 | 4 / 4 | Primera serie 3 / 3 / 0. Segunda serie 2 / 2 / 2. | Los tres nodos sirvieron ambos objetos con sus hashes originales. Se escribió y recuperó un tercer archivo a través de HAProxy. La secuencia duró 7,774 s. |

El nodo 3 empezó a recibir tráfico después de superar las sondas del balanceador. Un ensayo anterior llegó a observar seis discos antes de poder leer desde ese nodo el objeto creado durante la caída. Por ello la aceptación comprueba la topología desde el propio nodo y exige lecturas directas con integridad. [Ensayo de reincorporación inicial](../../evidence/moment-01/minio/ensayos/reincorporacion-inicial/result.json)

| Objeto Bronze | SHA-256 del origen y de la descarga |
|---|---|
| `ventas.csv` | `93fcbd243fc069c94145a573a828bd5971169fa63cd0d98b59c303b5c1dbfde4` |
| `degradado.bin` | `65604a7a5af39fde4d31b36bc2a117240eac063f95c5b27a62d6094b168aecc8` |
| `recuperado.csv` | `00048ec9a81745163363c6e328bc03d6cc73574ce5413bb073bf18fe736d1e4d` |

Las capturas muestran la sesión autenticada, los tres buckets y el contenido de Bronze. Al tomar las imágenes, el contador general indicaba dos objetos y la lista del bucket ya mostraba los tres nombres. Las descargas S3 con hash acreditan el contenido. Las comprobaciones administrativas de Silver y Gold se realizaron sobre las dos claves exactas. [Consola](../../evidence/moment-01/minio/validacion/consola.png) · [Buckets](../../evidence/moment-01/minio/validacion/buckets.png) · [Objetos Bronze](../../evidence/moment-01/minio/validacion/objetos-bronze.png)

## Despliegue preparado para las VM Ubuntu del inventario

El destino propuesto son tres VM de almacenamiento con dos sistemas de archivos XFS independientes por VM, resolución interna de nombres y una VM para HAProxy. Los puertos pertenecen a la red privada del laboratorio. En un entorno con transporte por redes no confiables se necesita TLS para S3 y la consola. El ensayo aquí documentado utilizó HTTP sobre la red interna de Docker y loopback. [Inventario](../../infrastructure/proxmox/inventory.json) · [Puertos y reglas de comunicación](../../architecture/network/communication.csv)

1. En el ejecutor de preparación, extraiga el binario de la imagen usada en el ensayo. El instalador compara el SHA-256 de los bytes con el valor registrado. Transfiera el artefacto a cada VM por el canal de administración.

```bash
IMAGEN='bitnamilegacy/minio:2025.4.22-debian-12-r2@sha256:50cec18ac4184af4671a78aedd5554942c8ae105d51a465fa82037949046da01'
TEMP_MINIO=$(docker create --network none "$IMAGEN")
docker cp "$TEMP_MINIO:/opt/bitnami/minio/bin/minio" ./minio
docker rm -v "$TEMP_MINIO"
sha256sum ./minio
```

2. Distribuya por un canal privado los mismos ficheros `root_user` y `root_password` a los tres nodos. En el cliente administrativo prepare también `ingesta_password`. Use valores aleatorios y un directorio de acceso restringido. El instalador comprueba el nombre de nodo, los dos montajes XFS y sus UUID antes de habilitar el servicio. Ejecútelo por nodo, conservando el quórum durante tareas de mantenimiento. La unidad de systemd carga las credenciales desde archivos protegidos. [Instalador del nodo](../../infrastructure/minio/install-node.sh) · [Unidad systemd](../../infrastructure/minio/lago-minio.service)
3. En `lb-minio`, ejecute el instalador de HAProxy. Valida la configuración con el ejecutable de la VM y guarda una copia de la configuración anterior en la primera sustitución. El paquete HAProxy de Ubuntu puede diferir de la imagen Docker del ensayo. [Instalador del balanceador](../../infrastructure/load-balancers/minio/install.sh)

```bash
# En cada VM minio-N con los dos XFS montados
sudo infrastructure/minio/install-node.sh "$DIRECTORIO_SECRETOS" "$BINARIO_MINIO"
# En la VM lb-minio
sudo infrastructure/load-balancers/minio/install.sh
```

4. Desde un cliente privado con `mc`, exporte las variables siguientes y ejecute el bootstrap. El directorio del cliente contiene alias con material sensible. Conserve la misma fuente de contraseñas al repetirlo.

```bash
export MINIO_ENDPOINT=http://lb-minio:9000
export MINIO_SECRETS_DIR="$DIRECTORIO_SECRETOS"
export MC_CONFIG_DIR="$DIRECTORIO_PRIVADO_DE_MC"
sh infrastructure/minio/bootstrap.sh
mc admin info --json admin
mc ls admin
```

5. En la red de administración compruebe la consola en `lb-minio:9001` y las cabeceras con `curl -fsSI http://lb-minio:9000/minio/health/cluster/read` y `curl -fsSI http://lb-minio:9000/minio/health/cluster`. Supervise `systemctl status lago-minio` y `journalctl -u lago-minio` por nodo. En `lb-minio`, use `systemctl status haproxy` y su registro de acceso. Los resultados del despliegue en VM se documentarán cuando estén disponibles. [Pruebas de configuración y binario](../../evidence/moment-01/minio/preparacion.json)
