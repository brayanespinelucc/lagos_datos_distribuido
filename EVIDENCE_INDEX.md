# Índice de evidencias

## Momento 1 · Proxmox y Ubuntu

| Evidencia | Obtención y alcance | Requisitos |
|---|---|---|
| [Validación portátil](evidence/moment-01/proxmox/validacion.json) | `2026-11-26T09:37:11+00:00`. Ejecución de `plan` y `render` en Codex Cloud, validación de ocho configuraciones con el esquema de Canonical y once pruebas aprobadas. Registra también los prerrequisitos ausentes en el host. | M1-PVE, M1-UBU, M1-VM, M1-RED, M1-COM, M1-DOC-IP, M1-DOC-INST, M1-DEMO-PVE, M1-DEMO-COM |

SHA-256 del acta `9583513b3bcc03c72683d2518eb7d014ad123a5a7976f0359a415a81e4c41620`. El acta contiene los hashes de las fuentes probadas. Las verificaciones de arranque, acceso real a Proxmox y conectividad de los 56 pares de VM continúan pendientes. [Procedimiento reproducible](docs/moment-01/proxmox-ubuntu.md)
