# Documentación del proyecto

## Proyecto Python Data Engineering

Plantilla modular y reutilizable para construir pipelines de Ingeniería de Datos mediante Python, PostgreSQL, Docker y Apache Airflow.

## Índice

| Documento | Descripción |
|---|---|
| [Arquitectura](arquitectura.md) | Arquitectura general, componentes y flujo ETL |
| [Módulos](modulos.md) | Inventario de módulos Python |
| [Configuración](configuracion.md) | Configuración YAML, variables de entorno y conexiones |
| [Despliegue](despliegue.md) | Construcción de imagen Docker y despliegue con Airflow |
| [Operación](operacion.md) | Ejecución, supervisión, auditoría y mantenimiento |

## Orden recomendado de lectura

1. Arquitectura.
2. Módulos.
3. Configuración.
4. Despliegue.
5. Operación.

## Tecnologías principales

- Python 3.12
- Pandas
- SQLAlchemy
- PostgreSQL 16
- Docker
- Apache Airflow 2.10.3
- Pytest

## Estado del proyecto

La versión 1.0.0 cuenta con un pipeline ETL modular, carga incremental, orquestación con Airflow y registro de auditoría en PostgreSQL.

La ejecución integrada ha sido validada satisfactoriamente.

---

Documentación: versión 1.0.0
