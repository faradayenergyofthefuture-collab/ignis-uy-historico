"""Diagnóstico de sensibilidad espacial de la coincidencia MODIS–VIIRS.

No armoniza radiometría, cobertura, probabilidades de detección ni FRP.
Los ceros representan ausencia de registros *en los archivos cargados*,
NO observación satelital con ausencia de fuego.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RESOLUCIONES = (0.05, 0.10, 0.20, 0.40)
COLUMNAS = [
    "Resolución (°)", "Celdas-día con ambos", "Días con coincidencia",
    "Meses con coincidencia", "Meses con ambas familias",
]


def preparar_observaciones(datos: pd.DataFrame | None) -> pd.DataFrame:
    """Conservar observaciones fechadas, geolocalizadas y con familia reconocida.

    La identidad de satélite y los recuentos originales no se sustituyen.
    """
    cols = ["fecha_utc", "mes_utc", "anio", "latitude", "longitude", "familia"]
    if datos is None or datos.empty:
        return pd.DataFrame(columns=cols)
    faltantes = {"fecha", "latitude", "longitude", "instrumento"} - set(datos.columns)
    if faltantes:
        raise ValueError("Faltan columnas del Maestro: " + ", ".join(sorted(faltantes)))

    z = datos[["fecha", "latitude", "longitude", "instrumento"]].copy()
    fecha = pd.to_datetime(z["fecha"], errors="coerce", utc=True)
    z["latitude"] = pd.to_numeric(z["latitude"], errors="coerce")
    z["longitude"] = pd.to_numeric(z["longitude"], errors="coerce")
    nombre = z["instrumento"].fillna("").astype(str).str.upper().str.strip()
    z["familia"] = np.select(
        [nombre.str.startswith("MODIS"), nombre.str.startswith("VIIRS")],
        ["MODIS", "VIIRS"], default="",
    )
    z["fecha_utc"] = fecha.dt.strftime("%Y-%m-%d")
    z["mes_utc"] = fecha.dt.strftime("%Y-%m")
    z["anio"] = fecha.dt.year
    z = z.dropna(subset=["fecha_utc", "latitude", "longitude", "anio"])
    z = z[
        z["latitude"].between(-90, 90)
        & z["longitude"].between(-180, 180)
        & z["familia"].isin(["MODIS", "VIIRS"])
    ]
    return z[cols].copy().reset_index(drop=True)


def presencia_mensual(datos: pd.DataFrame | None) -> pd.DataFrame:
    """Recuentos por mes/familia del archivo importado, sin inferir cobertura."""
    cols = ["Mes UTC", "MODIS", "VIIRS", "Ambas presentes"]
    z = preparar_observaciones(datos)
    if z.empty:
        return pd.DataFrame(columns=cols)
    p = z.groupby(["mes_utc", "familia"]).size().unstack(fill_value=0)
    for sensor in ("MODIS", "VIIRS"):
        if sensor not in p:
            p[sensor] = 0
    p = p[["MODIS", "VIIRS"]].sort_index().reset_index()
    p["Ambas presentes"] = (p.MODIS > 0) & (p.VIIRS > 0)
    return p.rename(columns={"mes_utc": "Mes UTC"})[cols]


def comparar_resoluciones(
    datos: pd.DataFrame | None,
    ano: int | None = None,
    resoluciones: tuple[float, ...] = RESOLUCIONES,
) -> pd.DataFrame:
    """Contar celdas-día coincidentes según tamaño de la cuadrícula.

    Reproduce la convención del Maestro: round(lat/grados) y round(lon/grados).
    'Celdas-día' = misma fecha UTC + celda + presencia de ambas familias.
    """
    z = preparar_observaciones(datos)
    if ano is not None:
        z = z[z["anio"] == int(ano)]
    meses_ambos = int(presencia_mensual(z)["Ambas presentes"].sum()) if not z.empty else 0
    salida = []
    for res in resoluciones:
        res = float(res)
        if not np.isfinite(res) or res <= 0 or res > 5:
            raise ValueError("La resolución debe estar entre 0 y 5 grados, sin incluir 0.")
        if z.empty:
            salida.append([res, 0, 0, 0, 0])
            continue
        q = z.copy()
        q["grid_lat"] = np.rint(q["latitude"] / res).astype(int)
        q["grid_lon"] = np.rint(q["longitude"] / res).astype(int)
        g = q.groupby(
            ["fecha_utc", "grid_lat", "grid_lon", "familia"], sort=True
        ).size().unstack(fill_value=0)
        for sensor in ("MODIS", "VIIRS"):
            if sensor not in g:
                g[sensor] = 0
        coinciden = g[(g["MODIS"] > 0) & (g["VIIRS"] > 0)]
        dias = coinciden.index.get_level_values("fecha_utc").unique()
        meses = pd.Index(dias.str.slice(0, 7)).nunique()
        salida.append([res, int(len(coinciden)), int(len(dias)), int(meses), meses_ambos])
    return pd.DataFrame(salida, columns=COLUMNAS)


def diagnostico_comparabilidad(datos: pd.DataFrame | None) -> dict:
    """Resumen descriptivo: NO calcula ni autoriza una serie calibrada."""
    z = preparar_observaciones(datos)
    meses = presencia_mensual(z)
    return {
        "registros": int(len(z)),
        "meses_importados": int(len(meses)),
        "meses_con_ambas_familias": int(meses["Ambas presentes"].sum()) if len(meses) else 0,
        "dias_con_detecciones_modis": int(z.loc[z.familia == "MODIS", "fecha_utc"].nunique()),
        "dias_con_detecciones_viirs": int(z.loc[z.familia == "VIIRS", "fecha_utc"].nunique()),
        "cobertura_satelital_verificada": False,
        "serie_armonizada_validada": False,
    }
