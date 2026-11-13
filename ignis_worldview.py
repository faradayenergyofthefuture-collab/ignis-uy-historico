"""Enlaces de inspección reproducible en NASA Worldview.

Worldview es una fuente de CONTEXTO visual independiente, no valida
por sí sola una detección FIRMS o su tamaño en terreno.
Referencia de parámetros: nasa-gibs/worldview, doc/url_parameters.md.
"""
from __future__ import annotations

from urllib.parse import urlencode

import pandas as pd


def enlace_worldview(fecha: object, latitud: float, longitud: float, radio_grados: float = 0.20) -> str:
    """Abrir fecha y área en la proyección geográfica de NASA Worldview."""
    lat, lon, radio = float(latitud), float(longitud), float(radio_grados)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordenadas geográficas fuera de rango.")
    if not 0 < radio <= 5:
        raise ValueError("El radio del mapa debe estar entre 0 y 5 grados.")
    fecha_dt = pd.to_datetime(fecha, errors="coerce", utc=True)
    if pd.isna(fecha_dt):
        raise ValueError("Fecha no válida.")
    dia = fecha_dt.strftime("%Y-%m-%d")
    # No cruzar los bordes geográficos internacionales; el recorte operativo
    # de IGNIS es Uruguay y por lo tanto no necesita antimeridiano.
    oeste, este = max(-180, lon-radio), min(180, lon+radio)
    sur, norte = max(-90, lat-radio), min(90, lat+radio)
    vista = ",".join(f"{v:.5f}" for v in (oeste,sur,este,norte))
    return "https://worldview.earthdata.nasa.gov/?" + urlencode(
        {"p":"geographic","v":vista,"t":dia}
    )
