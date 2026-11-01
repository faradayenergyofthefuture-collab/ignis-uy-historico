"""IGNIS UY — piloto histórico, independiente de la versión 1.7.
Lee archivos NASA FIRMS CSV/ZIP cargados explícitamente por el usuario.
No incorpora ni presume datos históricos no suministrados.
"""
import io
import zipfile
import hashlib
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

st.set_page_config(page_title="IGNIS UY | Histórico piloto", page_icon="🛰️", layout="wide")
st.title("🛰️ IGNIS UY — Histórico de actividad térmica")
st.caption("Piloto independiente · datos NASA FIRMS cargados por el equipo · no reemplaza IGNIS UY 1.7")
st.info("Los registros representan anomalías térmicas observadas, no incendios confirmados. Los mapas muestran detecciones, no superficies quemadas.")

REGIONES = {
    "Uruguay (rectángulo aproximado)": (-35.2, -30.0, -58.6, -53.0),
    "Durazno (caso 2023)": (-33.460, -33.280, -56.750, -56.440),
    "Cerro del Toro (Maldonado)": (-34.880, -34.840, -55.280, -55.230),
    "Treinta y Tres (caso 2023)": (-32.985, -32.879, -54.069, -53.920),
    "Canelones (zona de Atlántida)": (-34.788, -34.724, -55.890, -55.810),
    "Lavalleja (caso 2023)": (-34.116, -34.044, -54.940, -54.842),
    "Artigas (caso 2023)": (-30.505, -30.443, -56.576, -56.499),
}

def sensor_de(df, nombre):
    sat = df.get("satellite", pd.Series("", index=df.index)).astype(str).str.upper()
    ins = df.get("instrument", pd.Series("", index=df.index)).astype(str).str.upper()
    n = nombre.lower()
    if ins.eq("MODIS").all() or "m-c61" in n or "modis" in n:
        return "MODIS"
    if ins.eq("VIIRS").all() or "viirs" in n or "j1v" in n or "sv-c2" in n:
        if sat.isin(["N20", "NOAA-20", "J1"]).all() or "j1v" in n or "noaa20" in n:
            return "VIIRS NOAA-20"
        if sat.isin(["SNPP", "S-NPP", "NPP"]).all() or "sv-c2" in n or "snpp" in n:
            return "VIIRS S-NPP"
    return "Sin identificar"

@st.cache_data(show_spinner=False)
def analizar_bytes(contenido, nombre_archivo):
    """Carga un archivo o varios CSV internos, sin confiar en el nombre del ZIP."""
    if nombre_archivo.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            tablas = [(n, z.read(n)) for n in z.namelist() if n.lower().endswith(".csv") and not n.startswith("__MACOSX/")]
    else:
        tablas = [(nombre_archivo, contenido)]
    resultados, problemas = [], []
    for nombre, raw in tablas:
        try:
            df = pd.read_csv(io.BytesIO(raw), low_memory=False)
            req = {"latitude", "longitude", "acq_date"}
            if not req.issubset(df.columns):
                problemas.append(f"{nombre}: faltan {sorted(req-set(df.columns))}")
                continue
            sensor = sensor_de(df, nombre)
            if sensor == "Sin identificar":
                problemas.append(f"{nombre}: no se identifica instrumento, omitido")
                continue
            df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
            df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
            df["fecha"] = pd.to_datetime(df["acq_date"], errors="coerce", utc=True)
            df = df.dropna(subset=["latitude", "longitude", "fecha"]).copy()
            df = df.loc[df.latitude.between(-90, 90) & df.longitude.between(-180, 180)]
            df["instrumento"] = sensor
            df["fuente"] = f"{nombre_archivo} :: {nombre}"
            df["archivo_hash"] = hashlib.sha256(raw).hexdigest()[:16]
            # Preserve all original fields for exports but normalize the key fields.
            resultados.append(df)
        except Exception as exc:
            problemas.append(f"{nombre}: error de lectura {exc}")
    return resultados, problemas

st.subheader("1 · Carga documentada")
st.write("Subí ZIP o CSV de NASA FIRMS. Podés cargar archivos del 2000 sin VIIRS; no es un error. Los archivos no se recuperan automáticamente de tu computadora ni de NASA.")
archivos = st.file_uploader("Archivos NASA FIRMS (selección múltiple)", type=["zip","csv"], accept_multiple_files=True)
if not archivos:
    st.info("Cargá uno o varios archivos para habilitar los gráficos. Empezá por 2000 y añadí otros años progresivamente.")
    st.stop()

partes, advertencias, inventario = [], [], []
for a in archivos:
    contenido = a.getvalue()
    tablas, errs = analizar_bytes(contenido, a.name)
    advertencias.extend(errs)
    for t in tablas:
        partes.append(t)
        inventario.append({"Archivo":a.name,"Instrumento":t.instrumento.iloc[0] if len(t) else "—", "Registros válidos":len(t), "Fecha mínima":str(t.fecha.min().date()) if len(t) else "—", "Fecha máxima":str(t.fecha.max().date()) if len(t) else "—", "CSV hash":t.archivo_hash.iloc[0] if len(t) else "—"})
for msg in advertencias:
    st.warning(msg)
if not partes:
    st.error("No se encontraron registros válidos.")
    st.stop()
datos = pd.concat(partes, ignore_index=True)
# Drop exact repeated observations (e.g. same archive loaded twice). Distinct sensors are retained.
identidad = [c for c in ["instrumento","satellite","latitude","longitude","acq_date","acq_time","brightness","bright_ti4","bright_ti5"] if c in datos.columns]
antes = len(datos)
datos = datos.drop_duplicates(subset=identidad).copy()
eliminados = antes-len(datos)
if eliminados:
    st.warning(f"Se omitieron {eliminados} registros repetidos exactos según campos satelitales comunes. Verificá si las extracciones FIRMS se solapan.")
st.dataframe(pd.DataFrame(inventario), use_container_width=True, hide_index=True)
st.caption("El inventario muestra los archivos realmente cargados. No representa cobertura histórica completa ni oportunidades de observación.")

st.subheader("2 · Selección de zona y serie")
zona = st.selectbox("Región / recorte", list(REGIONES))
la0,la1,lo0,lo1 = REGIONES[zona]
if zona == "Uruguay (rectángulo aproximado)":
    st.caption("Atención: el rectángulo puede incluir puntos fuera de Uruguay. No se usa un límite administrativo exacto.")
else:
    st.caption("Los seis recortes proceden de la guía cartográfica de 2023; no representan límites departamentales certificados.")
subset = datos.loc[datos.latitude.between(la0,la1) & datos.longitude.between(lo0,lo1)].copy()
subset["anio"] = subset.fecha.dt.year
subset["mes"] = subset.fecha.dt.month
subset["dia"] = subset.fecha.dt.date
sensor_sel = st.multiselect("Instrumentos a visualizar", sorted(datos.instrumento.unique()), default=sorted(datos.instrumento.unique()))
subset = subset[subset.instrumento.isin(sensor_sel)]
if not subset.empty:
    anios = sorted(subset.anio.unique().tolist())
    seleccionado = st.selectbox("Año que querés estudiar", anios, index=len(anios)-1)
else:
    seleccionado = None
c1,c2,c3 = st.columns(3)
c1.metric("Registros en la región (archivos cargados)", f"{len(subset):,}".replace(",","."))
c2.metric("Años con registros cargados", subset.anio.nunique() if len(subset) else 0)
c3.metric("Instrumentos con registros", subset.instrumento.nunique() if len(subset) else 0)
if subset.empty:
    st.warning("No hay registros en el recorte. Probá la vista nacional. Cero registros cargados no equivale a ausencia de fuego.")
    st.stop()

st.subheader("3 · Calendario histórico por mes (años con datos cargados)")
mensual = subset.groupby(["anio","mes","instrumento"]).size().reset_index(name="detecciones")
st.caption("Se muestran SOLO los meses presentes en los archivos; los meses no cargados se marcan sin datos (gris), no con cero. Los recuentos de sensores distintos NO son directamente comparables.")
for inst in sorted(subset.instrumento.unique()):
    mm = mensual[mensual.instrumento==inst]
    tabla = mm.pivot_table(index="mes", columns="anio", values="detecciones", aggfunc="sum")
    tabla = tabla.reindex(index=range(1,13), columns=range(2000,2027))
    fig,ax = plt.subplots(figsize=(15,4.3))
    fig.patch.set_facecolor("white")
    masked = np.ma.masked_invalid(tabla.to_numpy(dtype=float))
    cmap = plt.get_cmap("magma").copy()
    cmap.set_bad("#dddddd")
    im=ax.imshow(masked, aspect="auto", cmap=cmap)
    ax.set_yticks(range(12), ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Set","Oct","Nov","Dic"])
    ax.set_xticks(range(27), list(range(2000,2027)), rotation=90, fontsize=7)
    ax.set_title(f"{inst} · detecciones registradas (gris: sin registros cargados; no equivale a cobertura ausente)")
    fig.colorbar(im, ax=ax, label="Recuentos de detecciones", fraction=.025, pad=.02)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

st.subheader("4 · Serie anual y año seleccionado")
serie = subset.groupby(["anio","instrumento"]).size().unstack(fill_value=0).reindex(range(2000,2027))
st.line_chart(serie)
st.caption("Las líneas solo describen los archivos aportados; un año incompleto no puede compararse con uno completo. El año 2000 puede comenzar en noviembre y 2026 puede incluir solo enero-febrero.")
if seleccionado is not None:
    year_df = subset[subset.anio==seleccionado]
    meses = year_df.groupby(["mes","instrumento"]).size().unstack(fill_value=0).reindex(range(1,13))
    st.write(f"**Año seleccionado: {seleccionado}** · {len(year_df)} detecciones térmicas en los archivos cargados")
    st.bar_chart(meses)
    st.dataframe(year_df.groupby(["dia","instrumento"]).size().reset_index(name="detecciones"), use_container_width=True, hide_index=True)

st.subheader("5 · Mapa de densidad de puntos térmicos")
st.caption("Densidad visual de detecciones, NO número de incendios. El sesgo por cobertura de sensores y años no está normalizado.")
map_df = subset if seleccionado is None else subset[subset.anio==seleccionado]
if len(map_df):
    mapa=folium.Map(location=[-32.9,-56.0], zoom_start=7, tiles="CartoDB positron")
    # capped rendering for browser performance; source counts remain complete.
    puntos=map_df[["latitude","longitude"]].dropna()
    if len(puntos)>15000:
        puntos=puntos.sample(15000, random_state=42)
        st.caption("Vista cartográfica limitada a una muestra reproducible de 15.000 puntos para rendimiento.")
    HeatMap(puntos.to_numpy().tolist(), radius=12, blur=16).add_to(mapa)
    st_folium(mapa, height=530, width=None, returned_objects=[])
else:
    st.info("No hay puntos para mapear en este año.")

st.subheader("6 · Trazabilidad y descarga")
st.warning("El piloto no dispone de evidencia independiente para confirmar incendios, alertas validadas ni máximos históricos nacionales. Los expedientes periodísticos de 2023 permanecen en la aplicación original IGNIS UY 1.7.")
exportar = subset[["fecha","latitude","longitude","instrumento","fuente","anio","mes"]].copy()
exportar["fecha"] = exportar["fecha"].astype(str)
st.download_button("Descargar observaciones filtradas (CSV)", exportar.to_csv(index=False).encode("utf-8-sig"), file_name="ignis_historico_observaciones.csv", mime="text/csv")
st.download_button("Descargar resumen mensual (CSV)", mensual.to_csv(index=False).encode("utf-8-sig"), file_name="ignis_historico_mensual.csv", mime="text/csv")
st.caption("PRÓXIMA VALIDACIÓN: inventario de cobertura por año/instrumento, verificación de archivos, polígono oficial de Uruguay, normalización por oportunidades de observación y contraste con registros independientes.")
