"""Compatibilidad: mantiene la app principal en ignis_historico.py.
Este archivo no tiene lógica nueva; solo delega la ejecución al dashboard real.
"""

import runpy

if __name__ == "__main__":
    runpy.run_path("ignis_historico.py", run_name="__main__")
