# Procedimiento de despliegue

## 1. Arquitectura de despliegue

El proyecto utiliza Docker para ejecutar el proceso ETL y Apache Airflow para orquestarlo.

El entorno Docker se encuentra en `~/airflow-docker`, separado del directorio del proyecto ETL.

## 2. Entorno local reproducible (docker-compose del repositorio)

El repositorio incluye `docker-compose.yml` para levantar, sin dependencias
externas, un warehouse PostgreSQL y el motor ETL:

```bash
cp .env.example .env                    # definir DB_NAME, DB_USER, DB_PASSWORD
docker compose up -d warehouse          # PostgreSQL en el puerto WAREHOUSE_PORT (5435)
docker compose run --rm migraciones     # crea o actualiza la estructura
docker compose run --rm etl             # ejecuta el pipeline completo
```

Este entorno es independiente del de Airflow y usa por defecto el puerto
5435 para no chocar con el warehouse de Airflow (5434).

## 3. Servicios Docker del entorno de Airflow

| Servicio | Función | Puerto |
|---|---|---:|
| postgres | Base de datos de metadatos de Airflow | 5433 |
| scheduler | Programa y ejecuta los DAG | Interno |
| webserver | Interfaz web de Airflow | 8080 |
| warehouse | Base de datos PostgreSQL del proyecto | 5434 |

## 4. Iniciar el entorno de Airflow

Desde Ubuntu/WSL:

```bash
cd ~/airflow-docker
docker compose up -d

Comprobar el estado:
docker compose ps


5. Construir la imagen ETL
Desde Ubuntu/WSL:
docker build --build-arg ETL_VERSION=2.0.0 -t hospital-etl:2.0.0 \
/mnt/c/Users/User/Documents/proyecto_python_data_engineering

Importante: el DAG usa por defecto la imagen hospital-etl:2.0.0.
La imagen debe reconstruirse después de actualizar el código.

La imagen contiene el código Python y la configuración necesaria para ejecutar el pipeline.

6. Acceder a Airflow
Abrir en el navegador:

http://localhost:8080

El DAG principal es:

hospital_etl_pipeline

Fábrica de DAG: Airflow crea automáticamente un DAG por cada pipeline
(config/config.yaml y pipelines/<nombre>/config.yaml) a partir del archivo
dags/fabrica_pipelines_etl.py. No hay que escribir DAG a mano.

| DAG | Configuración | Horario |
|---|---|---|
| hospital_etl_pipeline | config/config.yaml | 0 6 * * * (6:00) |
| ventas_etl_pipeline | pipelines/ventas/config.yaml | 30 6 * * * (6:30) |

El horario y demás parámetros se definen en la sección orquestacion de cada
config.yaml. Los DAG nuevos aparecen pausados: actívelos en la interfaz o con
airflow dags unpause <dag_id>.

Tareas de cada DAG, en orden:
1. aplicar_migraciones: python -m src.migrar (2 reintentos con 5 minutos de espera).
2. ejecutar_pipeline_etl: python -m src.ejecutar_pipeline (sin reintentos automáticos:
   un FALLIDO ya queda auditado y alertado por el pipeline).

Montajes que necesita el scheduler (docker-compose.yaml de Airflow), en solo lectura:

    - /mnt/c/Users/User/Documents/proyecto_python_data_engineering/dags:/opt/airflow/dags/proyecto_python_data_engineering
    - /mnt/c/Users/User/Documents/proyecto_python_data_engineering/config:/opt/airflow/proyecto_etl/config:ro
    - /mnt/c/Users/User/Documents/proyecto_python_data_engineering/pipelines:/opt/airflow/proyecto_etl/pipelines:ro

Las rutas de datos de cada pipeline (rutas en config.yaml) deben estar dentro de
data/ y logs/ del proyecto: el contenedor ETL monta esas dos carpetas y cada
carpeta raw en solo lectura.

Variables de Airflow para las alertas por correo (opcionales):

| Variable | Ejemplo |
|---|---|
| ETL_SMTP_HOST | smtp.gmail.com |
| ETL_SMTP_PUERTO | 587 |
| ETL_SMTP_USUARIO | cuenta@gmail.com |
| ETL_SMTP_PASSWORD | contraseña de aplicación (Airflow la oculta) |
| ETL_ALERTA_DESTINATARIOS | persona1@empresa.com,persona2@empresa.com |

Si una tarea falla por un motivo que el pipeline no puede reportar (imagen
inexistente, contenedor que no arranca, tiempo agotado, migraciones), Airflow
envía un correo "[ETL] FALLO EN AIRFLOW" con el enlace al log.

Variables de entorno opcionales del scheduler:

| Variable | Valor por defecto |
|---|---|
| ETL_CONFIGS_DIR | /opt/airflow/proyecto_etl |
| ETL_PROJECT_PATH | /mnt/c/Users/User/Documents/proyecto_python_data_engineering |
| ETL_IMAGE | hospital-etl:2.1.0 |
| ETL_DOCKER_NETWORK | airflow-docker_default |

Cambiar el horario de un pipeline no requiere reconstruir la imagen. Cualquier
otro cambio de config.yaml, del código o de las migraciones sí la requiere.

Permisos: aplicar una migración nueva requiere permisos de DDL (CREATE/ALTER).
Si la conexión hospital_dw_etl usa un usuario de servicio con permisos limitados,
aplique las migraciones una vez con el usuario propietario de la base:

DB_USER=<propietario> DB_PASSWORD=<clave> python -m src.migrar

Cuando no hay migraciones pendientes, la tarea aplicar_migraciones solo consulta
public.etl_migraciones y funciona con el usuario de servicio.

Variables de entorno opcionales del scheduler (si no se definen se usan los valores del entorno local actual):

| Variable | Valor por defecto |
|---|---|
| ETL_PROJECT_PATH | /mnt/c/Users/User/Documents/proyecto_python_data_engineering |
| ETL_IMAGE | hospital-etl:2.0.0 |
| ETL_DOCKER_NETWORK | airflow-docker_default |
| ETL_AIRFLOW_CONN_ID | hospital_dw_etl |
| ETL_ENVIRONMENT | desarrollo |

7. Ejecutar el pipeline
Desde ~/airflow-docker:
docker compose exec scheduler airflow dags trigger hospital_etl_pipeline

8. Consultar ejecuciones
docker compose exec scheduler airflow dags list-runs \
-d hospital_etl_pipeline

Una ejecución correcta debe finalizar con estado success.


9. Verificación de resultados
La ejecución se valida mediante:
- Estado de la tarea en Airflow.
- Registros procesados en PostgreSQL.
- Registro de auditoría en public.etl_auditoria.
- Archivos generados en las carpetas processed, rejected y logs.

10. Integración continua
El flujo .github/workflows/ci.yml se ejecuta en cada push y pull request:
- Lint con Ruff y pruebas unitarias con cobertura.
- Pruebas de integración contra un servicio PostgreSQL 16 (migraciones, carga, idempotencia y fallos auditados).
- Construcción de la imagen Docker.

11. Consideraciones de seguridad
- No incluir credenciales en el repositorio.
- Mantener protegidos los archivos .env.
- Utilizar conexiones de Airflow para gestionar credenciales.
- No exponer puertos de bases de datos innecesariamente.
- Evitar almacenar datos clínicos reales en entornos de prueba.

12. Adaptación a otros proyectos
Para reutilizar esta plantilla se deben adaptar:
1. La ruta del proyecto.
2. La imagen Docker y su nombre.
3. Las variables de entorno.
4. La conexión de Airflow.
5. El identificador y nombre del DAG.
6. Los volúmenes y carpetas de datos.
7. La base de datos y tabla de destino.

Versión documentada: 2.0.0
