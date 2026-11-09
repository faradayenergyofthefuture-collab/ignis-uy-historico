"""Motor transparente de consultas estadísticas de ASK IGNIS.

No utiliza un LLM, IA generativa ni servicios externos: solo reglas explícitas
y los registros cargados por la persona usuaria. No valida incendios.
"""
import unicodedata

import pandas as pd


def normalizar_pregunta(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip()


def _resultado(respuesta: str, grafico=None, fuentes=None):
    return {
        "answer": respuesta,
        "chart": grafico,
        "sources": fuentes if fuentes is not None else [],
    }


def responder_ignis(datos: pd.DataFrame, pregunta: str):
    """Responde en español sin atribuir los resultados a un modelo de IA.

    La función no suma detecciones como si fueran incendios únicos ni crea
    datos a partir de preguntas. Los filtros se aplican al archivo recibido.
    """
    q = normalizar_pregunta(pregunta)
    if not q:
        return _resultado("Escribí una consulta sobre tus registros FIRMS.")

    if any(t in q for t in ("que es ask ignis", "que ia", "que modelo", "como funciona ask")):
        return _resultado(
            "ASK IGNIS es un asistente estadístico basado en reglas de Python y Pandas. "
            "No utiliza GPT, Gemini ni otro modelo generativo. "
            "Analiza únicamente los archivos cargados en esta sesión."
        )
    if any(t in q for t in (
        "incendio confirmado", "incendios confirmados", "fuego confirmado",
        "son incendios", "validar incendio", "verificar incendio",
    )):
        return _resultado(
            "Un punto de calor FIRMS es una observación de anomalía térmica, no la "
            "confirmación de un incendio. Para verificar un episodio hacen falta "
            "fuentes externas, fechas y coordenadas comparables. "
            "Consultá «Alertas y trazabilidad» para revisar documentación."
        )

    if datos is None or datos.empty:
        return _resultado(
            "Todavía no hay registros cargados. Importá un ZIP/CSV NASA FIRMS o un "
            "Maestro IGNIS en «Carga de datos» para realizar consultas estadísticas."
        )

    frame = datos.copy()
    frame["fecha"] = pd.to_datetime(frame["fecha"], errors="coerce", utc=True)
    frame = frame.dropna(subset=["fecha"])
    if frame.empty:
        return _resultado(
            "El archivo no contiene fechas válidas para analizar. Revisá la carga."
        )

    # Esta procedencia indica únicamente el archivo aportado, no una
    # validación independiente de las observaciones o de un incendio.
    fuentes = ["Registros importados en IGNIS (sesión actual)"]
    if "fuente" in frame.columns and frame["fuente"].notna().any():
        fuentes.append("Campo de procedencia «fuente» del archivo cargado")

    if "uruguay" in q or " uy" in " " + q:
        frame = frame[
            frame["latitude"].between(-35.5, -29.7)
            & frame["longitude"].between(-58.8, -52.8)
        ]

    has_modis = "modis" in q
    has_viirs = "viirs" in q
    if has_modis and not has_viirs:
        frame = frame[frame["instrumento"].astype(str).str.contains(
            "MODIS", case=False, na=False
        )]
    elif has_viirs and not has_modis:
        frame = frame[frame["instrumento"].astype(str).str.contains(
            "VIIRS", case=False, na=False
        )]

    if "departamento" in q or any(n in q for n in (
        "durazno", "lavalleja", "artigas", "canelones", "treinta y tres", "cerro del toro"
    )):
        return _resultado(
            "ASK IGNIS aún no puede asignar automáticamente cada detección a un "
            "departamento o caso a partir del texto. Seleccioná la región desde "
            "los filtros de IGNIS para explorar ese recorte. "
            "No se inventan límites administrativos.",
            fuentes=fuentes,
        )

    if (has_modis and has_viirs) or (
        "compar" in q and ("sensor" in q or "instrument" in q)
    ):
        grouped = frame.groupby("instrumento").size().reset_index(name="Observaciones")
        grouped = grouped.rename(columns={"instrumento": "Instrumento"})
        return _resultado(
            "Comparación descriptiva de registros MODIS y VIIRS en el archivo "
            "cargado. Los conteos no están armonizados entre sensores y no "
            "equivalen a incendios únicos.",
            grouped,
            fuentes,
        )

    if "frp" in q or "potencia radiativa" in q or "fire radiative power" in q:
        frp = pd.to_numeric(
            frame.get("frp", pd.Series(index=frame.index, dtype=float)),
            errors="coerce",
        ).dropna()
        if frp.empty:
            return _resultado(
                "No hay valores FRP numéricos disponibles en el recorte cargado.",
                fuentes=fuentes,
            )
        return _resultado(
            f"En {len(frp):,} registros con FRP disponible, el mínimo es "
            f"{frp.min():,.2f} MW, el máximo {frp.max():,.2f} MW y el "
            f"promedio {frp.mean():,.2f} MW. "
            "Estos valores no miden por sí solos superficie quemada.",
            fuentes=fuentes,
        )

    if any(t in q for t in ("este mes", "mes actual", "this month")):
        now = pd.Timestamp.now(tz="UTC")
        frame = frame[
            (frame["fecha"].dt.year == now.year)
            & (frame["fecha"].dt.month == now.month)
        ]
        grouped = frame.groupby(frame["fecha"].dt.day).size().reset_index(
            name="Observaciones"
        )
        grouped.columns = ["Día", "Observaciones"]
        return _resultado(
            f"En {now.strftime('%Y-%m')} hay {len(frame):,} observaciones "
            "en los archivos cargados para el recorte consultado. "
            "Un cero no demuestra ausencia de incendios ni cobertura completa.",
            grouped,
            fuentes,
        )

    if any(t in q for t in ("ultimos cinco", "ultimos 5", "last five years")):
        last = int(frame["fecha"].dt.year.max())
        frame = frame[frame["fecha"].dt.year >= last - 4]
        grouped = frame.groupby(frame["fecha"].dt.year).size().reset_index(
            name="Observaciones"
        )
        grouped.columns = ["Año", "Observaciones"]
        return _resultado(
            f"Actividad de los cinco años hasta {last}, según los años presentes "
            "en el archivo. Son registros observados, no incendios confirmados.",
            grouped,
            fuentes,
        )

    if any(t in q for t in (
        "historico", "historia", "por ano", "periodos", "evolucion anual",
        "historical"
    )):
        grouped = frame.groupby(frame["fecha"].dt.year).size().reset_index(
            name="Observaciones"
        )
        grouped.columns = ["Año", "Observaciones"]
        return _resultado(
            "Serie anual calculada a partir del histórico efectivamente cargado. "
            "La comparación puede verse afectada por diferencias de cobertura y "
            "de sensores entre años.",
            grouped,
            fuentes,
        )

    if any(t in q for t in ("por mes", "por meses", "actividad mensual", "activity by month")):
        grouped = frame.groupby(frame["fecha"].dt.month).size().reset_index(
            name="Observaciones"
        )
        grouped.columns = ["Mes", "Observaciones"]
        return _resultado(
            "Distribución por mes calendario de las observaciones del archivo. "
            "Combina los años cargados y no equivale a una tasa de incendios.",
            grouped,
            fuentes,
        )

    if any(t in q for t in (
        "cuant", "cantidad", "numero", "total", "deteccion", "observacion",
        "hotspot", "punto de calor", "registro", "count"
    )):
        counts = frame.groupby("instrumento").size().reset_index(
            name="Observaciones"
        ).rename(columns={"instrumento": "Instrumento"})
        return _resultado(
            f"El recorte consultado contiene {len(frame):,} registros de "
            "observaciones térmicas cargadas. No son incendios únicos "
            "ni superficie quemada.",
            counts,
            fuentes,
        )

    return _resultado(
        "No reconozco todavía esa consulta. Probá preguntar por el total de "
        "observaciones, la comparación MODIS y VIIRS, la actividad por año o "
        "mes, o los valores FRP. ASK IGNIS no inventa respuestas "
        "cuando la pregunta está fuera de sus reglas.",
        fuentes=fuentes,
    )
