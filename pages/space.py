import streamlit as st

from ignis_espacio import render_ignis_space_module

st.set_page_config(page_title="IGNIS UY | Space 3D", page_icon="🌍", layout="wide")

st.title("IGNIS UY — Space")

with st.spinner("Preparando la vista espacial 3D..."):
    # La página /space reusa la capa de observaciones del proyecto y no reconstruye la app.
    # El conjunto de datos maestro se toma desde la sesión si ya fue cargado; si no, se muestra una guía clara.
    if "combined" in st.session_state and st.session_state["combined"] is not None:
        render_ignis_space_module(st.session_state["combined"])
    else:
        st.info("Primero cargá o importá un archivo de observaciones FIRMS o el maestro IGNIS para activar la vista 3D del espacio.")
        st.caption("La ruta /space se integra con la plataforma existente sin reemplazar el resto del dashboard.")
