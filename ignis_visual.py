"""Componentes de presentación de IGNIS UY.

Solo cambia la UI. No altera importación de datos, armonización,
correspondencia de observaciones ni métricas científicas.
"""
import json
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def apply_visual_theme():
    st.markdown("""<style>
    .stApp {background:linear-gradient(155deg,#091324 0%,#070e1b 70%,#06101d 100%)!important}
    .block-container {max-width:1700px;padding-top:1.5rem;padding-bottom:3rem}
    section[data-testid="stSidebar"] {background:#0c1d32!important;border-right:1px solid #284963}
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
      display:flex;align-items:center;width:100%;box-sizing:border-box;
      padding:.48rem .65rem;margin:2px 0;border-radius:10px;
      border:1px solid transparent;background:transparent;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
      border-color:#42b7d0;background:rgba(33,143,177,.19)
    }
    [data-testid="stMetric"] {
      background:linear-gradient(125deg,#14283f,#0d2036)!important;
      border:1px solid #355976!important;border-radius:16px!important;
      padding:18px!important;min-height:104px
    }
    [data-testid="stMetricValue"]{color:#f0faff!important}
    .stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{
      background:linear-gradient(95deg,#087eb8,#125fc5)!important;
      border:1px solid #2689db!important;color:white!important
    }
    .ignis-ui-kicker{font-size:.74rem;font-weight:800;letter-spacing:.15em;
      text-transform:uppercase;color:#67ddef;margin-bottom:.65rem}
    .ignis-ui-header{margin:0 0 1.1rem}
    .ignis-ui-header h1{font-size:clamp(1.8rem,3vw,2.55rem)!important;
      margin:.15rem 0 .45rem;line-height:1.2}
    .ignis-ui-header p{color:#b8d2e2;margin:0;line-height:1.6}
    .ignis-ui-topbar{display:flex;align-items:center;justify-content:space-between;
      gap:15px;flex-wrap:wrap;padding:.75rem 1.15rem;margin:0 0 1rem;
      border:1px solid #315672;border-radius:16px;background:rgba(7,19,34,.94)}
    .ignis-ui-wordmark{display:flex;align-items:center;gap:12px;
      font-size:1.15rem;font-weight:850;color:#f5faff}
    .ignis-ui-wordmark img{width:43px;height:43px;object-fit:contain;border-radius:9px}
    .ignis-ui-wordmark small{display:block;color:#a7c6d8;font-size:.75rem;font-weight:500}
    .ignis-ui-links{display:flex;flex-wrap:wrap;gap:8px}
    .ignis-ui-links a{color:#d3ecff;text-decoration:none;border:1px solid #38617a;
      border-radius:10px;padding:9px 13px;font-size:.84rem;font-weight:650}
    .ignis-ui-links a:hover{background:#163958;border-color:#62d5eb}
    .ignis-ui-hero{
      border:1px solid #44718f;border-radius:22px;
      min-height:370px;background-color:#0e294b;
      background-size:cover;background-position:center right;
      display:flex;flex-direction:column;justify-content:center;
      padding:clamp(24px,5vw,60px);margin-bottom:1rem;
      box-shadow:0 20px 45px rgba(0,0,0,.24)
    }
    .ignis-ui-hero h1{font-size:clamp(2.6rem,5.8vw,5rem)!important;
      line-height:1.02;margin:.15rem 0 1rem;color:#fff!important}
    .ignis-ui-hero h1 span{color:#6ad3ff}
    .ignis-ui-hero p{font-size:1.02rem;line-height:1.65;
      color:#d6e7f5;max-width:590px;margin:0}
    .ignis-ui-hero-facts{display:flex;flex-wrap:wrap;gap:12px;
      margin-top:1.6rem;font-size:.82rem;color:#bddbea}
    .ignis-ui-hero-facts span{padding:.55rem .85rem;border-radius:10px;
      background:rgba(8,24,43,.70);border:1px solid rgba(114,180,209,.28)}
    .ignis-ui-card{background:#10263c;border:1px solid #2a5069;
      border-radius:15px;padding:18px;min-height:142px;margin-bottom:10px}
    .ignis-ui-card b{font-size:1.02rem;color:#e9f8ff}
    .ignis-ui-card p{color:#bcd5e3;margin:.55rem 0 0;line-height:1.55}
    .ignis-ui-subtitle{color:#a9c9dc;font-size:.9rem}
    .ignis-ui-bar{height:2px;background:linear-gradient(90deg,#37c4db,transparent);
      margin:.6rem 0 1.25rem}
    @media(max-width:850px){
      .ignis-ui-hero{min-height:300px;background-position:66% center}
      .ignis-ui-links a{padding:7px 9px;font-size:.76rem}
      .ignis-ui-hero-facts{gap:6px}
      .block-container{padding-left:.85rem;padding-right:.85rem}
    }
    </style>""",unsafe_allow_html=True)


def _header(kicker, title, subtitle):
    st.markdown(
        '<div class="ignis-ui-header">'
        f'<div class="ignis-ui-kicker">{escape(kicker)}</div>'
        f'<h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>'
        '<div class="ignis-ui-bar"></div>',
        unsafe_allow_html=True,
    )


def _empty_uruguay_outline(base, key):
    file = Path(base) / "uruguay_contorno.geojson"
    if not file.exists():
        st.info("El contorno de Uruguay no está disponible en este despliegue.")
        return
    geometry = json.loads(file.read_text(encoding="utf-8"))["features"][0]["geometry"]
    coords = geometry["coordinates"] if geometry["type"] == "Polygon" else geometry["coordinates"][0]
    ring = coords[0]
    fig = go.Figure(go.Scatter(
        x=[p[0] for p in ring],y=[p[1] for p in ring],
        mode="lines",fill="toself",fillcolor="rgba(15,138,169,.20)",
        line=dict(color="#49cfe4",width=3),hoverinfo="skip",
    ))
    fig.update_layout(height=510,showlegend=False,
        margin=dict(l=12,r=12,t=12,b=12),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#0b1c30",
        xaxis=dict(visible=False,scaleanchor="y"),
        yaxis=dict(visible=False))
    st.plotly_chart(fig,use_container_width=True,key=key)


def render_project_home(base, asset_uri, pages, navigate):
    logo = Path(base) / "logo_ignis.png"
    logo_markup = (f'<img src="{asset_uri(logo)}" alt="Logo IGNIS UY">'
                   if logo.exists() else "🛰️")
    st.markdown(
        '<div class="ignis-ui-topbar"><div class="ignis-ui-wordmark">'
        f'{logo_markup}<div>IGNIS UY<small>Histórico · Uruguay</small></div></div>'
        '<div class="ignis-ui-links">'
        '<a href="https://ema.fau.mil.uy/" target="_blank" rel="noopener noreferrer">EMA ↗</a>'
        '<a href="https://www.spaceappschallenge.org/2026/" target="_blank" '
        'rel="noopener noreferrer">NASA Space Apps ↗</a></div></div>',
        unsafe_allow_html=True,
    )
    image = Path(base) / "hero_espacio.jpg"
    url = asset_uri(image, "image/jpeg") if image.exists() else ""
    background = (
        "background-image:linear-gradient(92deg,rgba(5,13,29,.98) 0%,"
        "rgba(5,18,39,.92) 39%,rgba(6,19,43,.35) 100%),"
        f"url('{url}');"
        if url else ""
    )
    st.markdown(
        f'<div class="ignis-ui-hero" style="{background}">'
        '<div class="ignis-ui-kicker">Análisis satelital de actividad térmica en Uruguay</div>'
        '<h1>IGNIS UY<br><span>Histórico</span></h1>'
        '<p>Explorá observaciones NASA FIRMS de los sensores MODIS y VIIRS, '
        'compará períodos históricos y consultá evidencia documental para '
        'interpretar la actividad térmica del territorio uruguayo.</p>'
        '<div class="ignis-ui-hero-facts">'
        '<span>🛰️ MODIS + VIIRS</span>'
        '<span>🗓️ Estudio histórico 2000–2026</span>'
        '<span>🧭 Enfoque geoespacial</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    c1,c2,c3=st.columns([1.25,1,1],gap="medium")
    with c1:
        st.button("📚 Explorar histórico",type="primary",use_container_width=True,
                  key="hero_to_history",on_click=navigate,args=(pages[4],))
    with c2:
        st.button("🗺️ Centro de control",use_container_width=True,
                  key="hero_to_dashboard",on_click=navigate,args=(pages[1],))
    with c3:
        st.button("📂 Cargar datos",use_container_width=True,
                  key="hero_to_upload",on_click=navigate,args=(pages[2],))
    st.write("")
    st.subheader("Qué podés hacer en IGNIS")
    cards=[
      ("🛰️ Observaciones satelitales",
       "Explorá los registros originales y las diferencias entre los instrumentos MODIS y VIIRS."),
      ("🗺️ Atlas científico",
       "Localizá actividad térmica por región, fecha y sensor en los mapas del estudio."),
      ("🛡️ Trazabilidad",
       "Contrastá episodios con informes y fuentes externas, sin asumir que una detección confirma un incendio."),
    ]
    for col,(title,desc) in zip(st.columns(3,gap="medium"),cards):
        with col:
            st.markdown(f'<div class="ignis-ui-card"><b>{title}</b>'
                        f'<p>{desc}</p></div>',unsafe_allow_html=True)
    st.caption("Investigación independiente en el contexto de NASA Space Apps Challenge 2026. "
               "Las anomalías térmicas no equivalen a incendios confirmados; "
               "la armonización sigue siendo experimental y la cobertura real "
               "depende de los archivos suministrados.")


def render_control_center(combined,sample,selected,base,map_fn,pages,navigate):
    _header("Panel general · Uruguay","Centro de control",
            "Monitoreo exploratorio y análisis histórico de observaciones NASA FIRMS.")
    if isinstance(combined,pd.DataFrame) and not combined.empty and not sample.empty:
        view=sample[sample.anio==selected] if selected is not None else sample
    else:
        view=pd.DataFrame()
    cards=[
        ("Detecciones visibles",f"{len(view):,}" if not view.empty else "Sin datos"),
        ("Años con registros",str(sample.anio.nunique()) if not sample.empty else "—"),
        ("Sensores presentes",str(view.instrumento.nunique()) if not view.empty else "—"),
        ("Año seleccionado",str(selected) if selected is not None else "—"),
    ]
    for column,(title,value) in zip(st.columns(4,gap="small"),cards):
        column.metric(title,value)
    st.write("")
    left,right=st.columns([1.9,1],gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("#### 🗺️ Actividad térmica · Uruguay")
            if not view.empty:
                map_fn(view,"ignis_control_map")
            else:
                st.caption("Importá registros para visualizar las detecciones.")
                _empty_uruguay_outline(base,"ignis_control_empty")
    with right:
        with st.container(border=True):
            st.markdown("#### 📡 Instrumentos")
            if view.empty:
                st.info("No hay observaciones en esta selección.")
                st.button("📂 Importar datos",type="primary",
                          use_container_width=True,key="control_upload",
                          on_click=navigate,args=(pages[2],))
            else:
                counts=view.groupby("instrumento").size().sort_values()
                fig=go.Figure(go.Bar(
                    x=counts.values,y=counts.index.astype(str),orientation="h",
                    marker_color="#44d1e4"))
                fig.update_layout(height=245,margin=dict(l=12,r=12,t=15,b=28),
                    paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#dceffa"),xaxis_title="Registros")
                st.plotly_chart(fig,use_container_width=True,key="ignis_control_sensors")
                st.caption("Cantidad de detecciones por instrumento; no son incendios únicos.")
        with st.container(border=True):
            st.markdown("#### 🛡️ Validación externa")
            st.caption("Evidencias históricas y referencias originales para revisar posibles episodios.")
            st.button("Consultar fuentes",use_container_width=True,key="control_evidence",
                      on_click=navigate,args=(pages[7],))
        with st.container(border=True):
            st.markdown("#### 📚 Otras herramientas")
            st.button("Atlas científico",use_container_width=True,key="control_atlas",
                      on_click=navigate,args=(pages[6],))
            st.button("Armonización MODIS–VIIRS",use_container_width=True,
                      key="control_harmonization",on_click=navigate,args=(pages[5],))
    if not view.empty:
        st.markdown("#### 📈 Evolución mensual del año seleccionado")
        months=view.groupby("mes").size().sort_index()
        fig=go.Figure(go.Bar(
            x=months.index.tolist(),y=months.values.tolist(),
            marker=dict(color="#f28c52"),name="Detecciones"))
        fig.update_layout(height=290,margin=dict(l=15,r=15,t=12,b=35),
            paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e4f3ff"),xaxis=dict(title="Mes",dtick=1,range=[.5,12.5]),
            yaxis_title="Registros")
        st.plotly_chart(fig,use_container_width=True,key="ignis_control_months")
    st.caption("La ausencia de registros no significa ausencia de incendios ni confirma "
               "cobertura satelital completa. Esta plataforma no emite alertas oficiales.")


def render_scientific_atlas(sample,selected,base,map_fn,columns,pages,navigate):
    _header("Atlas científico · Exploración espacial",
            "Atlas de actividad térmica",
            "Elegí una escala temporal y explorá las observaciones térmicas cargadas para Uruguay.")
    if sample.empty:
        st.info("Importá archivos ZIP/CSV o el Maestro IGNIS antes de explorar el atlas.")
        left,right=st.columns([2,1],gap="medium")
        with left:
            _empty_uruguay_outline(base,"ignis_atlas_empty")
        with right:
            st.markdown("#### Empezá por cargar datos")
            st.button("📂 Ir a Carga de datos",type="primary",
                      use_container_width=True,key="atlas_upload",
                      on_click=navigate,args=(pages[2],))
        return
    selector=st.radio("Período del mapa",
                      ["Todo el histórico cargado","Año seleccionado"],
                      horizontal=True,key="ignis_atlas_period")
    mapped=sample if selector=="Todo el histórico cargado" else sample[sample.anio==selected]
    a,b,c=st.columns(3)
    a.metric("Detecciones en el recorte",f"{len(mapped):,}")
    b.metric("Años con registros",str(mapped.anio.nunique()))
    c.metric("Sensores presentes",str(mapped.instrumento.nunique()))
    st.write("")
    map_col,tools_col=st.columns([2.15,1],gap="medium")
    with map_col:
        with st.container(border=True):
            st.markdown("#### 🗺️ Distribución geográfica")
            if not mapped.empty:
                map_fn(mapped,"ignis_atlas_scientific")
            else:
                st.info("No hay puntos para el período seleccionado.")
                _empty_uruguay_outline(base,"ignis_atlas_selection_empty")
    with tools_col:
        with st.container(border=True):
            st.markdown("#### 🧰 Herramientas")
            st.button("🔄 Comparar MODIS–VIIRS",use_container_width=True,
                      key="atlas_harmonization",on_click=navigate,args=(pages[5],))
            st.button("🛡️ Fuentes externas",use_container_width=True,
                      key="atlas_sources",on_click=navigate,args=(pages[7],))
            if not mapped.empty:
                available=[c for c in columns if c in mapped.columns]
                csv=mapped[available].to_csv(index=False).encode("utf-8-sig")
                st.download_button("⬇️ Descargar recorte CSV",csv,
                    file_name="IGNIS_atlas_registros.csv",mime="text/csv",
                    use_container_width=True,key="atlas_download")
        with st.container(border=True):
            st.markdown("#### 📊 Actividad por sensor")
            if not mapped.empty:
                counts=mapped.groupby("instrumento").size()
                fig=go.Figure(go.Pie(labels=counts.index.astype(str),
                                    values=counts.values,hole=.65,
                                    marker=dict(colors=["#3aa5e7","#f39c5c","#40d1c5","#ad91ff"])))
                fig.update_layout(height=245,margin=dict(l=8,r=8,t=4,b=4),
                    paper_bgcolor="rgba(0,0,0,0)",font=dict(color="#ebf6ff"),
                    showlegend=True,legend=dict(orientation="h",y=-.12))
                st.plotly_chart(fig,use_container_width=True,key="atlas_instrument_pie")
            else:
                st.caption("No hay datos para comparar.")
        with st.container(border=True):
            st.markdown("#### 📈 Actividad por mes")
            if not mapped.empty:
                monthly=mapped.groupby("mes").size().sort_index()
                fig=go.Figure(go.Scatter(
                    x=monthly.index.tolist(),y=monthly.values.tolist(),
                    mode="lines+markers",line=dict(color="#4bd5eb",width=3),
                    marker=dict(size=7,color="#fd9356")))
                fig.update_layout(height=220,margin=dict(l=8,r=8,t=12,b=25),
                    paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#dceeff"),xaxis=dict(dtick=1,title="Mes"))
                st.plotly_chart(fig,use_container_width=True,key="atlas_month_line")
    st.caption("Mapa estadístico basado en los registros FIRMS importados; "
               "no utiliza imágenes satelitales como fondo. La densidad es ilustrativa "
               "y no corresponde a hectáreas quemadas. Los meses sin registros "
               "no demuestran ausencia de actividad.")
