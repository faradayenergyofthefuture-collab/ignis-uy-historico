import pandas as pd
import streamlit as st

from ignis_espacio import render_ignis_space_module

st.set_page_config(page_title="IGNIS UY | Espacio 3D", page_icon="🌍", layout="wide")

st.markdown(
    """
    <style>
    .ignis-space-hero {
        background: linear-gradient(120deg, rgba(9,16,31,0.96), rgba(16,40,66,0.92) 38%, rgba(28,58,92,0.85) 100%);
        border: 1px solid rgba(137, 170, 255, 0.35);
        border-radius: 20px;
        padding: 1.4rem 1.5rem;
        box-shadow: 0 20px 42px rgba(5, 10, 24, 0.28);
        margin-bottom: 1rem;
        position: relative;
        overflow: hidden;
    }
    .ignis-space-hero::after {
        content: "";
        position: absolute;
        inset: 0 auto 0 58%;
        width: 42%;
        background: radial-gradient(circle at center, rgba(92, 197, 255, 0.22), transparent 60%);
        pointer-events: none;
    }
    .ignis-space-hero .eyebrow {
        font-size: 11px;
        letter-spacing: 1.6px;
        text-transform: uppercase;
        color: #9fb9ff;
        font-weight: 700;
        margin-bottom: 0.45rem;
    }
    .ignis-space-hero h1 {
        margin: 0;
        color: #edf4ff;
        font-size: clamp(2.1rem, 3vw, 2.8rem);
        line-height: 1.1;
        letter-spacing: -0.04em;
    }
    .ignis-space-hero p {
        margin: 0.7rem 0 0;
        color: #d7e3ff;
        line-height: 1.65;
        max-width: 80%;
    }
    </style>
    <div class="ignis-space-hero">
      <div class="eyebrow">Espacio / seguimiento satelital</div>
      <h1>IGNIS UY — Espacio</h1>
      <p>Visualización 3D de la Tierra, focos térmicos y seguimiento orbital para Uruguay y su contexto regional, con una experiencia más visual y profesional.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.spinner("Preparando la vista espacial 3D..."):
    data = st.session_state.get("combined")
    if data is None:
        data = st.session_state.get("ignis_combined")
    if data is None:
        data = pd.DataFrame()
    render_ignis_space_module(data)
