# Configuración y variables de entorno

## 1. Configuración general

El proyecto utiliza `config/config.yaml` para centralizar los parámetros
generales del pipeline.

Entre sus configuraciones se encuentran:

- Nombre y entorno del proyecto.
- Archivos de entrada.
- Rutas de datos originales, procesados y rechazados.
- Nombres de archivos generados.
- Orden de las tareas del pipeline.
- Parámetros de conexión y destino PostgreSQL.
- Configuración de auditoría y logging.

### Secciones principales de `config.yaml`

| Sección | Contenido |
|---|---|
| `proyecto` | Nombre, versión y entorno. |
| `fuentes` | Fuentes de entrada: `nombre` (se guarda en `hospital_origen`) y `archivo` (nombre exacto) o `patron` (comodines, para lotes). |
| `ingesta` | `modo`: `completa` (todos los archivos en cada ejecución) o `incremental` (solo archivos no cargados antes, por hash SHA-256). |
| `esquema` | Contrato de datos: columnas en orden, `tipo` (texto, entero, decimal, fecha, booleano), `obligatoria`, `derivada`, `longitud_max` y `descripcion`. |
| `reglas` | Reglas de negocio: `columna`, `tipo` (`rango`, `valores_permitidos`, `patron`), sus parámetros y el `mensaje` de rechazo. Se suman a las reglas automáticas del esquema. |
| `calidad` | Umbrales: `max_porcentaje_rechazo` (0-100), `min_registros_extraidos` y `accion` (`fallar`: no carga; `advertir`: carga y anota en `etl_auditoria.advertencias`). |
| `rutas` | Carpetas `raw`, `processed`, `rejected` y `logs` (relativas a la raíz o absolutas). |
| `archivos` | Nombres de los archivos generados, incluido `conflictos_clave`. |
| `pipeline.id` | Identificador del pipeline en la auditoría. |
| `pipeline.columna_fuente` | Columna derivada del esquema donde se guarda el nombre de cada fuente. |
| `pipeline.clave_negocio` | Columnas que identifican un registro; deben coincidir con el índice único de la tabla destino. |
| `pipeline.tareas` | Etapas en orden: `nombre`, `modulo` y `funcion`. |
| `pipeline.detener_si_falla` | `true`: se detiene en el primer fallo (FALLIDO). `false`: continúa y termina como PARCIAL. |
| `base_datos` | Esquema, tabla destino, tabla de auditoría, `tabla_archivos` (linaje), `tabla_rechazos` (historial de rechazos) y, opcionalmente, `columnas_actualizables` y `columna_actualizacion` del UPSERT. |
| `migraciones` | `directorio` con las migraciones del proyecto (por defecto `sql/migraciones`). |
| `logging` | Archivo, nivel, rotación y formato (incluye `run_id`). |

Para usar otra configuración sin modificar el archivo del repositorio,
defina `ETL_CONFIG_PATH` con la ruta del YAML alternativo.

## 2. Variables de entorno

Las variables de entorno permiten separar la configuración sensible
del código fuente.

El contenedor ETL utiliza las siguientes variables para conectarse
a PostgreSQL:

| Variable | Función |
|---|---|
| `DB_HOST` | Servidor de PostgreSQL. |
| `DB_PORT` | Puerto de conexión. |
| `DB_NAME` | Nombre de la base de datos. |
| `DB_USER` | Usuario de conexión. |
| `DB_PASSWORD` | Contraseña de conexión. |

No se deben escribir contraseñas directamente en los módulos Python,
el DAG ni los archivos de documentación.

La plantilla `.env.example` documenta todas las variables. Para el
desarrollo local:

```bash
cp .env.example .env   # y reemplazar los valores
```

Las variables definidas en el entorno del proceso (Airflow, Docker, CI)
tienen prioridad sobre el archivo `.env`.

Variables adicionales:

| Variable | Función |
|---|---|
| `ETL_CONFIG_PATH` | Ruta de un `config.yaml` alternativo. |
| `WAREHOUSE_PORT` | Puerto del host para el PostgreSQL de `docker-compose.yml` (5435 por defecto). |
| `ETL_IMAGE_TAG` | Etiqueta de la imagen construida por `docker-compose.yml`. |
| `ETL_PYTHON` | Intérprete que usa `ejecutar_pipeline.bat`. |
| `RUN_INTEGRATION_TESTS` | `1` para ejecutar las pruebas de integración. |

## 3. Conexión de Airflow

Airflow utiliza una conexión identificada como:

`hospital_dw_etl`

Esta conexión proporciona los parámetros de acceso a PostgreSQL
al contenedor mediante variables de entorno.

Las credenciales se administran desde Airflow y no se incluyen
directamente en el código del DAG.

## 4. Identificación de las ejecuciones

El pipeline admite variables para identificar el contexto de ejecución:

| Variable | Función |
|---|---|
| `ETL_ORCHESTRATOR` | Identifica el orquestador. |
| `ETL_PIPELINE_ID` | Identifica el pipeline. |
| `ETL_PIPELINE_VERSION` | Identifica la versión. |
| `ETL_ENVIRONMENT` | Identifica el ambiente de ejecución. |

En la ejecución actual, Airflow proporciona los valores del
orquestador, identificador del DAG, versión y ambiente.

## 5. Archivos de protección

| Archivo | Función |
|---|---|
| `.env` | Variables locales y posibles credenciales. |
| `.gitignore` | Evita incorporar archivos sensibles o innecesarios a Git. |
| `.dockerignore` | Evita incluir archivos innecesarios en la imagen Docker. |

El archivo `.env` no debe publicarse ni compartirse.

## 6. Configuración de Docker

El proyecto utiliza `Dockerfile` para construir la imagen:

`hospital-etl:2.0.0` (la versión se pasa con `--build-arg ETL_VERSION`)

Airflow ejecuta esta imagen mediante `DockerOperator`.

Los directorios de datos procesados, rechazados y logs se montan
como volúmenes para conservar los resultados fuera del contenedor.

El directorio `data/raw` se monta en modo de solo lectura.

## 7. Adaptación a nuevos proyectos

Para reutilizar esta arquitectura:

1. Adaptar el nombre y entorno en `config/config.yaml`.
2. Definir las fuentes de datos y sus archivos.
3. Configurar las rutas de entrada y salida.
4. Crear la base de datos y adaptar las migraciones de `sql/migraciones/`
   (ejecutarlas con `python -m src.migrar`).
5. Configurar las variables de entorno.
6. Crear la conexión correspondiente en Airflow.
7. Adaptar el DAG y su identificador.
8. Construir la imagen Docker del nuevo proyecto.
9. Ejecutar las pruebas antes de ponerlo en funcionamiento.

## 8. Seguridad

Las credenciales deben permanecer fuera del repositorio.

Antes de compartir o publicar el proyecto, verificar que `.env`
y cualquier otro archivo con secretos estén excluidos de Git.

No incluir datos reales de pacientes en ejemplos, pruebas o documentación.

## 9. Estado

Documento elaborado a partir de la configuración del proyecto
hospitalario, versión 2.0.0.
