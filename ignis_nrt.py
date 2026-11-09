"""IGNIS UY: consulta opcional y liviana de detecciones recientes NASA FIRMS.

NO altera ni importa al Maestro IGNIS. Las detecciones no confirman incendios.
La consulta de red ocurre EXCLUSIVAMENTE al pulsar el botón del formulario.
"""

from __future__ import annotations

import io
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

FUENTES = {
    "VIIRS NOAA-20": "VIIRS_NOAA20_NRT",
    "VIIRS NOAA-21": "VIIRS_NOAA21_NRT",
    "MODIS Terra/Aqua": "MODIS_NRT",
}
# Misma caja geográfica aproximada usada en el dashboard histórico.
BBOX_URUGUAY = "-58.6,-35.2,-53.0,-30.0"  # oeste,sur,este,norte
LIMITE_BYTES = 4_000_000


def _clave_nasa():
    """La clave se obtiene del gestor seguro de Streamlit; nunca del repositorio.

    Acepta ambos nombres para mantener compatibilidad con la configuración
    existente del resto del dashboard (FIRMS_MAP_KEY) y con la nueva API NRT.
    """
    for nombre in ("NASA_FIRMS_MAP_KEY", "FIRMS_MAP_KEY"):
        try:
            clave = str(st.secrets.get(nombre, "")).strip()
            if clave:
                return clave
        except Exception:
            pass
    for nombre in ("NASA_FIRMS_MAP_KEY", "FIRMS_MAP_KEY"):
        clave = os.environ.get(nombre, "").strip()
        if clave:
            return clave
    return ""


@st.cache_data(ttl=900, max_entries=16, show_spinner=False)
def _pedir_sensor(clave: str, producto: str, dias: int):
    """Una sola descarga por sensor, como máximo una vez cada 15 min por caché.

    No se devuelve la URL en excepciones: contiene la clave privada MAP_KEY.
    """
    url = ("https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
           f"{clave}/{producto}/{BBOX_URUGUAY}/{dias}")
    request = Request(url, headers={"User-Agent": "IGNIS-UY/1.0 (NASA FIRMS research prototype)"})
    try:
        with urlopen(request, timeout=12) as respuesta:
            contenido = respuesta.read(LIMITE_BYTES + 1)
            if len(contenido) > LIMITE_BYTES:
                return pd.DataFrame(), "Respuesta demasiado grande para el modo liviano"
    except HTTPError as error:
        return pd.DataFrame(), f"NASA FIRMS respondió HTTP {error.code}"
    except (URLError, TimeoutError, OSError):
        return pd.DataFrame(), "No se pudo establecer comunicación con NASA FIRMS"
    try:
        dataframe = pd.read_csv(io.BytesIO(contenido), low_memory=False)
        dataframe.columns = [str(col).strip().lower() for col in dataframe.columns]
        requeridas = {"latitude", "longitude", "acq_date", "acq_time"}
        if not requeridas.issubset(dataframe):
            return pd.DataFrame(), "Formato de respuesta inesperado"
        dataframe["latitude"] = pd.to_numeric(dataframe["latitude"], errors="coerce")
        dataframe["longitude"] = pd.to_numeric(dataframe["longitude"], errors="coerce")
        dataframe = dataframe.dropna(subset=["latitude", "longitude"]).copy()
        dataframe = dataframe[
            dataframe.latitude.between(-35.2, -30.0)
            & dataframe.longitude.between(-58.6, -53.0)
        ].copy()
        # acq_time FIRMS se expresa HHMM en UTC.
        hora = (dataframe["acq_time"].astype(str).str.replace(r"\.0$", "", regex=True)
                .str.zfill(4).str.slice(0, 2) + ":" +
                dataframe["acq_time"].astype(str).str.replace(r"\.0$", "", regex=True)
                .str.zfill(4).str.slice(2, 4))
        dataframe["adquisicion_utc"] = pd.to_datetime(
            dataframe["acq_date"].astype(str) + " " + hora,
            utc=True, errors="coerce"
        )
        dataframe["frp"] = pd.to_numeric(dataframe.get("frp", pd.Series(index=dataframe.index, dtype=float)), errors="coerce")
        dataframe["producto"] = next((nombre for nombre, codigo in FUENTES.items() if codigo == producto), producto)
        columnas = ["producto", "adquisicion_utc", "latitude", "longitude", "frp"]
        for adicional in ("confidence", "daynight", "satellite"):
            if adicional in dataframe:
                columnas.append(adicional)
        return dataframe[columnas].copy(), None
    except (ValueError, TypeError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return pd.DataFrame(), "NASA respondió datos que no pudieron interpretarse"


def _consulta(clave: str, fuentes: list[str], dias: int):
    """Dos o tres peticiones acotadas; no descarga todo el planeta."""
    tablas, incidencias = [], []
    with ThreadPoolExecutor(max_workers=min(3, len(fuentes))) as ejecutor:
        trabajos = {ejecutor.submit(_pedir_sensor, clave, FUENTES[nombre], dias): nombre for nombre in fuentes}
        for trabajo in as_completed(trabajos):
            nombre = trabajos[trabajo]
            try:
                df, error = trabajo.result()
            except Exception:
                df, error = pd.DataFrame(), "Error inesperado durante la consulta"
            if error:
                incidencias.append(f"{nombre}: {error}")
            elif not df.empty:
                tablas.append(df)
    if tablas:
        combinado = pd.concat(tablas, ignore_index=True, sort=False)
        combinado = combinado.sort_values("adquisicion_utc", ascending=False).reset_index(drop=True)
    else:
        combinado = pd.DataFrame()
    return combinado, incidencias


def _mapa_liviano(df: pd.DataFrame):
    """Gráfico liviano y sin teselas de terceros, con contorno existente de Uruguay."""
    figura = go.Figure()
    geojson = Path(__file__).resolve().parent / "uruguay_contorno.geojson"
    if geojson.exists():
        try:
            objeto = json.loads(geojson.read_text(encoding="utf-8"))
            geometria = objeto["features"][0]["geometry"]
            anillo = (geometria["coordinates"][0] if geometria["type"] == "Polygon"
                      else geometria["coordinates"][0][0])
            figura.add_trace(go.Scatter(
                x=[p[0] for p in anillo], y=[p[1] for p in anillo],
                fill="toself", fillcolor="rgba(52,38,105,0.4)",
                line=dict(color="#9bc7ff", width=2), name="Uruguay (aprox.)",
                hoverinfo="skip"
            ))
        except (ValueError, KeyError, IndexError, TypeError):
            pass
    colores = {"VIIRS NOAA-20": "#5de1ff", "VIIRS NOAA-21": "#ffc668", "MODIS Terra/Aqua": "#d2a4ff"}
    for nombre, subconjunto in df.groupby("producto", sort=True):
        muestra = subconjunto.iloc[:1200]  # límite visual: nunca exceder 3600 puntos
        figura.add_trace(go.Scattergl(
            x=muestra["longitude"], y=muestra["latitude"],
            mode="markers", name=nombre,
            marker=dict(size=8, opacity=0.8, color=colores.get(nombre, "#ddd")),
            customdata=muestra["adquisicion_utc"].dt.strftime("%Y-%m-%d %H:%M UTC").fillna("Sin hora"),
            hovertemplate="%{customdata}<br>Latitud: %{y:.4f}<br>Longitud: %{x:.4f}<extra>"+nombre+"</extra>"
        ))
    figura.update_layout(
        height=460, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0b1230", margin=dict(l=12, r=12, t=20, b=15),
        legend=dict(orientation="h", y=1.05, x=0),
        xaxis=dict(title="Longitud", range=[-58.9, -52.8], gridcolor="rgba(170,190,235,.15)"),
        yaxis=dict(title="Latitud", range=[-35.5, -29.75], scaleanchor="x", scaleratio=1,
                   gridcolor="rgba(170,190,235,.15)")
    )
    st.plotly_chart(figura, use_container_width=True)


def mostrar_monitoreo_nrt():
    st.subheader("🛰️ Monitoreo satelital reciente · NASA FIRMS")
    st.caption("Consulta bajo demanda. Este módulo NO modifica los datos históricos ni el Maestro IGNIS.")
    st.info("NASA publica anomalías térmicas con cierta demora; no es una transmisión satelital continua ni un sistema de emergencia.")
    clave = _clave_nasa()
    if not clave:
        st.warning("Para activar las consultas, configurá NASA_FIRMS_MAP_KEY o FIRMS_MAP_KEY en los Secrets de la aplicación Streamlit (no en GitHub).")
        st.markdown("Solicitar clave gratuita: https://firms.modaps.eosdis.nasa.gov/api/map_key/")

    with st.form("ignis_nrt_consulta_form"):
        a, b = st.columns([2, 1])
        with a:
            seleccion = st.multiselect(
                "Satélites a consultar", list(FUENTES),
                default=["VIIRS NOAA-20", "VIIRS NOAA-21"],
                help="Cada fuente es un producto separado; no se suman como incendios."
            )
        with b:
            dias = st.selectbox("Período reciente (UTC)", [1, 2, 3], index=1,
                                 format_func=lambda x: f"Últimos {x} día(s) calendario")
        enviar = st.form_submit_button("🔎 Consultar NASA FIRMS", disabled=(not clave or not seleccion), type="primary")

    if enviar:
        with st.spinner("Consultando fuentes recientes de NASA FIRMS..."):
            datos, incidencias = _consulta(clave, seleccion, dias)
        st.session_state["ignis_nrt_ultimo"] = {
            "datos": datos, "incidencias": incidencias, "fuentes": seleccion,
            "dias": dias, "fecha_consulta": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        }
    estado = st.session_state.get("ignis_nrt_ultimo")
    if estado is None:
        st.caption("Sin consultas realizadas en esta sesión. La plataforma histórica funciona normalmente.")
        return

    st.caption(f"Consulta solicitada: {estado['fecha_consulta']} · Fuentes: {', '.join(estado['fuentes'])} · Ventana: {estado['dias']} día(s) UTC. Caché de 15 minutos.")
    for incidencia in estado["incidencias"]:
        st.warning(incidencia)
    datos = estado["datos"]
    if datos.empty:
        st.info("No hay detecciones en las respuestas consultadas para el recorte de Uruguay, o las fuentes no pudieron responder. Esto NO demuestra ausencia de incendios.")
        return

    x, y, z = st.columns(3)
    x.metric("Observaciones recientes disponibles", f"{len(datos):,}")
    y.metric("Fuentes con detecciones", datos["producto"].nunique())
    z.metric("Última adquisición disponible (UTC)",
             datos["adquisicion_utc"].max().strftime("%d/%m %H:%M") if datos["adquisicion_utc"].notna().any() else "Sin hora")
    st.markdown("#### Ubicación de las detecciones recibidas")
    _mapa_liviano(datos)
    st.caption("Recorte aproximado rectangular: puede incluir áreas fuera de Uruguay. Puntos limitados a 1200 por fuente en el mapa; la tabla y el CSV conservan todos los registros devueltos.")
    st.markdown("#### Detecciones por fuente (no incendios únicos)")
    recuentos = datos.groupby("producto").size().reset_index(name="observaciones")
    st.dataframe(recuentos, use_container_width=True, hide_index=True)
    st.markdown("#### Registros recientes")
    tabla = datos.head(400).copy()
    tabla["adquisicion_utc"] = tabla["adquisicion_utc"].dt.strftime("%Y-%m-%d %H:%M UTC")
    st.dataframe(tabla, use_container_width=True, hide_index=True, height=260)
    exportar = datos.copy()
    exportar["adquisicion_utc"] = exportar["adquisicion_utc"].dt.strftime("%Y-%m-%d %H:%M UTC")
    st.download_button("⬇️ Descargar consulta reciente CSV", exportar.to_csv(index=False).encode("utf-8-sig"),
                       file_name="IGNIS_FIRMS_consulta_reciente.csv", mime="text/csv")
    st.warning("Detección térmica ≠ incendio confirmado. No inferir superficie quemada, severidad, cobertura completa ni cantidad de incendios sumando sensores. Para emergencias se deben usar canales oficiales.")
