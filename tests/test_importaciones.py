"""
Cada módulo de src/ debe poder importarse solo, en un proceso nuevo.

Detecta importaciones circulares que no aparecen en el resto de las
pruebas (allí los módulos ya están cargados en otro orden).
"""

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
MODULOS = sorted(
    f"src.{ruta.stem}" for ruta in (RAIZ / "src").glob("*.py") if ruta.stem != "__init__"
)


@pytest.mark.parametrize("modulo", MODULOS)
def test_modulo_se_importa_en_un_proceso_limpio(modulo):

    resultado = subprocess.run(
        [sys.executable, "-c", f"import {modulo}"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert resultado.returncode == 0, resultado.stderr
