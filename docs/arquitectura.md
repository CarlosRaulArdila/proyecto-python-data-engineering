# Arquitectura del proyecto de Ingeniería de Datos Hospitalarios

## 1. Objetivo

Construir un pipeline ETL modular, automatizado y reutilizable para integrar, limpiar, validar y cargar datos procedentes de diferentes fuentes hospitalarias.

## 2. Arquitectura general

```mermaid
flowchart TD
    A[Archivos CSV de hospitales] --> B[Data Raw]
    B --> C[Consolidación con Python]
    C --> D[Limpieza de datos]
    D --> E[Validación de reglas]
    E --> F[Datos procesados y rechazados]
    F --> G[Carga incremental]
    G --> H[(PostgreSQL - hospital_dw)]
    I[Apache Airflow] --> J[DockerOperator]
    J --> K[Contenedor hospital-etl:1.0]
    K --> C
    K --> L[Auditoría ETL]
    L --> H

3. Componentes tecnológicos
ComponenteTecnologíaResponsabilidad
LenguajePython 3.12Procesamiento ETL
TransformaciónPandasConsolidación y limpieza
Base de datosPostgreSQL 16Almacenamiento
ConectividadSQLAlchemy y psycopg2Acceso a PostgreSQL
ContenedoresDockerEjecución aislada
OrquestaciónApache Airflow 2.10.3Programación y seguimiento
OperadorDockerOperatorEjecución del ETL desde Airflow
PruebasPytestValidación del código

4. Estructura del pipeline
1. Extracción: lectura de los archivos CSV ubicados en data/raw.
2. Consolidación: integración de los archivos de origen.
3. Limpieza: tratamiento de registros incompletos y duplicados.
4. Validación: aplicación de reglas de calidad de datos.
5. Rechazos: separación de registros que no cumplen los criterios.
6. Carga incremental: inserción o actualización de registros en PostgreSQL.
7. Auditoría: almacenamiento de los metadatos y resultados de cada ejecución.

5. Orquestación
Airflow administra el DAG hospital_etl_pipeline.

El DAG utiliza DockerOperator para ejecutar la imagen hospital-etl:1.0.

La conexión de Airflow con PostgreSQL se administra mediante la conexión hospital_dw_etl, sin almacenar las credenciales directamente en el código.

6. Auditoría
La tabla public.etl_auditoria registra:
- Identificador de ejecución (run_id).
- Proyecto y pipeline.
- Orquestador, versión y ambiente.
- Estado de ejecución.
- Registros extraídos, limpios y rechazados.
- Operaciones realizadas en la base de datos.
- Duración y fechas de ejecución.

7. Validación funcional
Una ejecución validada del pipeline presentó los siguientes resultados:
IndicadorResultado
Registros extraídos15
Registros limpios12
Registros rechazados3
Operaciones en PostgreSQL0
Duración2,92 segundos
EstadoEXITOSO

Las cero operaciones de base de datos corresponden a una nueva ejecución sin cambios que requirieran inserciones o actualizaciones.

8. Principios de diseño
- Modularidad: cada responsabilidad se implementa por separado.
- Reutilización: configuración y código separados.
- Idempotencia: evitar duplicados al reprocesar datos.
- Trazabilidad: registrar cada ejecución.
- Aislamiento: ejecución mediante contenedores Docker.
- Calidad: pruebas automatizadas con Pytest.
- Seguridad: credenciales fuera del código fuente.

9. Estado
Arquitectura funcional validada en entorno local de desarrollo.

Versión documentada: 1.0.0.
