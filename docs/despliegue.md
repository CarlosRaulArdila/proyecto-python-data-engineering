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
docker build --build-arg ETL_VERSION=1.1.0 -t hospital-etl:1.1.0 \
/mnt/c/Users/User/Documents/proyecto_python_data_engineering

Importante: el DAG usa por defecto la imagen hospital-etl:1.1.0.
La imagen debe reconstruirse después de actualizar el código.

La imagen contiene el código Python y la configuración necesaria para ejecutar el pipeline.

6. Acceder a Airflow
Abrir en el navegador:

http://localhost:8080

El DAG principal es:

hospital_etl_pipeline

Tareas del DAG, en orden:
1. aplicar_migraciones: ejecuta python -m src.migrar (idempotente).
2. ejecutar_pipeline_etl: ejecuta python -m src.ejecutar_pipeline.

Ambas tienen 2 reintentos con 5 minutos de espera.

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
| ETL_IMAGE | hospital-etl:1.1.0 |
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

Versión documentada: 1.1.0
