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
| [Nuevo pipeline](nuevo_pipeline.md) | Cómo crear un pipeline de otro dominio solo con configuración |
| [Cambios](../CHANGELOG.md) | Historial de versiones |

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

- **1.1.0 (Fase 1 - estabilización):** migraciones SQL versionadas, entorno
  `docker-compose` reproducible, orquestación sin subprocesos, detección de
  conflictos de clave, integración continua y pruebas contra PostgreSQL.
- **2.0.0 (Fase 2 - plantilla reutilizable):** esquema, reglas, clave de negocio
  y UPSERT declarados en `config.yaml`; ingesta incremental con linaje; un
  esquema de PostgreSQL por proyecto y un segundo pipeline de ejemplo (ventas)
  creado solo con configuración. Ver [Nuevo pipeline](nuevo_pipeline.md).

---

Documentación: versión 2.0.0
