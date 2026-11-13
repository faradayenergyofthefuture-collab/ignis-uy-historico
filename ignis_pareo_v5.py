"""Pareo exploratorio MODIS–VIIRS con unicidad global y continuidad UTC.

No iguala sensibilidades, no calibra FRP, no identifica incendios únicos.
A diferencia del pareo original, permite cruces a medianoche UTC y no
reutiliza un registro MODIS o VIIRS en otra pareja del mismo resultado.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

R_TIERRA_KM = 6371.0088
COLUMNAS = [
    "modis", "viirs", "fecha_modis_utc", "fecha_viirs_utc",
    "distancia_km", "diferencia_min", "cruza_dia_utc",
    "lat_modis", "lon_modis", "lat_viirs", "lon_viirs",
    "frp_modis", "frp_viirs",
]


def tiempos_adquisicion(datos: pd.DataFrame) -> pd.Series:
    """Interpretar acq_time FIRMS como HHMM UTC, descartando tiempos inválidos."""
    fecha = pd.to_datetime(datos["fecha"], errors="coerce", utc=True)
    if "acq_time" not in datos.columns:
        return pd.Series(pd.NaT, index=datos.index, dtype="datetime64[ns, UTC]")
    texto = (datos["acq_time"].fillna("").astype(str).str.strip()
             .str.replace(r"\\.0$", "", regex=True))
    valido = texto.str.fullmatch(r"\\d{1,4}").fillna(False)
    texto = texto.where(valido, "").str.zfill(4)
    hh = pd.to_numeric(texto.str.slice(0, 2), errors="coerce")
    mm = pd.to_numeric(texto.str.slice(2, 4), errors="coerce")
    valido = valido & hh.between(0, 23) & mm.between(0, 59)
    minutos = (hh * 60 + mm).where(valido)
    tiempo = fecha.dt.normalize() + pd.to_timedelta(minutos, unit="m")
    return tiempo.where(valido & fecha.notna())


def _xyz(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    lat = np.radians(lats.astype(float))
    lon = np.radians(lons.astype(float))
    return np.column_stack([
        np.cos(lat) * np.cos(lon),
        np.cos(lat) * np.sin(lon),
        np.sin(lat),
    ])


def preparar_pareo(datos: pd.DataFrame | None) -> pd.DataFrame:
    """Registro válido = lat/lon, fecha, hora UTC y familia inequívocas."""
    if datos is None or datos.empty:
        return pd.DataFrame(columns=[
            "instrumento", "latitude", "longitude", "frp", "instante", "dia_utc"
        ])
    requeridas = {"fecha", "latitude", "longitude", "instrumento"}
    faltantes = requeridas - set(datos.columns)
    if faltantes:
        raise ValueError("Faltan columnas para pareo: " + ", ".join(sorted(faltantes)))
    z = datos.copy()
    z["latitude"] = pd.to_numeric(z["latitude"], errors="coerce")
    z["longitude"] = pd.to_numeric(z["longitude"], errors="coerce")
    z["instrumento"] = z["instrumento"].fillna("").astype(str).str.strip()
    z["familia"] = np.select(
        [z.instrumento.str.upper().str.startswith("MODIS"),
         z.instrumento.str.upper().str.startswith("VIIRS")],
        ["MODIS", "VIIRS"], default="",
    )
    z["instante"] = tiempos_adquisicion(z)
    z["frp"] = pd.to_numeric(
        z["frp"] if "frp" in z else pd.Series(np.nan, index=z.index),
        errors="coerce",
    )
    z = z.loc[
        z.latitude.between(-90, 90) & z.longitude.between(-180, 180)
        & z.instante.notna() & z.familia.ne("")
    ].copy()
    if z.empty:
        return z
    z["dia_utc"] = z.instante.dt.floor("D")
    # El Maestro ya está deduplicado; esto evita replicados accidentales
    # también al llamar el módulo con tablas de laboratorio.
    if "id_registro" in z:
        ids = z["id_registro"].fillna("").astype(str).str.strip()
        con_id = ids.ne("")
        z["_identificador"] = np.where(
            con_id, ids,
            z["instrumento"] + "|" + z["instante"].astype(str)
            + "|" + z["latitude"].astype(str) + "|" + z["longitude"].astype(str),
        )
    else:
        z["_identificador"] = (
            z["instrumento"] + "|" + z["instante"].astype(str)
            + "|" + z["latitude"].astype(str) + "|" + z["longitude"].astype(str)
        )
    z = z.drop_duplicates(subset=["familia", "_identificador"]).reset_index(drop=True)
    return z


def emparejar_global(
    datos: pd.DataFrame | None,
    ano: int | None = None,
    radio_km: float = 5.0,
    ventana_min: int = 30,
    max_candidatos: int = 250_000,
) -> pd.DataFrame:
    """Seleccionar parejas globalmente únicas, ordenadas por tiempo y distancia.

    El filtro de año se aplica a MODIS (referencia); se pueden asociar
    observaciones VIIRS del día siguiente cuando existe cruce de año.
    Una estrategia greedy no equivale a emparejamiento global de costo mínimo.
    """
    if not (0 < float(radio_km) <= 50):
        raise ValueError("radio_km debe estar entre 0 y 50.")
    if not (0 <= int(ventana_min) <= 1440):
        raise ValueError("ventana_min debe estar entre 0 y 1440.")
    if max_candidatos < 1:
        raise ValueError("max_candidatos debe ser positivo.")
    z = preparar_pareo(datos)
    if z.empty:
        return pd.DataFrame(columns=COLUMNAS)
    m = z[z["familia"] == "MODIS"].copy()
    v = z[z["familia"] == "VIIRS"].copy()
    if ano is not None:
        m = m[m.instante.dt.year == int(ano)]
    if m.empty or v.empty:
        return pd.DataFrame(columns=COLUMNAS)
    # Restringir a ±1 día UTC para ventana <=24 h; evita O(M*V) global.
    v_por_dia = {dia: df for dia, df in v.groupby("dia_utc", sort=False)}
    radio_cuerda = 2 * np.sin(float(radio_km) / (2 * R_TIERRA_KM))
    candidatos = []
    for dia, ma in m.groupby("dia_utc", sort=True):
        partes = [
            v_por_dia[dia + pd.Timedelta(days=offset)]
            for offset in (-1, 0, 1)
            if dia + pd.Timedelta(days=offset) in v_por_dia
        ]
        if not partes:
            continue
        vi = pd.concat(partes, axis=0)
        x = _xyz(ma.latitude.to_numpy(), ma.longitude.to_numpy())
        y = _xyz(vi.latitude.to_numpy(), vi.longitude.to_numpy())
        vecinos = cKDTree(x).query_ball_tree(cKDTree(y), r=radio_cuerda)
        m_ids = ma.index.to_numpy()
        v_ids = vi.index.to_numpy()
        m_t = ma.instante.astype("int64").to_numpy()
        v_t = vi.instante.astype("int64").to_numpy()
        for i, indices in enumerate(vecinos):
            for j in indices:
                minutos = abs(int(m_t[i]) - int(v_t[j])) / 60_000_000_000
                if minutos > ventana_min:
                    continue
                cuerda = np.linalg.norm(x[i] - y[j])
                distancia = 2 * R_TIERRA_KM * np.arcsin(min(1.0, cuerda / 2))
                candidatos.append((minutos, float(distancia), int(m_ids[i]), int(v_ids[j])))
                if len(candidatos) > max_candidatos:
                    raise ValueError(
                        "Demasiados candidatos para el modo interactivo. "
                        "Reducí el radio, la ventana temporal o el recorte."
                    )
    usados_m, usados_v, salida = set(), set(), []
    for minutos, distancia, i, j in sorted(candidatos):
        if i in usados_m or j in usados_v:
            continue
        usados_m.add(i)
        usados_v.add(j)
        a, b = z.loc[i], z.loc[j]
        salida.append([
            a.instrumento, b.instrumento,
            a.instante.strftime("%Y-%m-%d %H:%M UTC"),
            b.instante.strftime("%Y-%m-%d %H:%M UTC"),
            round(distancia, 3), round(minutos, 2),
            bool(a.dia_utc != b.dia_utc),
            float(a.latitude), float(a.longitude),
            float(b.latitude), float(b.longitude),
            a.frp, b.frp,
        ])
    return pd.DataFrame(salida, columns=COLUMNAS)


def resumen_global(pares: pd.DataFrame) -> dict:
    if pares is None or pares.empty:
        return {"pares": 0, "cruces_medianoche": 0, "distancia_mediana_km": None}
    return {
        "pares": int(len(pares)),
        "cruces_medianoche": int(pares["cruza_dia_utc"].sum()),
        "distancia_mediana_km": float(pares["distancia_km"].median()),
    }
