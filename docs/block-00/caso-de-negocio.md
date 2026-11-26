# Caso de negocio del lago de datos

Una cadena minorista colombiana concilia archivos de punto de venta con maestros comerciales y conteos de inventario por sucursal. Un archivo retransmitido puede duplicar una línea de venta y alterar el total diario. Un código de producto inexistente impide asignar categoría a esa venta. La gerencia quiere conocer el importe facturado en COP y las unidades movidas por producto y sucursal sin perder la posibilidad de revisar el archivo original.

## Fuentes y granularidad

| Fuente | Grano | Uso |
|---|---|---|
| clientes | Un cliente sintético | Segmentar el consumo sin nombres ni documentos reales |
| categorias | Una categoría | Nombrar categorías de productos |
| productos | Un producto | Relacionar categoría y precio unitario en pesos |
| sucursales | Una sucursal | Ubicar la región del punto de venta |
| transacciones | Una compra, con cliente, fecha y sucursal | Identificar la cabecera que agrupa líneas de compra |
| ventas | Una línea de una transacción | Relacionar producto y cantidad efectivamente vendida |
| inventario | Un corte por fecha, sucursal y producto | Consultar existencias por referencia |

Los identificadores, relaciones, conceptos y valores proceden de un generador sintético reproducible. La semilla y el tamaño permiten repetir el ensayo o ampliar su volumen. La fecha comercial corresponde al día de la transacción. El precio unitario asumido para este ejercicio procede del maestro del lote. En un sistema real con precios variables se conservaría el precio pactado en cada línea.

## Reglas e indicadores

1. Las claves de producto, sucursal, cliente y transacción deben tener referencia válida. Se conserva cada fila original en Bronze, incluidos duplicados y errores.
2. Una venta aceptada tiene una clave de línea única y cantidad positiva. El proceso Silver identifica líneas duplicadas y valores nulos o inválidos con un motivo auditable. Un rechazo permanece disponible para conciliación.
3. El importe de línea se calcula en COP como cantidad por precio unitario. Se usa aritmética entera en pesos en todo el recorrido.
4. El total de ventas por fecha y sucursal es la suma de importes aceptados. Las unidades son la suma de cantidades y las transacciones son el número distinto de cabeceras contribuyentes.
5. Las ventas por producto suman importes y unidades por producto y categoría. Los cortes de inventario mantienen existencias sin sumarlas entre días, porque son observaciones puntuales.
6. La suma de ventas en Gold se contrasta con Silver para el mismo lote. El portal permite consultar el diccionario, la procedencia y el resultado exportado de las consultas.

## Decisiones de información

La coordinación comercial usa el corte diario para revisar el desempeño de la sucursal. El equipo de abastecimiento compara unidades vendidas con existencias por referencia. Ingeniería de datos conserva la entrada y el registro de calidad, y publica en el catálogo qué fuente y transformación explican cada indicador. Un lote de ejemplo permite sustentar qué cambia en el negocio cuando el dato se duplica, se rechaza o se recupera.
