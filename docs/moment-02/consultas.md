# Consulta SQL del lago de datos con Trino

El 26 de noviembre de 2026 el coordinador Trino 477 ejecutó quince consultas contra MinIO en el laboratorio remoto. La prueba obligatoria P2 corresponde a la página 7 del PDF del profesor. Su consulta principal, `20261126_200553_00021_sga7n`, reconcilió las tres capas y terminó en 1,72 segundos según Trino. [Acta P2](../../evidence/moment-02/trino/p2.json) · [SQL de conciliación](../../sql/queries/01-conciliacion.sql) · [Resultado CSV](../../results/sql/01-conciliacion.csv)

| Medida | Resultado |
|---|---:|
| Líneas de venta recibidas en Bronze | 251 |
| Líneas aceptadas en Silver | 247 |
| Repeticiones exactas descartadas | 1 |
| Líneas rechazadas por calidad | 3 |
| Unidades conciliadas entre Silver y Gold | 875 |
| Ventas conciliadas entre Silver y Gold | 33.589.000 COP |

La línea de venta V00000001 aparece dos veces en Bronze. Silver conservó 247 identificadores únicos. Las tres causas de rechazo fueron cantidad no positiva, producto desconocido y producto nulo, con una línea por causa. En Silver resultaron cero cantidades inválidas, cero importes incoherentes y cero claves incompletas. [Duplicados](../../results/sql/13-duplicados.csv) · [Rechazos](../../results/sql/12-rechazos.csv) · [Calidad Silver](../../results/sql/14-calidad.csv)

Centro facturó 12.052.500 COP en 44 transacciones, Occidente 11.559.500 COP en 40 y Norte 9.977.000 COP en 36. El producto P022, de la categoría Hogar, aportó 3.565.000 COP y 62 unidades. Las cifras pertenecen al lote comercial sintético usado en el proyecto. [Ventas por región](../../results/sql/03-ventas-region.csv) · [Productos](../../results/sql/05-productos.csv)

## Catálogo y correspondencia con MinIO

El conector Hive de Trino usa un metastore de archivos persistente para registrar los nombres y tipos SQL. Las tablas apuntan a objetos del servicio S3 de MinIO. Los esquemas del catálogo son `lago.bronze`, `lago.silver` y `lago.gold`. [Catálogo de Trino](../../services/trino/catalog/lago.properties) · [Definiciones SQL](../../sql/catalogo.sql)

- Bronze contiene siete CSV en la raíz del bucket. Una tabla externa expone cuatro campos de texto y siete vistas proyectan la cabecera de cada entidad. Cada vista filtra la ruta S3 exacta mediante la columna oculta `"$path"`. La cabecera queda excluida del conteo.
- Silver expone ventas, inventario y rechazos con tipos físicos Parquet. Gold expone ventas por día y sucursal y ventas por producto.
- La consulta 15 devolvió doce rutas S3 y sus conteos. El cotejo independiente recuperó los mismos objetos mediante GET a través de HAProxy. Los siete CSV coincidieron byte a byte. En los cinco Parquet los SHA-256 físicos diferían de las copias locales históricas. Al decodificar ambas versiones coincidieron todos los nombres, tipos, filas, multiplicidades y orden. La evidencia conserva ambas huellas y las firmas de contenido. [Orígenes y filas](../../results/sql/15-origenes.csv) · [Comparación de objetos](../../evidence/moment-02/trino/objetos.json)

## Ejecución reproducible

El ensayo utilizó un coordinador en el contenedor Docker `lago-sql-trino-1` y MinIO a través de su balanceador. El metastore estuvo en el volumen del coordinador. Las quince consultas, resultados, identificadores y capturas se conservan para consulta fuera del laboratorio. La instalación de Trino dentro de RKE2 queda pendiente. [Compose](../../services/trino/compose.yaml) · [Estado del coordinador](../../evidence/moment-02/trino/coordinador.png) · [Detalle real de P2](../../evidence/moment-02/trino/consulta-p2.png)

1. Prepare los buckets con el lote publicado y complete la transformación de Spark. En la red Docker de MinIO, proporcione a Compose `LAKE_DOCKER_NETWORK`, `S3_ENDPOINT`, la región y una identidad de lectura mediante las variables `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`. La política de referencia permite listar los tres buckets y leer sus objetos. [Política de lectura](../../services/trino/lectura-s3.json)
2. Desde la raíz del repositorio, arranque o reutilice el coordinador y consulte el puerto asignado. Antes de enviar SQL, verifique que `/v1/info` indique estado ACTIVE y `starting` falso.
3. Use un directorio de salida nuevo para conservar las evidencias históricas. El ejecutor registra los esquemas, vistas y tablas externas, consulta por HTTP, sigue las páginas devueltas por Trino y compara la conciliación con la evidencia de Spark.

```bash
docker compose -p lago-sql -f services/trino/compose.yaml up -d
direccion=$(docker compose -p lago-sql -f services/trino/compose.yaml port trino 8080)
curl --noproxy '*' --fail "http://$direccion/v1/info"
salida=$(mktemp -d)
python3 services/trino/consultar.py --coordinador "http://$direccion" \
  --resultados "$salida/results/sql" --evidencia "$salida/evidence/moment-02/trino"
```

Para repetir el cotejo de objetos, use el entorno Python del lago con boto3 y PyArrow. Defina `LAGO_S3_ENV` o las variables privadas de acceso y `S3_ENDPOINT_HOST` con la dirección del balanceador visible desde el ejecutor. Ejecute `python -m services.trino.comparar_objetos --output "$salida/objetos.json"`.

## Configuración de RKE2

El manifiesto preparado incorpora un Deployment de un coordinador, un Service ClusterIP, configuración generada desde las mismas fuentes y un PVC de 1 GiB. La preferencia del scheduler utiliza la etiqueta del grupo de analítica del segundo worker. Antes de aplicar, prepare en el namespace elegido el Secret `trino-s3-lectura` con las claves `acceso` y `secreto`; se requiere una StorageClass predeterminada o un PV compatible. Kustomize produjo los cinco recursos. El registro de preparación conserva la versión de kubectl y la huella del render. [Manifiesto](../../services/trino/kubernetes.yaml) · [Verificación](../../evidence/moment-02/trino/preparacion.json)

```bash
kubectl kustomize services/trino
kubectl --context "$CONTEXTO_LAB" -n "$NAMESPACE_LAGO" apply -k services/trino
kubectl --context "$CONTEXTO_LAB" -n "$NAMESPACE_LAGO" rollout status deployment/trino
kubectl --context "$CONTEXTO_LAB" -n "$NAMESPACE_LAGO" port-forward service/trino 8080:8080
```

## Consultas e interpretación

Las consultas 01–04 concilian ventas, agregan resultados por día y región, y calculan el ticket por sucursal. Las 05–08 comparan productos, categorías, clientes y segmentos. Las 09–11 cubren el último corte de inventario, prioridades de reposición por existencias y variación semanal. La primera semana no tiene base para calcular una variación y los cortes semanales de los extremos pueden ser parciales. Las 12–15 auditan rechazos, duplicados, calidad y orígenes. Cada CSV corresponde a una petición registrada por el coordinador. [Índice de resultados](../../results/sql/index.json) · [Consultas editables](../../sql/queries)
