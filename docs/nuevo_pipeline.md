# Crear un pipeline nuevo

El motor (`src/`) no contiene nada específico de ningún dominio. Un pipeline
nuevo se define con **un archivo de configuración, sus migraciones SQL y sus
datos**. El ejemplo completo está en [`pipelines/ventas/`](../pipelines/ventas/README.md).

## 1. Copiar la plantilla

```powershell
Copy-Item -Recurse pipelines\ventas pipelines\mi_proyecto
Remove-Item pipelines\mi_proyecto\datos_ejemplo\*
```

## 2. Editar `pipelines/mi_proyecto/config.yaml`

| Sección | Qué definir |
|---|---|
| `proyecto` | Nombre, versión y entorno. |
| `fuentes` | Cada fuente con `nombre` y `archivo` (exacto) o `patron` (lotes, p. ej. `"proveedor_a_*.csv"`). |
| `ingesta.modo` | `incremental` (solo archivos nuevos) o `completa`. |
| `esquema.columnas` | Columnas en orden: `nombre` (minúsculas, sin espacios), `tipo` (`texto`, `entero`, `decimal`, `fecha`, `booleano`), `etiqueta`, `obligatoria`, `longitud_max`. Incluya una columna `derivada: true` para el nombre de la fuente. |
| `reglas` | Reglas de negocio: `rango`, `valores_permitidos`, `patron`, cada una con su `mensaje`. |
| `rutas` | Carpetas propias, p. ej. `data/mi_proyecto/raw`. |
| `pipeline.id` | Identificador único (aparece en la auditoría y el linaje). |
| `pipeline.columna_fuente` | La columna derivada del esquema. |
| `pipeline.clave_negocio` | Columnas que identifican un registro (UPSERT). |
| `base_datos.esquema` | Esquema propio de PostgreSQL, p. ej. `mi_proyecto`. |
| `base_datos.tabla_destino` | Tabla final. |
| `migraciones.directorio` | `pipelines/mi_proyecto/migraciones`. |

`pipeline.tareas` normalmente no se modifica.

## 3. Migraciones

- `V001__tablas_de_control_etl.sql`: **no se modifica** (usa `{{esquema}}`).
- Las migraciones genéricas de auditoría, advertencias, rechazos y vistas de operación
  de `pipelines/ventas/migraciones` (`V001`, `V003`, `V004`, `V005`) se copian tal cual.
- `V002__crear_<tabla>.sql`: la tabla de destino, con
  - una columna por cada columna del esquema;
  - `fecha_creacion` y `fecha_actualizacion` (si usa `columna_actualizacion`);
  - un `UNIQUE` sobre las columnas de `clave_negocio`.

Los cambios posteriores van siempre en una migración nueva (`V003__...`),
nunca editando una ya aplicada.

## 4. Ejecutar

```powershell
$env:ETL_CONFIG_PATH = "pipelines\mi_proyecto\config.yaml"
python -m src.migrar              # con un usuario con permisos de DDL
python -m src.ejecutar_pipeline
```

Si algo no coincide (columna inexistente, regla mal escrita, tabla sin una
columna del esquema), el pipeline falla al iniciar con un mensaje que indica
qué corregir.

## 5. Permisos del usuario de servicio

Con el usuario administrador, otorgue al usuario del pipeline solo lo necesario:

```sql
GRANT USAGE ON SCHEMA mi_proyecto TO etl_service;
GRANT SELECT, INSERT, UPDATE ON mi_proyecto.<tabla_destino> TO etl_service;
GRANT SELECT, INSERT, UPDATE ON mi_proyecto.etl_auditoria TO etl_service;
GRANT SELECT, INSERT ON mi_proyecto.etl_archivos_procesados TO etl_service;
GRANT SELECT ON mi_proyecto.etl_migraciones TO etl_service;
GRANT SELECT, INSERT ON mi_proyecto.etl_rechazos TO etl_service;
GRANT SELECT ON mi_proyecto.vw_etl_salud, mi_proyecto.vw_etl_ejecuciones,
  mi_proyecto.vw_etl_calidad_diaria, mi_proyecto.vw_etl_rechazos_resumen,
  mi_proyecto.vw_etl_linaje TO etl_service;
```

## 6. Programarlo en Airflow

Agregue la sección `orquestacion` a su `config.yaml`:

```yaml
orquestacion:
  activo: true
  horario: "0 7 * * *"          # cron, o null para ejecución manual
  zona_horaria: "America/Bogota"
  conexion_airflow: "hospital_dw_etl"
  etiquetas: ["mi_proyecto"]
```

Reconstruya la imagen ETL. La fábrica de DAG creará `<pipeline.id>` en Airflow
automáticamente (aparece pausado la primera vez). Las rutas de datos deben estar
dentro de `data/` y `logs/`, y la carpeta `raw` debe existir en el equipo.

## 7. Pruebas

`tests/test_pipelines_ejemplo.py` valida automáticamente la configuración de
cada carpeta de `pipelines/`. Para una prueba de extremo a extremo, use como
modelo `tests/integracion/test_pipeline_ventas.py`.
