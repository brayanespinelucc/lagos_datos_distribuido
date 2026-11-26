# Publicación académica en GitLab

La guía exige el código fuente en GitLab en las páginas 6 y 8. El origen de trabajo autorizado es el repositorio GitHub del estudiante. La rama de entrega es `entrega/bloque-0-momento-1`. La URL de GitLab pasa a formar parte de la entrega una vez que el propietario confirme el espacio de nombres y un lector pueda abrir el commit. En el entorno de trabajo se identificó únicamente el remoto GitHub. [Repositorio de trabajo](https://github.com/brayanespinelucc/lagos_datos_distribuido)

## Transferir la versión de entrega

1. En la cuenta académica de GitLab, cree un proyecto vacío en el grupo o espacio autorizado. Elija su visibilidad conforme al acceso acordado con el profesor. Si la transferencia se hace mediante Git, deje el proyecto vacío de README inicial.
2. En una copia del repositorio con la rama de entrega actualizada, sustituya `<GRUPO>` en las órdenes por el espacio autorizado. Use una clave de despliegue o credencial del propietario mediante SSH o el gestor de credenciales.
3. Publique la rama bajo el nombre `main` en el proyecto vacío y contraste las dos huellas. Si se usa la importación de GitHub de GitLab en lugar de Git, seleccione la rama del avance como predeterminada y compare igualmente su commit.

```bash
git fetch origin entrega/bloque-0-momento-1
git rev-parse FETCH_HEAD
git remote add entrega-gitlab git@gitlab.com:<GRUPO>/lagos_datos_distribuido.git
git push entrega-gitlab FETCH_HEAD:refs/heads/main
git ls-remote entrega-gitlab refs/heads/main
```

Si el remoto ya existe, revise `git remote get-url entrega-gitlab` y use la dirección del proyecto autorizado. Un rechazo por historia divergente requiere revisar qué contenidos hay ya en el destino. Conservar el historial existente evita sobrescribir trabajo del grupo.

## CI, Pages y acceso del profesor

La configuración de CI usa Python 3.12. El job de verificación compila las fuentes Python, comprueba identificadores únicos en la matriz, valida el manifiesto histórico de MinIO y construye el portal estático en `public/`. El job manual de Pages usa esa misma carpeta como artefacto en la rama predeterminada. Use un runner con cuota disponible. La configuración puede revisarse con el editor de CI del proyecto antes de iniciar la pipeline. [Configuración CI](../../.gitlab-ci.yml) · [Importación desde GitHub](https://docs.gitlab.com/user/project/import/github/) · [GitLab Pages](https://docs.gitlab.com/user/project/pages/)

Para acreditar la entrega anote URL de GitLab, SHA completo, ID de pipeline y resultado, URL de Pages y fecha de una consulta externa. Abra el README, una descarga y la fuente del DAG con el permiso que tendrá el profesor. La fuente preparada para publicación se conserva en GitHub mientras se habilita el destino autorizado.
