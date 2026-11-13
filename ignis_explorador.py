"""IGNIS UY · Explorador científico V6.

Inspiración funcional: navegación por relato científico, calendarios comparables,
mapa con capas NASA por fecha, inventario de fuentes y exportación reproducible.
No reutiliza código ni activos gráficos de Kiln Watch.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ignis_explorer_data import (
    MESES, calendario_instrumental, comparacion_mensual, crear_exportacion,
    demo_sintetica, normalizar_explorador, resumen_explorador, series_anuales,
)
from ignis_worldview import enlace_worldview

COLOR_MODIS = "#F7A35B"
COLOR_VIIRS = "#49D7E8"
BG = "#061323"
LAYERS = {
    "VIIRS NOAA-20 · anomalías térmicas": "VIIRS_NOAA20_Thermal_Anomalies_375m_All",
    "VIIRS NOAA-21 · anomalías térmicas": "VIIRS_NOAA21_Thermal_Anomalies_375m_All",
    "VIIRS S-NPP · anomalías térmicas": "VIIRS_SNPP_Thermal_Anomalies_375m_All",
    "MODIS Terra/Aqua · anomalías térmicas": "MODIS_Combined_Thermal_Anomalies_All",
}
SOURCES = [
    ("NASA FIRMS", "INTEGRADA", "Anomalías MODIS/VIIRS, CSV/ZIP históricos y consultas NRT", "https://www.earthdata.nasa.gov/data/tools/firms"),
    ("NASA Worldview", "ENLACE INTEGRADO", "Inspección satelital por coordenada y fecha", "https://worldview.earthdata.nasa.gov/"),
    ("NASA GIBS WMS", "CAPAS OPCIONALES", "Visualización directa de anomalías térmicas por día", "https://gibs.earthdata.nasa.gov/"),
    ("Bomberos/PAIF y SINAE/MIRA", "PILOTO", "Cruce espaciotemporal y evidencia documental; validación independiente pendiente", "https://www.gub.uy/sistema-nacional-emergencias/"),
    ("NASA EONET", "PROPUESTA", "Eventos naturales como contexto", "https://eonet.gsfc.nasa.gov/"),
    ("NASA POWER", "PROPUESTA", "Contexto meteorológico; no detector de incendios", "https://power.larc.nasa.gov/"),
]


def _styles():
    st.markdown("""<style>
    .ignis-x-hero{
      border:1px solid #2e5c76;
      border-radius:0;
      background:
       linear-gradient(105deg,rgba(4,16,28,.98),rgba(4,21,37,.86) 64%,rgba(2,34,55,.66)),
       radial-gradient(ellipse at 86% 36%,rgba(36,164,203,.25),transparent 36%);
      padding:clamp(20px,3.4vw,54px) clamp(18px,3vw,46px);
      margin:0 0 16px;
      position:relative;overflow:hidden;
    }
    .ignis-x-hero:before{content:"";position:absolute;right:3%;top:-130px;width:280px;height:280px;
      border:1px solid rgba(87,183,210,.2);border-radius:50%;
      box-shadow:0 0 0 34px rgba(31,132,167,.03),0 0 0 70px rgba(31,132,167,.025)}
    .ignis-x-eyebrow{font-size:.73rem;letter-spacing:.21em;font-weight:800;color:#60d6e8}
    .ignis-x-hero h1{font-size:clamp(2.15rem,4.4vw,4.4rem)!important;line-height:1.02!important;
      margin:.8rem 0 .85rem!important;max-width:840px;color:#f2faff}
    .ignis-x-hero h1 em{font-style:normal;color:#6de2f0}
    .ignis-x-hero p{max-width:740px;color:#bfdae9;line-height:1.7;font-size:1rem}
    .ignis-x-tag{display:inline-block;margin:.9rem .6rem 0 0;padding:.4rem .7rem;
      border:1px solid rgba(81,183,209,.33);background:rgba(11,45,66,.57);
      color:#a6deeb;font-size:.72rem;letter-spacing:.055em}
    .ignis-x-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:0 0 18px}
    .ignis-x-stat{background:#0b2134;border:1px solid #2b5168;padding:20px 16px}
    .ignis-x-stat b{font-size:clamp(1.4rem,2.2vw,2.2rem);color:#f2fbff;display:block;
      line-height:1.1;font-variant-numeric:tabular-nums}
    .ignis-x-stat span{display:block;color:#a5c7d8;font-size:.74rem;line-height:1.4;margin-top:9px}
    .ignis-x-step{padding:20px;border:1px solid #2b4d64;background:#0a1b2b;min-height:142px}
    .ignis-x-step b{color:#b8f3fa;font-size:.85rem}
    .ignis-x-step p{color:#b7cede;font-size:.78rem;margin:.5rem 0 0;line-height:1.5}
    .ignis-x-note{padding:15px 17px;border-left:3px solid #50c4d7;background:#102b3c;
      margin:15px 0 10px;color:#c5e1ed;font-size:.84rem;line-height:1.6}
    .ignis-x-section{letter-spacing:.12em;text-transform:uppercase;color:#7edce8;font-size:.72rem;
      font-weight:800;margin:20px 0 12px}
    @media(max-width:850px){.ignis-x-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
       .ignis-x-stat{padding:14px 12px}.ignis-x-hero{padding:26px 20px}}
    </style>""", unsafe_allow_html=True)


def _hero(resumen: dict, region: str, demo: bool = False):
    rotulo = escape(str(region))
    st.markdown(f"""
    <div class="ignis-x-hero">
      <div class="ignis-x-eyebrow">IGNIS UY / OBSERVATORIO SATELITAL / V6</div>
      <h1>Dos generaciones de sensores.<br><em>Una historia por investigar.</em></h1>
      <p>Explorá observaciones MODIS y VIIRS sobre Uruguay. Compará calendarios, examiná
      anomalías térmicas por fecha y contrastá el contexto visual con NASA.
      Cada cifra conserva su procedencia y sus límites científicos.</p>
      <span class="ignis-x-tag">REGIÓN · {rotulo}</span>
      <span class="ignis-x-tag">{"SIMULACIÓN SINTÉTICA · NO NASA" if demo else "DATOS ORIGINALES · SIN CALIBRAR"}</span>
      <span class="ignis-x-tag">NASA FIRMS / EOSDIS</span>
    </div>
    """, unsafe_allow_html=True)
    pairs = [
        (f"{resumen['observaciones']:,}", "Observaciones válidas cargadas"),
        (str(resumen["anios_con_registros"]), "Años con registros importados"),
        (str(resumen["meses_con_ambas_familias"]), "Meses con ambas familias"),
        (escape(resumen["ultima_observacion_utc"] or "—"), "Última fecha UTC del recorte"),
    ]
    html = '<div class="ignis-x-stats">' + "".join(
        f'<div class="ignis-x-stat"><b>{v}</b><span>{lab}</span></div>'
        for v, lab in pairs
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _fig_calendario(table: pd.DataFrame, familia: str):
    color = COLOR_MODIS if familia == "MODIS" else COLOR_VIIRS
    if table.empty:
        return None
    values = table.to_numpy(dtype=float)
    scale = [[0, "#11263a"], [.16, "#1e4962"], [.5, color], [1, "#f9f4da"]]
    fig = go.Figure(go.Heatmap(
        z=values, x=list(MESES), y=[str(x) for x in table.index],
        zmin=0, zmax=max(float(np.nanmax(values)) if np.isfinite(values).any() else 1, 1),
        colorscale=scale,
        customdata=np.where(np.isnan(values), "Sin datos importados", "Observaciones del archivo"),
        hovertemplate="Año: %{y}<br>Mes: %{x}<br>%{customdata}<br>Recuento: %{z}<extra></extra>",
        hoverongaps=False, xgap=2, ygap=2, showscale=False,
    ))
    fig.update_layout(
        template="plotly_dark",height=max(315, min(850, 28 * len(table) + 88)),
        title=dict(text=f"{familia} · datos importados", font=dict(color=color, size=17), x=.02),
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color="#c7dceb",size=10),
        margin=dict(l=6,r=6,t=50,b=15),
        xaxis=dict(side="top", tickangle=0, fixedrange=True),
        yaxis=dict(autorange="reversed", fixedrange=True, type="category"),
    )
    return fig


def _fig_timeline(datos: pd.DataFrame):
    serie = series_anuales(datos)
    fig = go.Figure()
    for nombre, color in (("MODIS", COLOR_MODIS), ("VIIRS", COLOR_VIIRS)):
        sel = serie[serie.Familia == nombre]
        fig.add_trace(go.Scatter(
            x=sel["Año"], y=sel["Observaciones"],
            mode="lines+markers",name=nombre,
            line=dict(color=color,width=2),marker=dict(size=6),
            hovertemplate="Año %{x}<br>Observaciones importadas %{y}<extra>"+nombre+"</extra>",
        ))
    fig.update_layout(
        template="plotly_dark", height=340,
        paper_bgcolor=BG,plot_bgcolor=BG,
        margin=dict(l=30,r=15,b=25,t=20),
        legend=dict(orientation="h",y=1.08,x=0),
        xaxis=dict(title="Año",dtick=2,gridcolor="#20384b"),
        yaxis=dict(title="Detecciones importadas",gridcolor="#20384b"),
    )
    return fig


def _historia(datos):
    st.markdown('<div class="ignis-x-section">01 / La discontinuidad instrumental</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    steps=[
        ("MODIS", "Registra anomalías térmicas desde comienzos del período histórico disponible."),
        ("VIIRS", "Mayor capacidad de detectar focos pequeños en comparación con MODIS; no sumar series crudas."),
        ("EL DESAFÍO", "Comparar la actividad real requiere cobertura y calibración estadística, aún pendientes en IGNIS."),
    ]
    for col,(name,desc) in zip((c1,c2,c3),steps):
        with col:
            st.markdown(f'<div class="ignis-x-step"><b>{name}</b><p>{desc}</p></div>',unsafe_allow_html=True)
    st.markdown('<div class="ignis-x-section">02 / Calendarios paralelos (mismo territorio)</div>',unsafe_allow_html=True)
    a,b=st.columns(2)
    for family,col in (("MODIS",a),("VIIRS",b)):
        with col:
            fig=_fig_calendario(calendario_instrumental(datos,family),family)
            if fig:st.plotly_chart(fig,use_container_width=True,key=f"ignis_v6_calendar_{family}")
            else:st.info(f"Sin información {family} en el recorte.")
    st.markdown(
        '<div class="ignis-x-note"><b>Lectura correcta:</b> cada celda representa observaciones '
        'contenidas en los archivos cargados. Celdas vacías NO equivalen a cero actividad '
        'ni a cobertura satelital verificada. Los dos calendarios NO están calibrados.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="ignis-x-section">03 / Evolución por familia de instrumento</div>',unsafe_allow_html=True)
    st.plotly_chart(_fig_timeline(datos),use_container_width=True,key="ignis_v6_timeline")
    st.caption("Los saltos en recuentos pueden reflejar cambios instrumentales, disponibilidad y archivos importados, no una tendencia causal de incendios.")


def _mapa_observaciones(datos: pd.DataFrame):
    st.markdown('<div class="ignis-x-section">Explorador de detecciones del Maestro</div>',unsafe_allow_html=True)
    a,b=st.columns([1,1])
    anos=sorted(datos.anio.unique(),reverse=True)
    with a:
        ano=int(st.selectbox("Año UTC",anos,key="ignis_v6_year"))
    subset=datos[datos.anio == ano]
    meses=sorted(subset.mes.unique())
    with b:
        mes=int(st.selectbox("Mes UTC",meses,format_func=lambda m:MESES[int(m)-1],key="ignis_v6_month"))
    sel=subset[subset.mes == mes].copy()
    counts=sel.groupby("familia").size().to_dict()
    x,y,z=st.columns(3)
    x.metric("Detecciones importadas",f"{len(sel):,}")
    y.metric("MODIS",f"{counts.get('MODIS',0):,}")
    z.metric("VIIRS",f"{counts.get('VIIRS',0):,}")

    fig=go.Figure()
    # No ocultar que para velocidad el mapa muestra como máximo 2.400 puntos.
    if len(sel)>2400:
        mostradas=sel.sample(2400,random_state=26)
    else:
        mostradas=sel
    for family,color in (("MODIS",COLOR_MODIS),("VIIRS",COLOR_VIIRS)):
        parte=mostradas[mostradas.familia == family]
        if parte.empty:continue
        fig.add_trace(go.Scattergl(
            x=parte.longitude,y=parte.latitude,mode="markers",name=family,
            marker=dict(size=6,opacity=.72,color=color),
            customdata=parte[["dia_utc","instrumento"]].to_numpy(),
            hovertemplate="%{customdata[0]} UTC<br>%{customdata[1]}<br>Lat %{y:.4f}, Lon %{x:.4f}<extra></extra>",
        ))
    fig.update_layout(
        height=485,template="plotly_dark",paper_bgcolor=BG,plot_bgcolor=BG,
        margin=dict(l=15,r=12,t=25,b=25),
        legend=dict(orientation="h",y=1.07),
        xaxis=dict(title="Longitud",gridcolor="#1c374a",range=[-59,-52]),
        yaxis=dict(title="Latitud",gridcolor="#1c374a",range=[-36,-29.6],scaleanchor="x",scaleratio=1),
    )
    st.plotly_chart(fig,use_container_width=True,key="ignis_v6_explorer_scatter")
    if len(sel)>len(mostradas):st.caption(f"Visualización limitada a {len(mostradas):,} puntos; el CSV mantiene los {len(sel):,} registros.")
    st.markdown("#### Observaciones de ese mes")
    cols=[x for x in ("dia_utc","instrumento","latitude","longitude","frp","fuente") if x in sel.columns]
    st.dataframe(sel[cols].head(600),use_container_width=True,hide_index=True)
    st.download_button(
        "Descargar observaciones del mes CSV",
        sel[[x for x in ("fecha","instrumento","satellite","acq_time","latitude","longitude","frp","confidence","fuente","id_registro") if x in sel.columns]].to_csv(index=False).encode("utf-8-sig"),
        file_name=f"IGNIS_observaciones_{ano}_{mes:02}.csv",mime="text/csv",
        key="ignis_v6_month_download",
    )


def _capas_gibs(datos: pd.DataFrame):
    st.markdown('<div class="ignis-x-section">NASA GIBS / Inspección visual por día</div>',unsafe_allow_html=True)
    st.write(
        "Mapa interactivo con capa de anomalías térmicas de NASA GIBS y observaciones "
        "del Maestro. La capa es externa, opcional y corresponde a la fecha elegida."
    )
    dias=sorted(datos.dia_utc.unique(),reverse=True)
    dia=st.selectbox("Fecha UTC",dias,key="ignis_v6_gibs_date")
    z=datos[datos.dia_utc == dia].copy()
    ubicacion=z.iloc[0]
    # Coherente con los instrumentos del día, pero la capa elegida podría
    # no existir para un período histórico determinado.
    default=next((i for i,k in enumerate(LAYERS) if ("MODIS" in k and (z.familia == "MODIS").any()) or
                  ("NOAA-20" in k and z.instrumento.str.contains("NOAA-20").any())),0)
    layer=st.selectbox("Capa de anomalías térmicas NASA",list(LAYERS),index=default,key="ignis_v6_gibs_layer")
    cargar=st.checkbox(
        "Cargar capa satelital remota NASA GIBS (requiere Internet)",
        value=False,key="ignis_v6_enable_gibs",
    )
    if not cargar:
        st.info("Activá la opción para cargar el mapa NASA GIBS. No se realizan peticiones externas hasta habilitarla.")
    else:
        try:
            import folium
            import streamlit.components.v1 as components
            centro=[float(z.latitude.median()),float(z.longitude.median())]
            mapa=folium.Map(
                location=centro,zoom_start=8,tiles="CartoDB dark_matter",
                control_scale=True,prefer_canvas=True,
            )
            folium.raster_layers.WmsTileLayer(
                url="https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi",
                name=layer,layers=LAYERS[layer],
                fmt="image/png",transparent=True,overlay=True,control=True,
                show=True,version="1.3.0",time=dia,
                attribution="NASA GIBS / EOSDIS",
            ).add_to(mapa)
            muestra=z.sample(min(300,len(z)),random_state=26) if len(z)>300 else z
            for r in muestra.itertuples():
                folium.CircleMarker(
                    location=[float(r.latitude),float(r.longitude)],
                    radius=3,color=(COLOR_MODIS if r.familia=="MODIS" else COLOR_VIIRS),
                    fill=True,fill_opacity=.8,weight=1,
                    tooltip=f"{r.instrumento} · {r.dia_utc} UTC",
                ).add_to(mapa)
            folium.LayerControl(collapsed=False).add_to(mapa)
            components.html(mapa.get_root().render(),height=560,scrolling=False)
            if len(z)>len(muestra):st.caption(f"Mapa limitado a {len(muestra)} puntos para rendimiento; detecciones del día: {len(z)}.")
        except Exception as exc:
            st.warning(f"No se pudo preparar el mapa de contexto: {type(exc).__name__}. Usá Worldview como alternativa.")
    st.caption(
        "Las teselas NASA pueden no estar disponibles en la fecha o capa seleccionada; "
        "la falta de imagen no demuestra ausencia de anomalías. "
        "La superposición no confirma automáticamente incendios."
    )
    try:
        st.link_button(
            "Abrir este día y ubicación en NASA Worldview",
            enlace_worldview(dia,float(ubicacion.latitude),float(ubicacion.longitude),.8),
        )
    except (ValueError,TypeError):
        st.warning("No fue posible preparar el enlace de NASA Worldview.")


def _metodo(datos):
    st.markdown('<div class="ignis-x-section">Cómo se obtienen los números</div>',unsafe_allow_html=True)
    st.markdown(
        "La lógica del explorador es **determinista**: no genera registros, "
        "no interpola meses faltantes y no utiliza inteligencia artificial para calcular resultados."
    )
    steps=[
        ("01 · INGESTA","NASA FIRMS → archivos ZIP/CSV o NRT bajo demanda, claves fuera del repositorio."),
        ("02 · NORMALIZACIÓN","Fecha UTC, posición, familia instrumental, metadatos y deduplicación del Maestro."),
        ("03 · EXPLORACIÓN","Recuentos por mes/año y familia, mapas de observaciones y cruces espaciotemporales exploratorios."),
        ("04 · CONTEXTO","NASA GIBS y Worldview para inspección visual del lugar y fecha, no validación automática."),
        ("05 · VALIDACIÓN FUTURA","Cobertura instrumental verificada, calibración cuantitativa y pruebas fuera de muestra."),
    ]
    for title,desc in steps:
        st.markdown(
            f'<div class="ignis-x-step" style="min-height:0;margin:5px 0"><b>{escape(title)}</b><p>{escape(desc)}</p></div>',
            unsafe_allow_html=True,
        )
    st.markdown("#### Inventario de datos y recursos")
    tabla=pd.DataFrame(SOURCES,columns=["Fuente","Estado","Función","URL"])
    st.dataframe(tabla,use_container_width=True,hide_index=True,
                 column_config={"URL":st.column_config.LinkColumn("Abrir referencia")})
    st.caption(
        "Las fuentes en estado PROPUESTA no alimentan datos del explorador. "
        "Los registros institucionales corresponden a un módulo piloto independiente."
    )
    st.markdown("#### Transparencia de la IA")
    st.info(
        "ASK IGNIS utiliza reglas de Python y Pandas. No es un LLM ni utiliza "
        "Gemini o Claude para generar cifras. Las herramientas de IA usadas durante "
        "el desarrollo se documentarán según las declaraciones verificadas del equipo."
    )
    st.markdown("#### Estado de armonización")
    st.warning(
        "Los calendarios muestran DETECCIONES CRUDAS importadas. "
        "Todavía no se estima cobertura instrumental, no se corrige sensibilidad, "
        "no hay intervalo de incertidumbre calibrado y no se publica un índice "
        "armonizado comparable como el que propone Kiln Watch."
    )
    st.markdown(
        "[Metodología detallada](https://github.com/sarapcoffee/ignis-uy-historico/blob/main/docs/METODO_CIENTIFICO.md)"
        " · [Fuentes](https://github.com/sarapcoffee/ignis-uy-historico/blob/main/docs/FUENTES_DATOS.md)"
        " · [Uso de IA](https://github.com/sarapcoffee/ignis-uy-historico/blob/main/docs/USO_DE_IA.md)"
    )


def _exportar(datos,region,sensores,demo=False):
    st.markdown('<div class="ignis-x-section">Exportación reproducible / Ciencia abierta</div>',unsafe_allow_html=True)
    st.write(
        "Prepará un paquete descargable con las observaciones del recorte, "
        "resumen por mes, filtros seleccionados, fecha UTC de exportación, "
        "advertencias metodológicas y hashes SHA-256 de los CSV."
    )
    st.download_button(
        "Descargar conjunto de investigación ZIP",
        crear_exportacion(datos,region,list(sensores),demo=demo),
        file_name=("IGNIS_V6_DEMO_SINTETICA.zip" if demo else "IGNIS_UY_Explorador_V6_Investigacion.zip"),
        mime="application/zip",type="primary",
        key="ignis_v6_research_zip",
    )
    st.caption(
        "La exportación conserva los registros originales normalizados y sus fuentes "
        "si están en el Maestro. No contiene datos calibrados ni confirma incendios."
    )
    st.dataframe(comparacion_mensual(datos),use_container_width=True,hide_index=True)


def mostrar_explorador(datos: pd.DataFrame | None, region: str, sensores: list[str]):
    _styles()
    z = normalizar_explorador(datos)
    demo = False
    if z.empty:
        st.info(
            "Todavía no hay registros cargados en el Maestro IGNIS. "
            "Podés importar datos reales o explorar una demostración sintética "
            "sin guardar nada en el histórico."
        )
        demo = st.checkbox(
            "Explorar demostración 100 % sintética (no son observaciones de NASA)",
            value=False, key="ignis_v6_demo_activa",
        )
        if demo:
            z = normalizar_explorador(demo_sintetica())
        else:
            _hero(resumen_explorador(z),region)
            return
    _hero(resumen_explorador(z),region,demo=demo)
    if demo:
        st.error(
            "MODO DE DEMOSTRACIÓN: TODOS los puntos, fechas y recuentos de esta "
            "vista son sintéticos. No proceden de NASA FIRMS y no representan "
            "incendios ni anomalías reales. No se agregan al Maestro."
        )
    else:
        st.markdown(
            '<div class="ignis-x-note"><b>Distinción científica:</b> IGNIS muestra registros '
            'NASA FIRMS que efectivamente fueron importados. La ausencia de filas '
            'no garantiza cobertura satelital ni ausencia de fuego; los sensores '
            'todavía no están armonizados cuantitativamente.</div>',
            unsafe_allow_html=True,
        )
    tabs=st.tabs([
        "01 · Historia", "02 · Explorador", "03 · NASA GIBS",
        "04 · Método y fuentes", "05 · Descargar",
    ])
    with tabs[0]:
        _historia(z)
    with tabs[1]:
        _mapa_observaciones(z)
    with tabs[2]:
        if demo:
            st.warning(
                "El mapa de NASA GIBS se desactiva en modo sintético para evitar "
                "asociar registros ficticios a imágenes satelitales reales. "
                "Cargá registros FIRMS auténticos para usarlo."
            )
            st.link_button("Explorar NASA Worldview directamente","https://worldview.earthdata.nasa.gov/")
        else:
            _capas_gibs(z)
    with tabs[3]:
        _metodo(z)
    with tabs[4]:
        _exportar(z,region,sensores,demo=demo)
