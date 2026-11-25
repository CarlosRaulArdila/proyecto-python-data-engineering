# Operación y mantenimiento del pipeline

## 1. Objetivo

Este documento describe cómo ejecutar, supervisar y verificar el pipeline de Ingeniería de Datos.

## 2. Identificación del pipeline

- Proyecto: proyecto_python_data_engineering
- DAG: hospital_etl_pipeline
- Tarea: ejecutar_pipeline_etl
- Orquestador: Apache Airflow
- Ejecutor: DockerOperator
- Imagen: hospital-etl:1.0
- Base de datos: hospital_dw
- Tabla de auditoría: public.etl_auditoria

## 3. Ejecutar el pipeline

Desde WSL:

```bash
cd ~/airflow-docker
docker compose exec scheduler airflow dags trigger hospital_etl_pipeline

La ejecución también puede iniciarse desde la interfaz web de Airflow.

## 4. Supervisar ejecuciones
Consultar las ejecuciones:
docker compose exec scheduler airflow dags list-runs -d hospital_etl_pipeline
Consultar las tareas del DAG:
docker compose exec scheduler airflow tasks list hospital_etl_pipeline
El estado success indica que la ejecución terminó correctamente.

## 5. Consultar la auditoría
La tabla public.etl_auditoria almacena una fila por ejecución.

Consulta de las últimas ejecuciones:
SELECT
    id,
    fecha_inicio,
    fecha_fin,
    estado,
    registros_extraidos,
    registros_limpios,
    registros_rechazados,
    operaciones_bd,
    duracion_segundos,
    run_id,
    proyecto_id,
    pipeline_id,
    orquestador,
    version_pipeline,
    ambiente,
    archivo_log,
    mensaje_error
FROM public.etl_auditoria
ORDER BY fecha_inicio DESC
LIMIT 20;

## 6. Interpretación de métricas
Campo	Significado
registros_extraidos	Registros obtenidos de las fuentes
registros_limpios	Registros que superaron la limpieza
registros_rechazados	Registros descartados durante el procesamiento o validación
operaciones_bd	Operaciones de inserción o actualización
duracion_segundos	Tiempo total de ejecución
estado	Resultado final del pipeline

Una ejecución puede finalizar correctamente con cero operaciones en la base de datos si no existen cambios que deban insertarse o actualizarse.


## 7. Revisar archivos de salida
Comprobar las carpetas del proyecto:
- data/raw: archivos originales.
- data/processed: datos procesados.
- data/rejected: registros rechazados.
- logs: archivos de registro de ejecución.

## 8. Diagnóstico básico
El DAG no aparece en Airflow
Comprobar que el archivo del DAG esté en la carpeta configurada para Airflow y revisar los errores de importación.
La tarea falla al conectarse a PostgreSQL
Verificar:
- Estado del servicio warehouse.
- Conexión de Airflow hospital_dw_etl.
- Host, puerto, base de datos y usuario.
- Permisos del usuario de servicio.
La tarea falla al ejecutar Docker
Comprobar:
- Existencia de la imagen hospital-etl:1.0.
- Acceso al socket Docker.
- Red Docker compartida.
- Rutas de los volúmenes montados.
Existen registros rechazados
Revisar los archivos de data/rejected y los criterios de limpieza y validación.

##9. Buenas prácticas
- Revisar el estado final en Airflow.
- Verificar las métricas de auditoría.
- Investigar los errores antes de repetir una ejecución.
- Mantener copias de seguridad de los datos importantes.
- No modificar ni eliminar registros de auditoría sin un procedimiento controlado.
- No utilizar datos clínicos reales en pruebas.
- Proteger credenciales y archivos de configuración sensibles.

## 10. Reutilización
Para operar el pipeline en otro proyecto se deben actualizar el identificador del DAG, las conexiones, la configuración, las rutas, la imagen Docker y la tabla de destino.

Versión documentada: 1.0.0
