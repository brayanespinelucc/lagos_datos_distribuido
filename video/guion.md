# Guion de sustentación

La voz de esta edición es sintética, generada en español con Piper. Cada sección corresponde a una diapositiva. Los intervalos de audio medidos están en `storyboard.csv` y los subtítulos en `subtitulos.srt`.

## 01. Una plataforma para reconstruir el dato

Esta sustentación explica el diseño y la implementación de un lago de datos distribuido para una empresa comercial. La narración que se escucha es una voz sintética en español. El recorrido empieza con una pregunta que una sucursal podría plantear al cierre del día. Si aumentan los ingresos registrados, ¿podemos explicar qué productos, cantidades y transacciones produjeron ese cambio? Para responder conviene conservar la evidencia de origen, controlar las transformaciones y poder repetir las consultas. El proyecto organiza esas responsabilidades en tres momentos. El portal y el paquete descargable permiten contrastar cada explicación con archivos, resultados y limitaciones del laboratorio remoto.

## 02. Un cierre comercial que se puede auditar

Imaginemos tres sucursales que reportan ventas y existencias por separado. Una línea de venta incluye un producto y una transacción. El inventario indica cuántas unidades permanecen disponibles en cada sede. Si una venta aparece duplicada, sumarla dos veces modifica el ingreso y puede cambiar la comparación entre sucursales. Si falta la referencia del producto, la fila tampoco puede incorporarse con confianza a un indicador por categoría. La solución conserva la información que llegó y separa los registros aptos para el análisis. Los datos de este ejercicio se generaron con una semilla conocida, sin nombres reales de personas. Así se pueden provocar errores controlados y verificar sus consecuencias.

## 03. Qué pide la guía del profesor

La evaluación divide la plataforma en tres momentos. El primero, con treinta por ciento de peso, pide máquinas virtuales y comunicación, almacenamiento distribuido y Kubernetes operativos. El segundo, con treinta y cinco por ciento, incorpora la carga, las transformaciones, las consultas y el gobierno de datos. El tercero tiene el mismo peso y exige monitoreo y seis pruebas, incluida la pérdida de nodos. La matriz de trazabilidad indica para cada requisito la página del documento original, el criterio de aceptación, la evidencia y el estado. Esta distinción permite determinar qué se ejecutó en un servicio real, qué se comprobó solo en parte y qué requiere todavía el laboratorio completo.

## 04. Dos clústeres sobre el hipervisor

La arquitectura objetivo parte de un servidor dedicado con Proxmox. En el primer grupo, un balanceador conduce el tráfico de objetos y consola a tres máquinas MinIO. En el segundo, otro balanceador expone la ruta de acceso a un control plane y a dos máquinas de trabajo. Separar cómputo y almacenamiento permite retirar una tarea de transformación sin eliminar los objetos que procesaba. El servidor físico y ambos balanceadores siguen siendo dependencias compartidas. Distribuir procesos entre máquinas del mismo host ayuda ante determinadas averías de software, pero una falla eléctrica del host puede afectar todos los componentes a la vez. Por eso el inventario y el dominio de fallo se interpretan juntos.

## 05. De un inventario a ocho máquinas

Cada máquina del inventario lleva identificador, función, dirección, procesadores, memoria y discos. Las asignaciones suman cincuenta gibibytes de memoria entre los ocho invitados. El hipervisor también necesita recursos propios. El aprovisionamiento comienza revisando un plan sin reservar capacidad. El siguiente paso genera configuraciones de Ubuntu y reglas de red; el operador comprueba los identificadores, la clave pública y el disco de destino antes de aplicar. El entorno de ejecución disponible carece del dispositivo de virtualización que necesita Proxmox. Por eso se conserva la comprobación del plan y de las plantillas. La demostración de ocho máquinas encendidas y comunicadas necesita ejecutarse en un host remoto compatible.

## 06. Seguir una conexión por la red privada

Conviene leer la red desde el punto de vista de un cliente. La máquina que carga un objeto contacta con el balanceador de MinIO en el puerto nueve mil. El puerto nueve mil uno sirve a la consola. Los agentes de Kubernetes utilizan otro balanceador para registrar el nodo, y el cliente administrativo usa la entrada de la API. El diseño separa la subred de las máquinas, el rango interno de pods y el rango de servicios. Cuando se desplieguen las ocho máquinas, cada una deberá poder comprobar las otras siete. Eso produce cincuenta y seis trayectos dirigidos. Una conexión correcta desde la estación del administrador cubre solo una parte de esa verificación.

## 07. Cómo se conserva un objeto en MinIO

Cada uno de los tres nodos recibe dos unidades, formando un conjunto de seis. La política de paridad elegida distribuye cuatro fragmentos de datos y dos de paridad para el objeto de referencia. Si se pierde una máquina también dejan de estar disponibles sus dos discos. El margen de lectura y escritura debe comprobarse con el conjunto que ha quedado, el balanceador accesible y la política real del servicio. Los nombres bronze, silver y gold indican responsabilidades de los objetos, y se escriben en minúscula en la interfaz de almacenamiento. Los tres buckets usan el conjunto distribuido. Crear un bucket adicional no crea por sí mismo otro dominio físico de fallo.

## 08. Caída, recuperación e integridad

Una prueba de caída empieza guardando un objeto conocido. Se anota su tamaño y se calcula una huella digital SHA doscientos cincuenta y seis. Después se interrumpe un nodo del laboratorio aislado y se vuelve a consultar el objeto por el balanceador. Es importante anotar por separado si se pudo leer y si se pudo escribir otro objeto mientras faltaba el nodo. Al recuperar el mismo nodo se verifica el número de discos en línea, se comprueban de nuevo ambos objetos y se comparan sus huellas. El informe de las pruebas tres y cuatro explica el entorno de ejecución. Reiniciar un contenedor comparte un dominio físico distinto del que tendría una máquina en otro servidor.

## 09. Qué demuestra la API de Kubernetes

Kubernetes distingue el estado deseado de una carga y el estado que puede observarse en sus nodos. Un manifiesto puede describir dos réplicas y ser aceptado por el servidor incluso cuando aún falta un worker capaz de ponerlas en marcha. En el ensayo de admisión, un servidor de API y una base de datos etcd reciben los objetos del proyecto y rechazan una configuración con un campo inválido. La lectura de nodos del ensayo devuelve cero. La siguiente prueba en el clúster completo deberá mostrar los nombres del servidor y de los dos workers en estado operativo. También deberá comprobarse la ruta de ingreso, el volumen de la carga con estado y el efecto de retirar un worker.

## 10. El recorrido desde Bronze hasta Gold

El patrón Medallion conserva distintas versiones del valor analítico de una fuente. Bronze mantiene los archivos de entrada y sus huellas de integridad. Silver aplica el esquema, valida las llaves y conserva ventas e inventario en un formato apropiado para procesarlos. Gold resume las medidas a un nivel de negocio definido, por ejemplo las ventas diarias o el desempeño de productos. Una suma solo es interpretable si se conoce su unidad, moneda y nivel de agregación. Repetir el lote obliga a conservar relaciones y resultados coherentes. Si cambian las reglas de aceptación, la copia original permite calcular otra edición del indicador y explicar la diferencia ante el responsable comercial.

## 11. Airflow coordina las dependencias

El grafo de Airflow contiene cinco tareas en secuencia. Primero genera las fuentes y luego ingresa el lote en la capa original. A continuación ejecuta las transformaciones de Silver y Gold, valida su calidad y publica los metadatos del catálogo. La programación se define en tiempo universal coordinado y el entorno de ejecución recibe la ruta de los datos y la conexión de almacenamiento. Cuando falla una tarea, su registro y sus reintentos deben conservarse junto con la identidad de la ejecución. Una imagen del grafo muestra las dependencias. Para acreditar la carga automática se necesita además el resultado de las tareas y la evidencia de que los objetos correspondientes llegaron al almacenamiento.

## 12. Spark transforma y reconcilia

El lote pequeño contiene doscientas cincuenta y una filas de ventas originales. El generador introduce un duplicado exacto y tres defectos en campos de negocio. El procedimiento comprueba cantidades positivas y referencias de productos, normaliza los tipos y conserva el motivo del rechazo. Si las reglas se aplican como se especificaron, doscientas cuarenta y siete líneas quedarán disponibles para la capa limpia. Spark puede ejecutar el trabajo en modo local en el servidor remoto. Eso permite verificar la lógica y los archivos Parquet. Una ejecución distribuida entre workers exige un registro propio. El evaluador puede comparar el manifiesto del lote con la salida de calidad para reconciliar las filas de principio a fin.

## 13. Consultar con Trino

Las aplicaciones envían consultas SQL a Trino. El catálogo relaciona cada nombre de tabla con un esquema y con los objetos del almacenamiento. Para el laboratorio se utiliza el conector Hive y un metastore de archivos. Cuando una consulta solicita las ventas por día, el motor lee las columnas necesarias en los objetos publicados en MinIO. La evidencia debe registrar qué motor respondió, el texto de la consulta, las filas devueltas y una comparación con los resultados de la transformación. De esta forma se puede distinguir una vista previa del portal de la ejecución del motor de consultas. La vista exportada permite revisar la respuesta incluso después de apagar el laboratorio efímero.

## 14. Gobierno y linaje en DataHub

La persona que consulta una tabla necesita saber qué representa, quién puede explicarla y de dónde proceden los campos. El catálogo del ejercicio abarca siete entradas de origen, dos conjuntos limpios y dos productos analíticos. Cada ficha asocia tecnología, descripción, propietario funcional, clasificación y esquema. Una relación de linaje indica qué conjuntos alimentaron a otro. Por ejemplo, una agregación por producto depende de ventas aceptadas y de su identificación en el catálogo. La exportación conserva la información que se puede leer desde el portal. Para demostrar el servicio DataHub se comprueba por separado la aceptación y la consulta de los activos en la instancia correspondiente.

## 15. Prometheus observa los componentes

Prometheus organiza las mediciones en series temporales con etiquetas. Cada muestra necesita un instante, un componente de origen y el valor de una métrica. Al examinar una transición conviene confirmar primero que el colector alcanzaba el objetivo y que el período observado abarca el incidente. La pérdida de una muestra puede deberse a red, credenciales o a que el servicio dejó de responder. Para explicar el uso de memoria o de disco también importa saber si la medida pertenece al host, a una máquina virtual o a un contenedor. En el repositorio se pueden revisar la configuración de recolección, las reglas y sus condiciones, así como los requisitos de los servicios pendientes de instrumentar.

## 16. Grafana presenta series y estados

El diseño de monitoreo reúne vistas de infraestructura, Kubernetes, almacenamiento, procesamiento y consultas. Al abrir una vista hay que revisar el origen de datos y el intervalo de tiempo seleccionado. Una caída del servicio puede dejar una serie sin datos. Interpretar ese vacío como un valor igual a cero conduce a conclusiones incorrectas sobre memoria, conexiones o solicitudes. Durante una demostración conviene seleccionar la ventana del incidente, identificar las etiquetas del objetivo y compararla con la respuesta observada por el cliente. El material del proyecto separa las configuraciones importables de las capturas y mediciones realmente obtenidas. Esa distinción permite usar el portal aunque la instancia efímera haya terminado.

## 17. Seis pruebas con criterios observables

La primera prueba sigue una carga automática desde Airflow. La segunda solicita información al motor Trino y analiza las filas que entrega. La tercera retira un nodo MinIO y compara disponibilidad y quórum. La cuarta recupera ese nodo y comprueba nuevamente los objetos. La quinta exige retirar un worker de Kubernetes y observar el estado de los pods, su reprogramación y los efectos del almacenamiento. La sexta consulta las métricas y el estado de la plataforma en Grafana. Cada prueba se documenta con precondiciones, comandos, resultado esperado y resultado observado. Cuando falta un nodo físico o un servicio, el expediente conserva el límite y la operación necesaria para completar la demostración.

## 18. Leer un resultado de principio a fin

Tomemos la fuente de ventas como ejemplo de auditoría. El manifiesto registra cuántas filas contiene el archivo y una huella de su contenido. El informe de calidad debe explicar qué pasó con el duplicado y con las tres líneas defectuosas. Las aceptadas alimentan los importes por fecha y por producto. Una consulta puede volver a sumar esos importes y confrontarlos con la capa limpia. Así, un resultado analítico tiene varias comprobaciones independientes. Si los totales difieren, se localiza el primer punto en que cambia el conteo, la clave de unión o la unidad de medida. Los archivos de evidencia permiten repetir esa revisión sin mantener el clúster abierto.

## 19. Alcance y límites del laboratorio

El servidor disponible para el trabajo tiene una cuota de dos procesadores y ocho gibibytes de memoria según sus grupos de control. El hipervisor de la arquitectura completa debe alojar ocho máquinas y reservar recursos para sí mismo. Para aprovechar el entorno se ejecutan componentes por bloques y se exportan sus resultados antes de liberar recursos. Esto permite comprobar la lógica del sistema y medir operaciones concretas. Todavía se deben distinguir las pruebas en un host compartido, las pruebas de admisión y las que requieren un clúster completo. El informe identifica por qué una configuración aceptada o un segmento de vídeo no sustituyen la demostración de disponibilidad real en Proxmox y RKE2.

## 20. Recorrer el portal de consulta

El portal estático es el punto de entrada del profesor. En su portada se consulta el alcance de los momentos y desde la navegación se puede abrir la infraestructura, la trazabilidad y las evidencias. Conviene comenzar con un requisito de la matriz, seguirlo hasta el componente y revisar después el archivo original de resultados. El centro documental conserva informes y formatos editables. Las vistas de datos utilizan recursos exportados que se pueden revisar desde el navegador. Esta organización permite consultar el trabajo por correo y por enlace sin encender el computador personal del estudiante. El paquete descargable contiene además los materiales para repetir los ensayos en otra infraestructura autorizada.

## 21. Conclusiones y referencias

El valor del lago de datos surge de poder seguir una decisión desde el indicador hasta el archivo de origen. El primer momento separa infraestructura, almacenamiento y cómputo. El segundo relaciona las reglas de negocio con los datos limpios, las agregaciones y el catálogo. El tercero contrasta la disponibilidad con observaciones recogidas durante fallos y recuperaciones. La matriz de requisitos, el índice de evidencias y el informe técnico permiten saber con precisión cuáles de esas afirmaciones se demostraron en cada entorno. Para profundizar están las referencias a la guía del profesor y a la documentación oficial de cada tecnología. Con esta ruta el evaluador puede revisar la implementación, sus resultados y las condiciones pendientes.
