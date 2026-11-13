"""Piloto de factor instrumental con cobertura *externa aportada*.

IMPORTANTE: no infiere oportunidades de observación desde FIRMS;
no valida la calidad de cobertura declarada; no estima incendios.
Solo calcula una ratio de tasas de detección en fechas co-observadas
y evalúa su estabilidad en meses posteriores excluidos del ajuste.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ignis_explorer_data import normalizar_explorador


CAMPOS = ("fecha_utc", "familia", "oportunidades", "fuente")
COLUMNAS_RESULTADO = [
    "Mes UTC", "Días co-observados",
    "MODIS detecciones", "MODIS oportunidades",
    "VIIRS detecciones", "VIIRS oportunidades",
    "Referencia MODIS", "VIIRS crudo en escala MODIS",
    "VIIRS ajustado experimental",
]


def validar_cobertura(tabla: pd.DataFrame) -> pd.DataFrame:
    """Valida esquema, unicidad y cotas; NO verifica fuentes en NASA."""
    if tabla is None or tabla.empty:
        raise ValueError("Se requiere una tabla externa de cobertura, no vacía.")
    d = tabla.copy()
    d.columns = [str(c).strip().lower() for c in d.columns]
    faltan = set(CAMPOS) - set(d.columns)
    if faltan:
        raise ValueError("Faltan columnas de cobertura: " + ", ".join(sorted(faltan)))
    if len(d) > 120_000:
        raise ValueError("Demasiadas filas; acotá el archivo de cobertura.")
    fech = pd.to_datetime(d["fecha_utc"], errors="coerce", utc=True)
    d["fecha_utc"] = fech.dt.strftime("%Y-%m-%d")
    d["familia"] = d["familia"].fillna("").astype(str).str.upper().str.strip()
    d["oportunidades"] = pd.to_numeric(d["oportunidades"], errors="coerce")
    d["fuente"] = d["fuente"].fillna("").astype(str).str.strip()
    if (
        d["fecha_utc"].isna().any()
        or (~d["familia"].isin(["MODIS", "VIIRS"])).any()
        or (~np.isfinite(d["oportunidades"])).any()
        or (d["oportunidades"] <= 0).any()
        or (d["oportunidades"] > 1000).any()
        or d["fuente"].eq("").any()
    ):
        raise ValueError("Fecha, familia, oportunidades o fuente inválidas.")
    if d.duplicated(["fecha_utc", "familia"]).any():
        raise ValueError("Cada combinación fecha UTC/familia debe aparecer una sola vez.")
    return d[list(CAMPOS)].sort_values(["fecha_utc", "familia"]).reset_index(drop=True)


def _meses_cobertura_y_observaciones(
    datos: pd.DataFrame | None, cobertura: pd.DataFrame
) -> pd.DataFrame:
    """Usa exclusivamente fechas con exposición declarada para ambos sensores."""
    z = normalizar_explorador(datos)
    o = validar_cobertura(cobertura)
    fechas = o.groupby("fecha_utc").familia.nunique()
    ambos_dias = set(fechas[fechas == 2].index)
    o = o[o.fecha_utc.isin(ambos_dias)].copy()
    if o.empty:
        return pd.DataFrame()
    counts = z.groupby(["dia_utc", "familia"]).size().rename("detecciones")
    o = o.join(counts, on=["fecha_utc", "familia"])
    # Cero se permite SOLO para días que un archivo externo declara observados.
    o["detecciones"] = o["detecciones"].fillna(0).astype(int)
    o["mes"] = o.fecha_utc.str.slice(0, 7)
    resumen = o.groupby(["mes", "familia"]).agg(
        detecciones=("detecciones", "sum"),
        oportunidades=("oportunidades", "sum"),
        dias=("fecha_utc", "nunique"),
    )
    r = resumen.unstack("familia")
    if r.empty:
        return pd.DataFrame()
    # Aplanar nombres; ambos sensores están presentes en cada día seleccionado.
    r.columns = [f"{variable}_{familia}" for variable, familia in r.columns]
    return r.sort_index().reset_index(names="Mes UTC")


def _ratio(m: pd.DataFrame) -> float | None:
    if m.empty:
        return None
    ref_exp = float(m["oportunidades_MODIS"].sum())
    src_exp = float(m["oportunidades_VIIRS"].sum())
    if min(ref_exp, src_exp) <= 0:
        return None
    ref_rate = float(m["detecciones_MODIS"].sum()) / ref_exp
    src_rate = float(m["detecciones_VIIRS"].sum()) / src_exp
    if src_rate <= 0 or ref_rate <= 0:
        return None
    return ref_rate / src_rate


def evaluar_prototipo(
    datos: pd.DataFrame | None,
    cobertura: pd.DataFrame,
    min_meses: int = 10,
    min_dias_mes: int = 3,
    bootstrap: int = 400,
) -> dict:
    """Diagnóstico condicionado a cobertura aportada; NO producto calibrado.

    Retiene los últimos 30 % meses comparables como prueba temporal fuera
    de muestra; estima factor agregado en meses anteriores. Bootstrap solo
    sobre los meses de entrenamiento para IC del factor (no de incendios).
    """
    if min_meses < 10 or min_dias_mes < 1 or bootstrap < 20 or bootstrap > 2000:
        raise ValueError("Configuración de validación fuera de límites.")
    comparables = _meses_cobertura_y_observaciones(datos, cobertura)
    if comparables.empty:
        return {
            "estado": "insuficiente",
            "motivo": "No hay fechas co-observadas de MODIS y VIIRS en la cobertura aportada.",
            "meses": pd.DataFrame(),
        }
    q = comparables.copy()
    q = q[
        (q["dias_MODIS"] >= min_dias_mes)
        & (q["dias_VIIRS"] >= min_dias_mes)
    ].reset_index(drop=True)
    if len(q) < min_meses:
        return {
            "estado": "insuficiente",
            "motivo": f"Solo {len(q)} meses con al menos {min_dias_mes} días co-observados; se requieren {min_meses}.",
            "meses": q,
        }
    train_n = min(len(q) - 3, max(6, math.floor(len(q) * .70)))
    train, hold = q.iloc[:train_n].copy(), q.iloc[train_n:].copy()
    beta = _ratio(train)
    if beta is None:
        return {
            "estado": "insuficiente",
            "motivo": "No hay suficientes detecciones en ambas familias durante entrenamiento para estimar una razón estable.",
            "meses": q,
        }
    rng = np.random.default_rng(2026)
    b = []
    for _ in range(bootstrap):
        ids = rng.integers(0, len(train), size=len(train))
        val = _ratio(train.iloc[ids])
        if val is not None and np.isfinite(val):
            b.append(val)
    if len(b) < 20:
        return {"estado": "insuficiente", "motivo": "Bootstrap del factor insuficiente.", "meses": q}
    lo, hi = np.quantile(b, [.025, .975]).tolist()
    # Tasas = detecciones divididas por oportunidades externamente declaradas;
    # se proyectan sobre las oportunidades MODIS en el mes correspondiente.
    resultado = q.copy()
    resultado["Referencia MODIS"] = resultado["detecciones_MODIS"].astype(float)
    resultado["VIIRS crudo en escala MODIS"] = (
        resultado["detecciones_VIIRS"] / resultado["oportunidades_VIIRS"]
        * resultado["oportunidades_MODIS"]
    )
    resultado["VIIRS ajustado experimental"] = (
        resultado["VIIRS crudo en escala MODIS"] * beta
    )
    resultado["subconjunto"] = ["ajuste"] * train_n + ["evaluación"] * len(hold)
    test = resultado.iloc[train_n:].copy()
    ref = test["Referencia MODIS"].to_numpy(dtype=float)
    raw = test["VIIRS crudo en escala MODIS"].to_numpy(dtype=float)
    calibrated = test["VIIRS ajustado experimental"].to_numpy(dtype=float)
    mae_raw = float(np.mean(np.abs(raw - ref)))
    mae_cal = float(np.mean(np.abs(calibrated - ref)))
    vista = resultado.rename(columns={
        "dias_MODIS": "Días co-observados",
        "detecciones_MODIS": "MODIS detecciones",
        "oportunidades_MODIS": "MODIS oportunidades",
        "detecciones_VIIRS": "VIIRS detecciones",
        "oportunidades_VIIRS": "VIIRS oportunidades",
    })
    vista = vista[COLUMNAS_RESULTADO + ["subconjunto"]].copy()
    return {
        "estado": "experimental",
        "motivo": (
            "Comparación de tasas en días co-observados según cobertura aportada "
            "por la persona usuaria; la fuente no se valida automáticamente."
        ),
        "factor": float(beta),
        "factor_bootstrap_95": [float(lo),float(hi)],
        "meses_entrenamiento": int(len(train)),
        "meses_evaluacion": int(len(hold)),
        "mae_original": mae_raw,
        "mae_experimental": mae_cal,
        "meses": vista,
        "cobertura_verificada_independientemente": False,
        "calibracion_cientifica_validada": False,
    }
