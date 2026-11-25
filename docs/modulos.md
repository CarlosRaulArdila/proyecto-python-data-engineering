# Inventario de módulos Python

Ubicación: `src/`

## 1. Módulos de configuración e infraestructura

| Módulo | Responsabilidad |
|---|---|
| `configuracion.py` | Cargar y gestionar la configuración del proyecto. |
| `conexion_db.py` | Gestionar la conexión con PostgreSQL. |
| `crear_tabla.py` | Crear las tablas necesarias en la base de datos. |

## 2. Módulos de procesamiento ETL

| Módulo | Responsabilidad |
|---|---|
| `consolidar_datos.py` | Integrar los archivos procedentes de las fuentes de datos. |
| `limpiar_datos.py` | Limpiar los registros y gestionar datos incompletos o duplicados. |
| `validar_reglas.py` | Aplicar reglas de validación y calidad de datos. |
| `inspeccionar_datos.py` | Inspeccionar los datos durante el procesamiento. |

## 3. Módulos de carga

| Módulo | Responsabilidad |
|---|---|
| `cargar_postgresql.py` | Gestionar la carga de datos en PostgreSQL. |
| `cargar_incremental.py` | Insertar o actualizar registros evitando duplicados. |

## 4. Orquestación y auditoría

| Módulo | Responsabilidad |
|---|---|
| `ejecutar_pipeline.py` | Coordinar las etapas del pipeline ETL y gestionar su ejecución. |
| `auditoria.py` | Registrar los metadatos, resultados y estado de cada ejecución. |

## 5. Generación de datos

| Módulo | Responsabilidad |
|---|---|
| `generar_datos.py` | Generar datos para las fuentes de entrada. |
| `generar_datos_prueba.py` | Generar datos destinados a pruebas y validaciones. |

## 6. Consideraciones

Este inventario describe las responsabilidades previstas a partir de la estructura y los nombres de los módulos.

Las responsabilidades específicas y las dependencias entre módulos deberán contrastarse con el código fuente antes de utilizar esta documentación como especificación técnica definitiva.

## 7. Total de módulos

13 módulos Python identificados.
