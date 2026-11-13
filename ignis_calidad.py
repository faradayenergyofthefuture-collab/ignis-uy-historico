"""Auditoría de calidad FIRMS sin inventar cobertura satelital.

Días con DETECCIONES no son días OBSERVADOS. Las advertencias ayudan a
evaluar la suficiencia del Maestro antes de calibrar MODIS y VIIRS.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ignis_pareo_v5 import tiempos_adquisicion


def auditar_datos(datos: pd.DataFrame | None) -> dict:
    if datos is None or datos.empty:
        return {
            "filas": 0, "coordenadas_validas": 0, "fechas_validas": 0,
            "horarios_validos": 0, "instrumentos_reconocidos": 0,
            "frp_disponible": 0, "ids_repetidos": 0,
            "cobertura_verificada": False,
        }
    z = datos.copy()
    n = len(z)
    lat = pd.to_numeric(z["latitude"], errors="coerce") if "latitude" in z else pd.Series(np.nan,index=z.index)
    lon = pd.to_numeric(z["longitude"], errors="coerce") if "longitude" in z else pd.Series(np.nan,index=z.index)
    fech = pd.to_datetime(z["fecha"], errors="coerce", utc=True) if "fecha" in z else pd.Series(pd.NaT,index=z.index,dtype="datetime64[ns, UTC]")
    inst = z["instrumento"].fillna("").astype(str).str.upper().str.strip() if "instrumento" in z else pd.Series("",index=z.index)
    if "fecha" in z:
        hora = tiempos_adquisicion(z)
    else:
        hora = pd.Series(pd.NaT,index=z.index,dtype="datetime64[ns, UTC]")
    frp = pd.to_numeric(z["frp"], errors="coerce") if "frp" in z else pd.Series(np.nan,index=z.index)
    ids = z["id_registro"].fillna("").astype(str).str.strip() if "id_registro" in z else pd.Series("",index=z.index)
    existen_ids = ids.ne("")
    repetidos = int(ids[existen_ids].duplicated(keep="first").sum())
    return {
        "filas": int(n),
        "coordenadas_validas": int((lat.between(-90,90) & lon.between(-180,180)).sum()),
        "fechas_validas": int(fech.notna().sum()),
        "horarios_validos": int(hora.notna().sum()),
        "instrumentos_reconocidos": int((inst.str.startswith("MODIS") | inst.str.startswith("VIIRS")).sum()),
        "frp_disponible": int(frp.notna().sum()),
        "ids_repetidos": repetidos,
        "cobertura_verificada": False,
    }


def inventario_mensual(datos: pd.DataFrame | None, ano: int) -> pd.DataFrame:
    """Una fila por mes y sensor presente en el recorte.

    Los meses sin filas se señalan 'SIN REGISTROS IMPORTADOS' y nunca se
    interpretan como 'cobertura completa sin detecciones'.
    """
    columnas = [
        "Mes UTC", "Instrumento", "Observaciones importadas",
        "Días con detecciones", "Horarios válidos", "FRP disponible",
        "Estado de datos", "Cobertura orbital verificada",
    ]
    if datos is None or datos.empty or not {"fecha","instrumento"}.issubset(datos):
        return pd.DataFrame(columns=columnas)
    z = datos.copy()
    z["fecha_dt"] = pd.to_datetime(z["fecha"], errors="coerce", utc=True)
    z = z[z.fecha_dt.notna()]
    z = z[z.fecha_dt.dt.year == int(ano)]
    if z.empty:
        return pd.DataFrame(columns=columnas)
    z["mes"] = z.fecha_dt.dt.month
    z["dia"] = z.fecha_dt.dt.strftime("%Y-%m-%d")
    z["instrumento"] = z.instrumento.fillna("").astype(str).str.strip()
    z = z[z.instrumento.str.upper().str.startswith(("MODIS","VIIRS"))]
    if z.empty:
        return pd.DataFrame(columns=columnas)
    z["hora_ok"] = tiempos_adquisicion(z).notna()
    z["frp_ok"] = pd.to_numeric(
        z["frp"] if "frp" in z else pd.Series(np.nan,index=z.index),
        errors="coerce"
    ).notna()
    resumen = z.groupby(["mes", "instrumento"]).agg(
        observaciones=("dia","size"),
        dias=("dia","nunique"),
        horarios=("hora_ok","sum"),
        frp=("frp_ok","sum"),
    )
    sensores = sorted(z.instrumento.unique())
    filas = []
    for mes in range(1,13):
        for sensor in sensores:
            indice = (mes,sensor)
            if indice in resumen.index:
                a = resumen.loc[indice]
                n,d,h,f = map(int,[a.observaciones,a.dias,a.horarios,a.frp])
                estado="CON DETECCIONES IMPORTADAS"
            else:
                n=d=h=f=0
                estado="SIN REGISTROS IMPORTADOS"
            filas.append([
                f"{int(ano)}-{mes:02d}", sensor,n,d,h,f,estado,"NO",
            ])
    return pd.DataFrame(filas,columns=columnas)


def lectura_diagnostica(auditoria: dict) -> list[str]:
    avisos = []
    n = int(auditoria["filas"])
    if not n:
        return ["Sin registros importados: no se puede inferir cobertura ni ausencia de actividad térmica."]
    for etiqueta,campo in (
        ("coordenadas","coordenadas_validas"),
        ("fechas","fechas_validas"),
        ("horarios UTC","horarios_validos"),
        ("familia instrumental","instrumentos_reconocidos"),
    ):
        faltan = n - int(auditoria[campo])
        if faltan:
            avisos.append(f"{faltan:,} de {n:,} registros sin {etiqueta} válida.")
    if auditoria["ids_repetidos"]:
        avisos.append(f"Hay {auditoria['ids_repetidos']:,} IDs repetidos en esta tabla.")
    avisos.append("No se han verificado oportunidades de observación, nubosidad ni cobertura instrumental.")
    return avisos
