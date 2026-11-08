import streamlit as st

st.set_page_config(page_title="IGNIS UY | Principal", page_icon="🛰️", layout="wide")

home_page = st.Page("ignis_historico.py", title="Principal", icon="🏠")
space_page = st.Page("pages/space.py", title="Vista 3D", icon="🌍")

navigation = st.navigation([home_page, space_page])
navigation.run()
