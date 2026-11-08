import streamlit as st

from ignis_espacio import render_ignis_space_module

st.set_page_config(page_title="IGNIS UY | Espacio 3D", page_icon="🌍", layout="wide")

st.markdown(
    """
    <style>
    .ignis-space-hero {
        background: linear-gradient(135deg, rgba(13, 22, 46, 0.96), rgba(18, 45, 68, 0.88));
        border: 1px solid rgba(146, 176, 255, 0.38);
        border-radius: 18px;
        padding: 1.1rem 1.2rem;
        box-shadow: 0 18px 36px rgba(6, 12, 28, 0.28);
        margin-bottom: 1rem;
    }
    .ignis-space-hero .eyebrow {
        font-size: 11px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: #a5b9ff;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }
    .ignis-space-hero h1 {
        margin: 0;
        color: #edf4ff;
        font-size: clamp(2rem, 3vw, 2.7rem);
        line-height: 1.1;
    }
    .ignis-space-hero p {
        margin: 0.55rem 0 0;
        color: #cfe0ff;
        line-height: 1.6;
    }
    </style>
    <div class="ignis-space-hero">
      <div class="eyebrow">Espacio / seguimiento satelital</div>
      <h1>IGNIS UY — Espacio</h1>
      <p>Visualización 3D de la Tierra, focos térmicos y seguimiento orbital de observaciones satelitales para Uruguay y su contexto regional.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.spinner("Preparando la vista espacial 3D..."):
    if "combined" in st.session_state and st.session_state["combined"] is not None:
        render_ignis_space_module(st.session_state["combined"])
    else:
        st.info("Primero cargá o importá un archivo de observaciones FIRMS o el maestro IGNIS para activar la vista 3D del espacio.")
        st.caption("La ruta /space se integra con la plataforma existente sin reemplazar el resto del dashboard.")
