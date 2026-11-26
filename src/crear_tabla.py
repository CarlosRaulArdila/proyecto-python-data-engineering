"""
OBSOLETO - se conserva solo por compatibilidad con instrucciones antiguas.

La estructura de la base de datos ahora se gestiona con migraciones
versionadas en sql/migraciones/. Use:

    python -m src.migrar
"""

from src.migrar import main

if __name__ == "__main__":
    print("crear_tabla.py está obsoleto: ejecutando 'python -m src.migrar'.")
    raise SystemExit(main())
