"""
Descubrimiento de archivos de origen, ingesta incremental y linaje.

Cada fuente de config.yaml se declara con un archivo exacto o con un
patrón (para recibir lotes):

    fuentes:
      - nombre: "Hospital 1"
        archivo: "hospital_1.csv"          # exactamente este archivo
      - nombre: "Hospital 4"
        patron: "hospital_4_*.csv"         # todos los lotes que coincidan

    ingesta:
      modo: "completa"     # completa: procesa todos los archivos en cada ejecución
                           # incremental: solo los que no se hayan cargado antes

Cada archivo se identifica por su huella SHA-256: en modo incremental,
un archivo ya cargado se omite aunque cambie de nombre.

Flujo:
1. La etapa de consolidación descubre los archivos (`descubrir_archivos`),
   omite los ya procesados si el modo es incremental y escribe un
   manifiesto con los archivos que usó.
2. La última etapa (`registrar_ingesta`) inserta ese manifiesto en
   etl_archivos_procesados SOLO si todas las etapas anteriores terminaron
   bien. Si la carga falla, los archivos se reintentan en la siguiente
   ejecución.
"""

import fnmatch
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import text

from src.configuracion import CONFIG, resolver_ruta
from src.sql_utils import nombre_tabla

logger = logging.getLogger(__name__)

MODOS = {"completa", "incremental"}

PROCESSED_DIR = resolver_ruta(CONFIG["rutas"]["processed"])
RUTA_MANIFIESTO = PROCESSED_DIR / CONFIG["archivos"].get(
    "manifiesto", "manifiesto_archivos.json"
)

TABLA_ARCHIVOS = nombre_tabla(
    CONFIG["base_datos"]["esquema"],
    CONFIG["base_datos"].get("tabla_archivos", "etl_archivos_procesados"),
)


@dataclass(frozen=True)
class ArchivoFuente:
    fuente: str
    ruta: Path
    hash_sha256: str
    tamano_bytes: int

    @property
    def nombre(self) -> str:
        return self.ruta.name


def calcular_hash(ruta: Path, bloque: int = 1024 * 1024) -> str:
    """SHA-256 del contenido del archivo (leído por bloques, apto para archivos grandes)."""

    huella = hashlib.sha256()

    with open(ruta, "rb") as archivo:
        for parte in iter(lambda: archivo.read(bloque), b""):
            huella.update(parte)

    return huella.hexdigest()


def modo_ingesta(config: dict = CONFIG) -> str:
    modo = config.get("ingesta", {}).get("modo", "completa")

    if modo not in MODOS:
        raise ValueError(f"ingesta.modo inválido: {modo!r}. Valores admitidos: {sorted(MODOS)}")

    return modo


def validar_fuentes(fuentes: list[dict]) -> None:
    nombres = set()

    for indice, fuente in enumerate(fuentes, start=1):
        if "nombre" not in fuente:
            raise ValueError(f"La fuente #{indice} no tiene 'nombre'.")

        tiene_archivo, tiene_patron = "archivo" in fuente, "patron" in fuente

        if tiene_archivo == tiene_patron:
            raise ValueError(
                f"La fuente '{fuente['nombre']}' debe definir 'archivo' o 'patron' (solo uno)."
            )

        if fuente["nombre"] in nombres:
            raise ValueError(f"Fuente duplicada: {fuente['nombre']}")

        nombres.add(fuente["nombre"])


def descubrir_archivos(fuentes: list[dict], raw_dir: Path) -> list[ArchivoFuente]:
    """
    Devuelve los archivos de cada fuente, ordenados por nombre.

    - Fuente con 'archivo': debe existir (si no, error).
    - Fuente con 'patron': puede no tener archivos (se avisa).
    - Un archivo no puede pertenecer a dos fuentes.
    """

    validar_fuentes(fuentes)

    encontrados: list[ArchivoFuente] = []
    asignados: dict[str, str] = {}

    for fuente in fuentes:
        if "archivo" in fuente:
            ruta = raw_dir / fuente["archivo"]

            if not ruta.exists():
                raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

            rutas = [ruta]
        else:
            rutas = sorted(p for p in raw_dir.glob(fuente["patron"]) if p.is_file())

            if not rutas:
                logger.warning(
                    "La fuente '%s' no tiene archivos que coincidan con '%s' en %s",
                    fuente["nombre"],
                    fuente["patron"],
                    raw_dir,
                )

        for ruta in rutas:
            if ruta.name in asignados:
                raise ValueError(
                    f"El archivo {ruta.name} coincide con dos fuentes: "
                    f"'{asignados[ruta.name]}' y '{fuente['nombre']}'. Ajuste los patrones."
                )

            asignados[ruta.name] = fuente["nombre"]
            encontrados.append(
                ArchivoFuente(
                    fuente=fuente["nombre"],
                    ruta=ruta,
                    hash_sha256=calcular_hash(ruta),
                    tamano_bytes=ruta.stat().st_size,
                )
            )

    return encontrados


def archivos_no_configurados(fuentes: list[dict], raw_dir: Path) -> list[str]:
    """CSV presentes en raw_dir que no corresponden a ninguna fuente."""

    def pertenece(nombre: str) -> bool:
        for fuente in fuentes:
            if fuente.get("archivo") == nombre:
                return True
            if "patron" in fuente and fnmatch.fnmatch(nombre, fuente["patron"]):
                return True
        return False

    return sorted(p.name for p in raw_dir.glob("*.csv") if not pertenece(p.name))


# ------------------------------------------------------------------
# Base de datos
# ------------------------------------------------------------------


def hashes_procesados(conexion, pipeline_id: str, hashes: list[str]) -> set[str]:
    """Hashes que ya se registraron para este pipeline."""

    if not hashes:
        return set()

    filas = conexion.execute(
        text(
            f"SELECT DISTINCT hash_sha256 FROM {TABLA_ARCHIVOS} "
            "WHERE pipeline_id = :pipeline_id AND hash_sha256 = ANY(:hashes)"
        ),
        {"pipeline_id": pipeline_id, "hashes": list(hashes)},
    )

    return {fila[0].strip() for fila in filas}


def filtrar_nuevos(
    archivos: list[ArchivoFuente], ya_procesados: set[str]
) -> tuple[list[ArchivoFuente], list[ArchivoFuente]]:
    """Separa (nuevos, omitidos). También omite duplicados dentro del mismo lote."""

    nuevos, omitidos, vistos = [], [], set(ya_procesados)

    for archivo in archivos:
        if archivo.hash_sha256 in vistos:
            omitidos.append(archivo)
        else:
            nuevos.append(archivo)
            vistos.add(archivo.hash_sha256)

    return nuevos, omitidos


# ------------------------------------------------------------------
# Manifiesto (comunicación entre la consolidación y el registro final)
# ------------------------------------------------------------------


def escribir_manifiesto(entradas: list[dict], run_id: str | None, ruta: Path | None = None):
    ruta = ruta or RUTA_MANIFIESTO
    ruta.parent.mkdir(parents=True, exist_ok=True)
    contenido = {"run_id": run_id, "archivos": entradas}
    ruta.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")


def leer_manifiesto(ruta: Path | None = None) -> dict:
    ruta = ruta or RUTA_MANIFIESTO

    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el manifiesto de ingesta: {ruta}")

    return json.loads(ruta.read_text(encoding="utf-8"))


def entrada_manifiesto(archivo: ArchivoFuente, registros: int) -> dict:
    datos = asdict(archivo)
    datos["ruta"] = str(archivo.ruta)
    datos["nombre_archivo"] = archivo.nombre
    datos["registros"] = registros
    return datos


# ------------------------------------------------------------------
# Etapa final del pipeline
# ------------------------------------------------------------------


def registrar_ingesta(contexto: dict | None = None) -> dict:
    """
    Registra en etl_archivos_procesados los archivos del manifiesto.
    Se ejecuta como última etapa; si alguna etapa anterior falló, no
    registra nada para que los archivos se reintenten.
    """

    from src.conexion_db import obtener_engine

    contexto = contexto or {}

    if contexto.get("errores"):
        logger.warning(
            "Hubo errores en etapas anteriores: no se registran los archivos "
            "para que se reintenten en la próxima ejecución."
        )
        return {}

    manifiesto = leer_manifiesto()
    run_id = contexto.get("run_id") or manifiesto.get("run_id")
    pipeline_id = contexto.get("pipeline_id") or CONFIG["pipeline"]["id"]

    if manifiesto.get("run_id") and run_id and manifiesto["run_id"] != run_id:
        raise RuntimeError(
            "El manifiesto pertenece a otra ejecución "
            f"({manifiesto['run_id']}); no se registra para evitar linaje incorrecto."
        )

    archivos = manifiesto.get("archivos", [])

    if not archivos:
        logger.info("No hay archivos nuevos que registrar.")
        return {}

    with obtener_engine().begin() as conexion:
        conexion.execute(
            text(
                f"INSERT INTO {TABLA_ARCHIVOS} "
                "(pipeline_id, run_id, fuente, nombre_archivo, hash_sha256, "
                "tamano_bytes, registros) "
                "VALUES (:pipeline_id, :run_id, :fuente, :nombre_archivo, "
                ":hash_sha256, :tamano_bytes, :registros)"
            ),
            [
                {
                    "pipeline_id": pipeline_id,
                    "run_id": run_id,
                    "fuente": a["fuente"],
                    "nombre_archivo": a["nombre_archivo"],
                    "hash_sha256": a["hash_sha256"],
                    "tamano_bytes": a["tamano_bytes"],
                    "registros": a["registros"],
                }
                for a in archivos
            ],
        )

    logger.info(
        "Archivos registrados en %s: %s",
        TABLA_ARCHIVOS,
        ", ".join(a["nombre_archivo"] for a in archivos),
    )

    return {"archivos_registrados": len(archivos)}
