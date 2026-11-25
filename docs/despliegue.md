# Procedimiento de despliegue

## 1. Arquitectura de despliegue

El proyecto utiliza Docker para ejecutar el proceso ETL y Apache Airflow para orquestarlo.

El entorno Docker se encuentra en `~/airflow-docker`, separado del directorio del proyecto ETL.

## 2. Servicios Docker

| Servicio | Función | Puerto |
|---|---|---:|
| postgres | Base de datos de metadatos de Airflow | 5433 |
| scheduler | Programa y ejecuta los DAG | Interno |
| webserver | Interfaz web de Airflow | 8080 |
| warehouse | Base de datos PostgreSQL del proyecto | 5434 |

## 3. Iniciar el entorno

Desde Ubuntu/WSL:

```bash
cd ~/airflow-docker
docker compose up -d

Comprobar el estado:
docker compose ps


4. Construir la imagen ETL
Desde Ubuntu/WSL:
docker build -t hospital-etl:1.0 \
/mnt/c/Users/User/Documents/proyecto_python_data_engineering

La imagen contiene el código Python y la configuración necesaria para ejecutar el pipeline.

5. Acceder a Airflow
Abrir en el navegador:

http://localhost:8080

El DAG principal es:

hospital_etl_pipeline

6. Ejecutar el pipeline
Desde ~/airflow-docker:
docker compose exec scheduler airflow dags trigger hospital_etl_pipeline

7. Consultar ejecuciones
docker compose exec scheduler airflow dags list-runs \
-d hospital_etl_pipeline

Una ejecución correcta debe finalizar con estado success.


8. Verificación de resultados
La ejecución se valida mediante:
- Estado de la tarea en Airflow.
- Registros procesados en PostgreSQL.
- Registro de auditoría en public.etl_auditoria.
- Archivos generados en las carpetas processed, rejected y logs.

9. Consideraciones de seguridad
- No incluir credenciales en el repositorio.
- Mantener protegidos los archivos .env.
- Utilizar conexiones de Airflow para gestionar credenciales.
- No exponer puertos de bases de datos innecesariamente.
- Evitar almacenar datos clínicos reales en entornos de prueba.

10. Adaptación a otros proyectos
Para reutilizar esta plantilla se deben adaptar:
1. La ruta del proyecto.
2. La imagen Docker y su nombre.
3. Las variables de entorno.
4. La conexión de Airflow.
5. El identificador y nombre del DAG.
6. Los volúmenes y carpetas de datos.
7. La base de datos y tabla de destino.

Versión documentada: 1.0.0
