# Pipeline de ejemplo: ventas minoristas

Demuestra que el motor ETL de este repositorio se reutiliza en otro sector
**solo con configuración**: no hay ningún archivo Python específico de ventas.

| Elemento | Valor |
|---|---|
| Fuentes | `Tienda Norte` (`tienda_norte_*.csv`) y `Tienda Sur` (`tienda_sur_*.csv`), un archivo por día |
| Ingesta | `incremental`: solo procesa archivos nuevos (por hash SHA-256) |
| Clave de negocio | `pedido_id` + `tienda_origen` |
| Destino | `ventas.pedidos` (esquema propio de PostgreSQL) |
| Auditoría y linaje | `ventas.etl_auditoria`, `ventas.etl_archivos_procesados` |
| Reglas | formato `PED-000000`, cantidad 1–1000, precio > 0, categorías y canales permitidos |

## Archivos

```
pipelines/ventas/
├── config.yaml                 # todo el comportamiento del pipeline
├── migraciones/
│   ├── V001__tablas_de_control_etl.sql   # genérica ({{esquema}}): copiar tal cual
│   └── V002__crear_pedidos.sql           # tabla de destino del proyecto
└── datos_ejemplo/              # dos días de archivos de las dos tiendas
```

## Ejecutar (PowerShell, desde la raíz del proyecto)

```powershell
$env:ETL_CONFIG_PATH = "pipelines\ventas\config.yaml"

# 1. Estructura (crea el esquema 'ventas'; requiere un usuario con permisos de DDL)
python -m src.migrar

# 2. Día 1
New-Item -ItemType Directory -Force data\ventas\raw
Copy-Item pipelines\ventas\datos_ejemplo\*2026-11-24.csv data\ventas\raw\
python -m src.ejecutar_pipeline     # 10 leídos, 6 rechazados, 4 cargados

# 3. Repetir: no hay archivos nuevos
python -m src.ejecutar_pipeline     # 0 leídos

# 4. Día 2: llega un lote nuevo
Copy-Item pipelines\ventas\datos_ejemplo\tienda_norte_2026-11-25.csv data\ventas\raw\
python -m src.ejecutar_pipeline     # 2 leídos: 1 pedido nuevo y 1 actualizado

Remove-Item Env:ETL_CONFIG_PATH
```

Los rechazados y sus motivos quedan en `data/ventas/rejected/`.
