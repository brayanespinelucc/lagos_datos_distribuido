# Estado del proyecto

## Próxima actividad

**Momento 1 · MinIO.** Resolver la prueba de permisos que figura como fallida en `evidence/moment-01/minio/result.json`. El ensayo esperaba que la identidad de ingesta recibiera una denegación al escribir en Gold. Revisar la identidad y la operación que usa `tests/minio/lab.py` y contrastarlas con la política de ingesta. Guardar el resultado de esa prueba antes de avanzar a caída y recuperación.

## Último componente terminado en este entorno

**Validación portátil del aprovisionamiento Proxmox VE y Ubuntu Server 24.04.** Se reutilizaron el inventario, el aprovisionador y la suite del componente. El generador produjo ocho definiciones cloud-init y ocho archivos de firewall. La regla `sudo` de la plantilla se corrigió al contrastarla con el esquema de Canonical 24.1.3. El inventario rechaza ahora direcciones de red y de difusión para gateway, DNS e hipervisor. Pasaron las 11 pruebas, incluidas la concordancia entre inventario, figura y configuración de red, la repetición del render y las salvaguardas de discos.

El plan asigna 26 vCPU, 50 GiB de RAM y 380 GiB de discos virtuales. Las VM desplegadas en esta prueba y los pares medidos fueron cero. El ejecutor carece de KVM y Proxmox. El manifiesto de la imagen de Ubuntu respondió HTTP 403 desde el entorno. En un host compatible quedan pendientes la verificación de la imagen firmada, el arranque de las ocho VM y la medición de los 56 trayectos. El despliegue está preparado y su comprobación operativa permanece abierta. [Acta](evidence/moment-01/proxmox/validacion.json) · [Manual](docs/moment-01/proxmox-ubuntu.md)

## Continuidad

- El commit `dbc27f4` conserva el primer avance de Bloque 0 y Momento 1 sobre `e2afb46` de `main`. El PDF tiene ocho páginas y el prompt adjunto se conserva íntegro en `PROJECT_MASTER_PROMPT.md`.
- El commit `019deed` guarda los archivos que ya existían al reanudar esta ejecución, incluidas configuraciones, datasets, resultados, portal, documentos y guion. La matriz conserva sus 83 requisitos. Para el alcance de cada evidencia consulte el acta del componente.
- El objetivo completo incluye los tres momentos, las seis pruebas y la entrega académica final. GitHub sigue siendo el repositorio de trabajo y GitLab el destino académico. El alumno autorizó el acceso público por enlace al portal. Las siguientes ejecuciones se realizan por componente y reutilizan las dependencias y los resultados disponibles.
