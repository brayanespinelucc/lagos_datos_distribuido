"""DAG del laboratorio comercial. Código de negocio compartido con las CLI del proyecto."""
from contextlib import contextmanager
from datetime import timedelta
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile

from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator
import pendulum


@contextmanager
def storage_environment(env, needs_s3):
    """Admite un Secret montado o una conexión AWS de Airflow con endpoint explícito."""
    if not needs_s3:
        yield env
        return
    path = env.get("LAGO_S3_ENV")
    if path:
        if not Path(path).is_file():
            raise AirflowException("LAGO_S3_ENV apunta a un archivo inaccesible")
        yield env
        return
    connection = BaseHook.get_connection(env.get("LAGO_AIRFLOW_CONN_ID", "lago_minio"))
    endpoint = connection.extra_dejson.get("endpoint_url")
    if not connection.login or not connection.password or not endpoint:
        raise AirflowException("La conexión MinIO requiere login, contraseña y extra.endpoint_url")
    settings = {"S3_ENDPOINT_HOST": endpoint, "S3_ENDPOINT": endpoint, "AWS_ACCESS_KEY_ID": connection.login,
                "AWS_SECRET_ACCESS_KEY": connection.password,
                "AWS_DEFAULT_REGION": connection.extra_dejson.get("region_name", "us-east-1")}
    if not all(isinstance(v, str) and not any(c in v for c in ("\0", "\n", "\r")) for v in settings.values()):
        raise AirflowException("Valores inválidos en la conexión de almacenamiento")
    with NamedTemporaryFile(mode="w", prefix="lago-s3-") as credentials:
        credentials.writelines(f"{k}={v}\n" for k, v in settings.items())
        credentials.flush()
        yield {**env, "LAGO_S3_ENV": credentials.name}


def execute_stage(stage):
    env = os.environ.copy()
    repo = Path(env.get("LAGO_REPO_ROOT", Path(__file__).resolve().parents[3]))
    if not env.get("LAGO_DATA_ROOT"):
        raise AirflowException("Defina LAGO_DATA_ROOT en el ejecutor")
    data = Path(env["LAGO_DATA_ROOT"]).resolve()
    python = env.get("LAGO_PYTHON", sys.executable)
    if stage == "generate":
        command = [python, str(repo / "scripts/generate_data.py"), "--output", str(data / "source")]
    else:
        command = [python, str(repo / "scripts/lake_pipeline.py"), stage, "--data-root", str(data)]
    logger = logging.getLogger("airflow.task")
    logger.info("Etapa %s · directorio de datos %s", stage, data)
    with storage_environment(env, stage != "generate") as child_env:
        with subprocess.Popen(command, cwd=repo, env=child_env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True) as child:
            for line in child.stdout:
                logger.info("%s", line.rstrip())
            code = child.wait()
            if code:
                raise AirflowException(f"La etapa {stage} terminó con código {code}")
    if stage == "validate":
        report = data / "run/quality.json"
        summary = json.loads(report.read_text())
        logger.info("Control de calidad completado · %s · %d campos", report.name, len(summary))


with DAG(
    dag_id="lago_medallion",
    description="Ventas sintéticas, MinIO, transformaciones Spark y publicación de catálogo.",
    schedule="0 6 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    dagrun_timeout=timedelta(minutes=60),
    default_args={"owner": "ingenieria-datos", "retries": 2, "retry_delay": timedelta(seconds=30),
                  "retry_exponential_backoff": True, "execution_timeout": timedelta(minutes=25)},
    tags=["momento-02", "minio", "spark"],
    doc_md="""Cada día a las 06:00 UTC se regenera el lote sintético reproducible. Una ejecución escribe
    en Bronze, transforma mediante Spark, comprueba la calidad y publica los metadatos exportados.
    La última tarea utiliza el publicador de metadatos del proyecto. Su informe distingue el catálogo
    exportado de los servicios de gobierno consultados durante la ejecución.""",
) as dag:
    def task(task_id, stage):
        return PythonOperator(task_id=task_id, python_callable=execute_stage, op_args=[stage], do_xcom_push=False)

    generate = task("generate_sources", "generate")
    ingest = task("ingest_bronze", "ingest")
    transform = task("transform_silver_gold", "transform")
    validate = task("validate_quality", "validate")
    catalog = task("publish_catalog", "catalog")
    generate >> ingest >> transform >> validate >> catalog
