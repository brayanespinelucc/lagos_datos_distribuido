# Decisiones de arquitectura

| ID | Decisión | Justificación y efecto | Comprobación |
|---|---|---|---|
| ADR-01 | Mantener la topología del diagrama del docente | Un servidor Proxmox, ocho VM Ubuntu 24.04, dos balanceadores, tres nodos MinIO y tres nodos RKE2. La concentración en un host limita la tolerancia a fallos físicos. | PDF pp. 1–4 e inventario |
| ADR-02 | Separar las redes de VM, pods y servicios | 10.42.10.0/24, 10.52.0.0/16 y 10.53.0.0/16 tienen rangos disjuntos. Las direcciones fijas permiten reproducir HAProxy, RKE2 y resolución interna. | Inventario y pruebas de red |
| ADR-03 | Almacenar con seis unidades, dos por servidor MinIO | Un conjunto de seis con paridad explícita EC:2 admite cuatro fragmentos de datos y dos de paridad. Perder los dos discos de un servidor deja cuatro unidades para lectura y escritura. Solo se presupone tolerancia a esa pérdida mientras todas las demás unidades y la conectividad están sanas. | Validar el conjunto, la disponibilidad y la integridad durante una interrupción |
| ADR-04 | Ejecutar componentes M1 aislados en Codex Cloud | El entorno permite separar ejecución real de servicios, verificación de manifiestos y preparación de VM. Las pruebas quedan exportadas antes de retirar los servicios. | `evidence/` y matriz |
| ADR-05 | Usar el GitHub conectado como origen de trabajo | El requisito de GitLab aparece en las páginas 2, 6 y 8 del PDF. Se conserva una CI y un procedimiento de importación hacia una cuenta autorizada. | `.gitlab-ci.yml` y manual de publicación |
| ADR-06 | Distribuir un portal estático y un paquete autocontenido | El profesor puede revisar la evidencia con un navegador, incluso sin servicios del laboratorio. El usuario autorizó acceso público al portal del corte. El paquete permite consulta por correo. | Prueba en Chromium, validación de rutas, ZIP y manifiesto |
| ADR-07 | Documentar con fuentes editables en español | El PDF no fija norma de citación. Las decisiones y fuentes técnicas se asocian a archivos y páginas. PDF y DOCX permiten evaluación y edición académica. | Documentos del Momento 1 |
