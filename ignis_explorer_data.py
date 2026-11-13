"""Motor determinista del Explorador IGNIS — datos realmente cargados.

Separa explícitamente celdas sin registros importados de valores cero
observados (no calculables sin metadatos de oportunidad y cobertura).
"""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pandas as pd

FAMILIAS = ("MODIS", "VIIRS")
MESES = (
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
)
VERSION = "IGNIS EXPLORER 6.0 | datos exploratorios"


def normalizar_explorador(datos: pd.DataFrame | None) -> pd.DataFrame:
    """Normaliza una copia sin mutar Maestro ni alterar la procedencia."""
    columnas = ["fecha", "latitude", "longitude", "instrumento"]
    if datos is None or datos.empty:
        return pd.DataFrame(columns=columnas + ["familia", "fecha_utc", "anio", "mes", "dia_utc", "frp"])
    faltan = set(columnas) - set(datos.columns)
    if faltan:
        raise ValueError("El Maestro requiere columnas: " + ", ".join(sorted(faltan)))
    x = datos.copy()
    x["fecha_utc"] = pd.to_datetime(x["fecha"], errors="coerce", utc=True)
    x["latitude"] = pd.to_numeric(x["latitude"], errors="coerce")
    x["longitude"] = pd.to_numeric(x["longitude"], errors="coerce")
    ins = x["instrumento"].fillna("").astype(str).str.upper().str.strip()
    x["familia"] = np.select(
        [ins.str.startswith("MODIS"), ins.str.startswith("VIIRS")],
        ["MODIS", "VIIRS"], default="",
    )
    x["frp"] = pd.to_numeric(
        x["frp"] if "frp" in x else pd.Series(np.nan, index=x.index),
        errors="coerce",
    )
    x = x[
        x["fecha_utc"].notna()
        & x["latitude"].between(-90, 90)
        & x["longitude"].between(-180, 180)
        & x["familia"].isin(FAMILIAS)
    ].copy()
    if x.empty:
        return x
    x["anio"] = x["fecha_utc"].dt.year.astype(int)
    x["mes"] = x["fecha_utc"].dt.month.astype(int)
    x["dia_utc"] = x["fecha_utc"].dt.strftime("%Y-%m-%d")
    return x.reset_index(drop=True)


def calendario_instrumental(datos: pd.DataFrame | None, familia: str) -> pd.DataFrame:
    """Matriz año×mes: NaN = sin datos importados, NO cero incendios."""
    if familia not in FAMILIAS:
        raise ValueError("Familia instrumental desconocida.")
    z = normalizar_explorador(datos)
    if z.empty:
        return pd.DataFrame(columns=list(range(1, 13)), dtype=float)
    years = range(int(z.anio.min()), int(z.anio.max()) + 1)
    counts = z[z.familia == familia].groupby(["anio", "mes"]).size()
    table = counts.unstack().reindex(index=years, columns=range(1, 13))
    return table.astype(float)


def comparacion_mensual(datos: pd.DataFrame | None) -> pd.DataFrame:
    """Registros por mes en el Maestro, sin sumar familias como incendios."""
    z = normalizar_explorador(datos)
    columns = ["Mes UTC", "MODIS", "VIIRS", "Ambos presentes"]
    if z.empty:
        return pd.DataFrame(columns=columns)
    counts = z.groupby([z.fecha_utc.dt.strftime("%Y-%m"), "familia"]).size()
    wide = counts.unstack(fill_value=0)
    for name in FAMILIAS:
        if name not in wide:
            wide[name] = 0
    wide = wide[list(FAMILIAS)].sort_index().reset_index(names="Mes UTC")
    wide["Ambos presentes"] = (wide.MODIS > 0) & (wide.VIIRS > 0)
    return wide[columns]


def resumen_explorador(datos: pd.DataFrame | None) -> dict:
    z = normalizar_explorador(datos)
    cmp = comparacion_mensual(z if "fecha" in z else datos)
    return {
        "observaciones": int(len(z)),
        "anios_con_registros": int(z.anio.nunique()) if len(z) else 0,
        "meses_con_ambas_familias": int(cmp["Ambos presentes"].sum()) if len(cmp) else 0,
        "ultima_observacion_utc": z.fecha_utc.max().strftime("%Y-%m-%d") if len(z) else None,
        "fecha_minima_utc": z.fecha_utc.min().strftime("%Y-%m-%d") if len(z) else None,
        "n_modis": int((z.familia == "MODIS").sum()) if len(z) else 0,
        "n_viirs": int((z.familia == "VIIRS").sum()) if len(z) else 0,
        "datos_calibrados": False,
        "cobertura_validada": False,
    }


def series_anuales(datos: pd.DataFrame | None) -> pd.DataFrame:
    z = normalizar_explorador(datos)
    if z.empty:
        return pd.DataFrame(columns=["Año", "Familia", "Observaciones"])
    out = z.groupby(["anio", "familia"]).size().reset_index(name="Observaciones")
    return out.rename(columns={"anio": "Año", "familia": "Familia"})



def demo_sintetica() -> pd.DataFrame:
    """Datos generados, NO observaciones NASA, para probar interfaz sin claves.

    Dataset de ejemplo deliberadamente breve, limitado a años seleccionados.
    NUNCA se incorpora automáticamente al Maestro IGNIS ni a alertas.
    """
    rng = np.random.default_rng(2026)
    filas = []
    for year in (2001, 2005, 2012, 2018, 2023, 2026):
        for mes in (1, 2, 12):
            for sensor in ("MODIS", "VIIRS NOAA-20"):
                if sensor.startswith("VIIRS") and year < 2018:
                    continue
                n = 4 + (year % 5) + (mes % 3)
                if sensor.startswith("VIIRS"):
                    n = n * 2
                for idx in range(n):
                    day = int(rng.integers(1, 25))
                    filas.append({
                        "fecha": f"{year:04d}-{mes:02d}-{day:02d}",
                        "latitude": float(rng.uniform(-35, -30.2)),
                        "longitude": float(rng.uniform(-58.4, -53.2)),
                        "instrumento": sensor,
                        "satellite": "N20" if sensor.startswith("VIIRS") else "A",
                        "acq_time": "1415",
                        "frp": None,
                        "confidence": "simulada",
                        "fuente": "SIMULACION ARTIFICIAL — NO NASA FIRMS",
                        "id_registro": f"DEMO-{year}-{mes}-{sensor}-{idx:03d}",
                    })
    return pd.DataFrame(filas)

def crear_exportacion(datos: pd.DataFrame | None, region: str, filtros: list[str], demo: bool = False) -> bytes:
    """Paquete verificable: no modifica el Maestro ni afirma armonización."""
    z = normalizar_explorador(datos)
    # Los campos adicionales de fuente/ID se conservan si existen.
    keep = [
        col for col in (
            "fecha", "latitude", "longitude", "instrumento", "satellite",
            "acq_time", "frp", "confidence", "fuente", "id_registro"
        ) if col in z.columns
    ]
    observaciones = z[keep].to_csv(index=False).encode("utf-8-sig")
    mensual = comparacion_mensual(z).to_csv(index=False).encode("utf-8-sig")
    huellas = {
        "observaciones.csv": hashlib.sha256(observaciones).hexdigest(),
        "comparacion_mensual.csv": hashlib.sha256(mensual).hexdigest(),
    }
    manifest = {
        "project": "IGNIS UY",
        "version": VERSION,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "region_selected": str(region),
        "instrument_filters": list(map(str, filtros)),
        "data_source": ("DATOS SINTÉTICOS PARA DEMOSTRACIÓN — NO NASA" if demo else "NASA FIRMS, archivos efectivamente cargados en el Maestro IGNIS"),
        "demo_sintetica": bool(demo),
        "observation_count": int(len(z)),
        "date_range_utc": [
            z.fecha_utc.min().strftime("%Y-%m-%d") if len(z) else None,
            z.fecha_utc.max().strftime("%Y-%m-%d") if len(z) else None,
        ],
        "sha256": huellas,
        "scientific_status": {
            "counts_are_raw_observations": True,
            "quantitative_harmonization": False,
            "instrument_coverage_verified": False,
            "unique_fire_events": False,
            "absence_of_records_means_zero_fires": False,
        },
        "limitations": [
            "Las observaciones NASA FIRMS no son incendios únicos ni área quemada.",
            "No hay datos orbitales ni cobertura verificada; una celda vacía no es cero fuego.",
            "Los recuentos de diferentes instrumentos no están calibrados.",
        ],
    }
    info = (
        "IGNIS UY — EXPORTACIÓN DE INVESTIGACIÓN\n"
        "Los valores CSV son observaciones térmicas NASA FIRMS importadas, NO incendios únicos.\n"
        "No se estiman cobertura de satélite, armonización cuantitativa ni superficie quemada.\n"
        "El archivo manifest.json contiene filtros, método, fecha, y hashes SHA-256.\n"
    )
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("observaciones.csv", observaciones)
        zf.writestr("comparacion_mensual.csv", mensual)
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("LEEME.txt", info)
    return stream.getvalue()
