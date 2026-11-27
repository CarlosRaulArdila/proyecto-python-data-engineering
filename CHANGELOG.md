# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y versionado semántico.

## [Sin publicar] - Fase 3: operación autónoma

### Eliminado
- `dags/hospital_etl_dag.py`: reemplazado por la fábrica (mismo `dag_id`, conserva el historial).

### Añadido
- **Umbrales de calidad** (sección `calidad` y módulo `src/calidad.py`):
  `max_porcentaje_rechazo`, `min_registros_extraidos` y `accion` (`fallar` o `advertir`).
  - Nueva etapa `evaluar_calidad` entre la validación y la carga: con `fallar`, la
    ejecución se detiene **antes de escribir en la base** y los archivos se reintentan.
  - Con `advertir`, se carga y el incumplimiento queda en la nueva columna
    `etl_auditoria.advertencias` (migraciones `V005` y `ventas/V003`).
  - Si no hubo archivos nuevos (ingesta incremental) no se evalúan los umbrales.
- **Historial de rechazos en la base** (`src/rechazos.py`, migraciones `V006` y `ventas/V004`):
  tabla `etl_rechazos` con `run_id`, `tipo` (`incompleto`, `duplicado`, `conflicto_clave`,
  `regla_negocio`), `motivo`, `fuente` y el registro original en JSONB. Ya no se pierde el
  historial al sobrescribir los CSV.
  - Nueva etapa `registrar_rechazos`, después de validar y antes de los umbrales: los rechazos
    quedan guardados aunque un umbral detenga la carga.
  - Los CSV de incompletos y duplicados incluyen `motivo_rechazo`
    (por ejemplo, `Campos obligatorios vacíos: edad`).
- **Alertas** (`src/alertas.py`, sección `alertas`): por correo (SMTP con STARTTLS o SSL)
  y por webhook (formatos `slack`, `teams` y `generico`), solo con la librería estándar.
  - `notificar_en`: `FALLIDO`, `PARCIAL`, `ADVERTENCIA` (EXITOSO con advertencias), `EXITOSO`.
  - Secretos solo en variables de entorno o `.env` (`ETL_SMTP_*`, `ETL_ALERTA_DESTINATARIOS`,
    la URL del webhook); nunca en el YAML.
  - Una alerta que no se puede enviar nunca hace fallar el pipeline.
  - `python -m src.alertas --prueba` envía una alerta de ejemplo.
- **Fábrica de DAG** (`dags/fabrica_pipelines_etl.py` y `dags/etl_fabrica_config.py`):
  un DAG por cada `config/config.yaml` y `pipelines/*/config.yaml`, sin escribir código.
  - Sección `orquestacion` por pipeline: `horario` (cron o null), `zona_horaria`,
    `reintentos_migraciones`, `tiempo_maximo_minutos`, `conexion_airflow`, `etiquetas`, `activo`.
  - Hospital programado a las 6:00 y ventas a las 6:30 (America/Bogota).
  - Las variables de correo llegan al contenedor desde Variables de Airflow
    (`ETL_SMTP_*`, `ETL_ALERTA_DESTINATARIOS`); si no existen, no se envía correo.
  - Alerta de Airflow cuando una tarea falla por algo que el pipeline no pudo reportar
    (imagen inexistente, contenedor que no arranca, tiempo agotado, migraciones). Los
    FALLIDO del pipeline no se duplican: ya los avisa el propio pipeline.
  - La tarea del pipeline no se reintenta automáticamente (las migraciones, sí).
  - Validado contra Airflow 2.10.3 y apache-airflow-providers-docker 3.14.0.
- **Tablero de operación**:
  - Vistas SQL en cada esquema (migraciones `V007` y `ventas/V005`, idénticas): `vw_etl_salud`
    (OK, ADVERTENCIA, FALLANDO, o ATRASADO tras más de 26 h sin éxito), `vw_etl_ejecuciones`,
    `vw_etl_calidad_diaria`, `vw_etl_rechazos_resumen` y `vw_etl_linaje`. Son la capa estable
    para Power BI u otras herramientas.
  - `python -m src.tablero`: página HTML autocontenida (sin recursos externos) con la salud,
    los indicadores, las tendencias, las últimas ejecuciones, los motivos de rechazo y el
    linaje de todos los pipelines. Modo claro y oscuro, tooltip por barra, estados con
    ícono y texto.
- Marcador `{{zona_horaria}}` en las migraciones (`orquestacion.zona_horaria`, por defecto UTC).
- Dockerfile: la versión se declara después de instalar las dependencias (cambiarla ya no
  vuelve a descargar nada), caché de descargas de pip con BuildKit y tolerancia a redes
  lentas (`PIP_DEFAULT_TIMEOUT=120`, `PIP_RETRIES=10`).
- Prueba que importa cada módulo de `src/` en un proceso limpio (detecta importaciones
  circulares).
- Las etapas reciben en el contexto las métricas acumuladas (`metricas`), el detalle
  de todo lo que devolvieron (`detalle`) y la lista de `advertencias`.
- La consolidación informa `archivos_procesados`.

## [2.0.0] - 2026-11-25 - Fase 2: plantilla reutilizable

### Añadido
- **Esquema (contrato de datos) en `config.yaml`**: columnas, tipo (`texto`, `entero`,
  `decimal`, `fecha`, `booleano`), obligatoriedad, longitud máxima y columnas derivadas.
  Módulo `src/esquema.py`.
  - Cada fuente debe tener las columnas del esquema; si falta alguna, el pipeline falla
    indicando el archivo y la columna.
  - Las columnas de la fuente que no están en el esquema se descartan con un aviso.
  - Solo las columnas obligatorias determinan si un registro está incompleto.
  - La conversión de tipos antes de la carga se hace según el esquema.
- **Reglas de negocio en `config.yaml`** (sección `reglas`) con el motor `src/reglas.py`:
  - Tipos: `rango` (con límites inclusivos o exclusivos), `valores_permitidos` y `patron`.
  - Reglas automáticas desde el esquema: obligatoria, tipo (fecha, entero, decimal)
    y `longitud_max`.
  - La configuración se valida al iniciar (columna inexistente, tipo desconocido,
    parámetros faltantes, regex inválida, rango sobre columna no numérica).
  - Propiedad `etiqueta` en el esquema para los mensajes de rechazo.
- **UPSERT generado desde la configuración** (`cargar_incremental.py`):
  columnas del esquema, `ON CONFLICT` sobre `pipeline.clave_negocio`, actualización
  de las demás columnas solo si cambian (o de `base_datos.columnas_actualizables`)
  y `base_datos.columna_actualizacion` opcional. Sin columnas actualizables usa `DO NOTHING`.
- Verificación previa de la tabla destino: si no existe o le faltan columnas del
  esquema, el pipeline falla con un mensaje que indica cuáles.
- **Ingesta incremental y linaje** (`src/ingesta.py`, migración `V004`):
  - Las fuentes admiten `patron` (comodines, para lotes) además de `archivo`.
  - `ingesta.modo`: `completa` (todos los archivos) o `incremental` (solo los no
    cargados antes, identificados por hash SHA-256 aunque cambien de nombre).
  - Tabla `etl_archivos_procesados`: archivo, fuente, hash, tamaño, registros y
    `run_id` de cada ejecución exitosa.
  - Nueva etapa final `registrar_ingesta`: registra los archivos solo si todas las
    etapas anteriores terminaron bien; si la carga falla se reintentan.
  - Las etapas pueden recibir el contexto de la ejecución (`run_id`, `pipeline_id`,
    errores previos) declarando un parámetro.
- **Multi-proyecto: pipeline de ejemplo de ventas** (`pipelines/ventas/`), creado solo con
  configuración, migraciones y datos, sin código Python nuevo. Guía en `docs/nuevo_pipeline.md`.
  - `pipeline.columna_fuente`: nombre de la columna derivada con la fuente (antes
    `hospital_origen` fijo en el código).
  - `migraciones.directorio`: cada proyecto tiene sus migraciones, y su historial en
    `<base_datos.esquema>.etl_migraciones`. `src.migrar` crea el esquema si no existe.
  - Marcador `{{esquema}}` en los archivos SQL de migración.
  - La imagen Docker incluye `pipelines/`; se elige el pipeline con `ETL_CONFIG_PATH`.
- `src/sql_utils.py`: validación estricta de nombres de tablas y columnas antes de
  usarlos en SQL (los nombres del esquema deben ser identificadores en minúsculas).

### Cambiado
- Los textos compuestos solo por espacios cuentan como vacíos en la limpieza.
- Ya no hay nombres ni tipos de columnas escritos en el código del motor
  (`dtype={"numero_historia": str}`, `COLUMNAS_ENTERAS`).
- La validación es vectorizada: 200 000 registros en ~0,4 s (antes ~47 s con `iterrows`).
- Las listas de especialidades y técnicas anestésicas pasan de `validar_reglas.py` a `config.yaml`.
- La auditoría usa `base_datos.tabla_auditoria` en lugar de `public.etl_auditoria` fijo.
- `pipeline.clave_negocio` es obligatoria y se valida al cargar la configuración.
- Sin esquema, la lectura de CSV trata todo como texto (antes solo `numero_historia`).

### Notas de actualización desde 1.1.0
Versión mayor: el formato de `config.yaml` cambia.
1. Secciones nuevas obligatorias: `esquema` y `pipeline.columna_fuente`
   (`pipeline.clave_negocio` pasa a ser obligatoria). Opcionales: `reglas`,
   `ingesta`, `migraciones`, `base_datos.tabla_archivos`, `base_datos.columna_actualizacion`.
2. Agregar la etapa `registrar_ingesta` al final de `pipeline.tareas`.
3. Aplicar la migración `V004` con un usuario con permisos de DDL y otorgar
   `SELECT, INSERT` sobre `etl_archivos_procesados` al usuario de servicio.
4. Reconstruir la imagen: `docker build --build-arg ETL_VERSION=2.0.0 -t hospital-etl:2.0.0 .`

## [1.1.0] - 2026-11-25 - Fase 1: estabilización

### Añadido
- Migraciones SQL versionadas en `sql/migraciones/` y aplicador `python -m src.migrar`
  (idempotente, con bloqueo consultivo y verificación de checksum en `public.etl_migraciones`).
  - `V001`: tabla `hospital_registros` e **índice único de la clave de negocio**
    que exige el `ON CONFLICT` de la carga incremental (solo se crea si no existe uno equivalente).
  - `V002`: tabla `etl_auditoria` con índices (antes no estaba en el repositorio).
  - `V003`: columnas `fecha_creacion` y `fecha_actualizacion` en la tabla destino.
- `docker-compose.yml` con warehouse PostgreSQL, migraciones y motor ETL.
- `.env.example` con todas las variables documentadas.
- `src/registro_logs.py`: logs a consola y archivo con el `run_id` en cada línea.
- Detección de **conflictos de clave de negocio** (`registros_conflicto_clave.csv`).
- Aviso de CSV presentes en `data/raw` que no están declarados en `config.yaml`.
- Validaciones: edad y duración deben ser números enteros.
- Estado de auditoría `PARCIAL` cuando `detener_si_falla: false`.
- DAG: tarea `aplicar_migraciones` antes del pipeline y 2 reintentos por tarea.
- CI en GitHub Actions: Ruff, pruebas unitarias con cobertura, pruebas de integración
  contra PostgreSQL 16 y construcción de la imagen Docker.
- `requirements-dev.txt`, `ruff.toml`, `CHANGELOG.md`.
- 35 pruebas nuevas (54 unitarias y 3 de integración en total).
- Checksum de migraciones independiente de los finales de línea (CRLF/LF).

### Cambiado
- `ejecutar_pipeline.py` ejecuta las etapas **en el mismo proceso** y cada etapa
  **devuelve sus métricas**; se eliminaron los subprocesos, la lectura de la salida
  con expresiones regulares y las comparaciones con nombres de archivo.
- `pipeline.tareas` en `config.yaml` declara `nombre`, `modulo` y `funcion`.
- La auditoría de inicio está dentro del manejo de errores: si no puede registrarse,
  el pipeline no se ejecuta y termina con código 1.
- `conexion_db.py` crea el engine de forma perezosa (`obtener_engine`): importar
  el código ya no exige credenciales y los tests unitarios funcionan sin `.env`.
- La carga incremental normaliza los enteros (`33.0` → `33`), acepta un DataFrame
  vacío y valida el nombre de la tabla contra una lista blanca y un patrón.
- `configuracion.py` valida las secciones obligatorias y admite `ETL_CONFIG_PATH`
  y rutas absolutas.
- Sin rutas absolutas en `generar_datos.py`, `ejecutar_pipeline.bat` y el DAG
  (este último usa variables de entorno con los valores actuales por defecto).
- Versión única 1.1.0 en `config.yaml`, imagen Docker (`ETL_VERSION`) y DAG.
- La imagen Docker incluye `sql/` y excluye tests, docs y DAGs.

### Eliminado
- `src/cargar_postgresql.py` (carga completa con `TRUNCATE`, sustituida por la carga incremental).

### Obsoleto
- `src/crear_tabla.py`: delega en `python -m src.migrar`.

### Notas de actualización desde 1.0.0
1. Ejecutar `python -m src.migrar` sobre la base existente (no borra datos).
2. Reconstruir la imagen: `docker build --build-arg ETL_VERSION=1.1.0 -t hospital-etl:1.1.0 .`
3. Ejecutar los módulos con `python -m src.<modulo>` desde la raíz del proyecto.

## [1.0.0]
- Pipeline ETL modular, carga incremental, Docker, Airflow, auditoría y 22 pruebas.
