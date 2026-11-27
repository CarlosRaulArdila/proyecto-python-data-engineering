# Inventario de módulos Python

Ubicación: `src/` (paquete Python). Todos los módulos se ejecutan desde la raíz
del proyecto con `python -m src.<modulo>`.

## 1. Configuración e infraestructura

| Módulo | Responsabilidad |
|---|---|
| `configuracion.py` | Carga y valida `config/config.yaml` (o el archivo indicado en `ETL_CONFIG_PATH`). Resuelve rutas relativas desde la raíz del proyecto. |
| `conexion_db.py` | Crea de forma perezosa un único engine de SQLAlchemy por proceso (`obtener_engine`) y lo libera (`cerrar_engine`). Importarlo no exige credenciales. |
| `esquema.py` | Esquema (contrato de datos) declarado en `config.yaml`: tipos, obligatoriedad, columnas derivadas, verificación de fuentes y conversión de tipos. |
| `reglas.py` | Motor de reglas vectorizado: reglas automáticas del esquema y reglas de negocio de `config.yaml` (`rango`, `valores_permitidos`, `patron`). Extensible registrando nuevos tipos en `TIPOS_REGLA`. |
| `sql_utils.py` | Validación de identificadores SQL (tablas y columnas) generados desde la configuración. |
| `ingesta.py` | Descubrimiento de archivos por `archivo` o `patron`, hash SHA-256, modo incremental, manifiesto de la ejecución y etapa final `registrar_ingesta` (linaje en `etl_archivos_procesados`). |
| `calidad.py` | Umbrales de calidad (`calidad` en `config.yaml`): porcentaje máximo de rechazo y mínimo de registros, con acción `fallar` o `advertir`. |
| `rechazos.py` | Etapa `registrar_rechazos`: guarda en `etl_rechazos` cada registro rechazado de la ejecución, con tipo, motivo, fuente y el registro en JSON. |
| `alertas.py` | Alertas al terminar cada ejecución, por correo (SMTP) o webhook (Slack, Teams, genérico). Prueba: `python -m src.alertas --prueba`. |
| `tablero.py` | Genera el tablero HTML de operación de todos los pipelines a partir de las vistas `vw_etl_*`: `python -m src.tablero`. |
| `registro_logs.py` | Configura los logs a consola y a archivo rotativo, con el `run_id` en cada línea. |
| `migrar.py` | Aplica las migraciones del directorio configurado (`migraciones.directorio`), reemplaza `{{esquema}}`, crea el esquema si no existe y registra el historial en `<esquema>.etl_migraciones`. |
| `crear_tabla.py` | **Obsoleto.** Se conserva por compatibilidad y delega en `migrar.py`. |

## 2. Etapas del pipeline

Cada etapa expone una función sin argumentos que **devuelve un diccionario de
métricas**. El orquestador las declara en `config.yaml` (`pipeline.tareas`).

| Módulo | Función | Responsabilidad | Métricas devueltas |
|---|---|---|---|
| `consolidar_datos.py` | `ejecutar_consolidacion` | Une los CSV de las fuentes configuradas y avisa de CSV presentes en `raw/` que no están configurados. | `registros_extraidos` |
| `limpiar_datos.py` | `ejecutar_limpieza` | Separa incompletos, duplicados exactos y conflictos de clave de negocio. | `registros_limpios`, `registros_rechazados` |
| `validar_reglas.py` | `ejecutar_validacion` | Aplica las reglas del esquema y de `config.yaml` (vía `reglas.py`) e indica todos los motivos de cada rechazo. | `registros_validos`, `registros_rechazados` |
| `rechazos.py` | `registrar_rechazos` | Guarda los rechazos de la ejecución en la base, antes de los umbrales. | — |
| `calidad.py` | `evaluar_calidad` | Aplica los umbrales de calidad antes de cargar; con `fallar` detiene la ejecución. | — |
| `cargar_incremental.py` | `ejecutar_carga_incremental` | Verifica la tabla destino y ejecuta un UPSERT idempotente **generado desde el esquema y la clave de negocio**. | `operaciones_bd` |
| `ingesta.py` | `registrar_ingesta` | Última etapa: registra los archivos procesados solo si todo terminó bien. | — |

## 3. Orquestación y auditoría

| Módulo | Responsabilidad |
|---|---|
| `ejecutar_pipeline.py` | Ejecuta las etapas en orden dentro del mismo proceso, acumula sus métricas, aplica `detener_si_falla` y devuelve el código de salida (0 = EXITOSO). |
| `auditoria.py` | Registra el inicio (`EN_PROCESO`) y el cierre (`EXITOSO`, `FALLIDO` o `PARCIAL`) de cada ejecución en `public.etl_auditoria`. |

## 4. Utilidades de desarrollo

| Módulo | Responsabilidad |
|---|---|
| `generar_datos.py` | Genera los CSV sintéticos de las tres fuentes en la carpeta `raw` configurada. |
| `generar_datos_prueba.py` | Genera `datos_prueba.csv` con registros válidos e inválidos. |
| `inspeccionar_datos.py` | Perfilado rápido de los CSV de `raw/`. |

## 5. Retirados

| Módulo | Motivo |
|---|---|
| `cargar_postgresql.py` | Carga completa con `TRUNCATE`, sustituida por `cargar_incremental.py`. Se eliminó para evitar ejecuciones accidentales que borren la tabla de destino. |

## 6. Añadir una etapa nueva

1. Crear una función en un módulo de `src/` que devuelva un diccionario
   (puede usar las claves `registros_extraidos`, `registros_limpios`,
   `registros_rechazados` y `operaciones_bd` para que se auditen).
2. Declararla en `config.yaml`:

   ```yaml
   pipeline:
     tareas:
       - nombre: "mi_etapa"
         modulo: "src.mi_modulo"
         funcion: "ejecutar_mi_etapa"
   ```

3. Añadir sus pruebas en `tests/`.

---

Documentación: versión 2.1.0
