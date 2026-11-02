"""Evidencia documental externa para los expedientes históricos de IGNIS."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

RUTA_CATALOGO = Path(__file__).resolve().parent / "biblioteca_ignis" / "evidencias.json"


def cargar_catalogo():
    with RUTA_CATALOGO.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


def coincidente_en_datos(caso: dict, datos: pd.DataFrame | None) -> tuple[bool, int]:
    if datos is None or datos.empty:
        return False, 0
    fechas = pd.to_datetime(datos["fecha"], errors="coerce", utc=True)
    lat_min, lat_max, lon_min, lon_max = caso["bbox"]
    valido = pd.DataFrame({
        "fecha": fechas,
        "latitude": pd.to_numeric(datos["latitude"], errors="coerce"),
        "longitude": pd.to_numeric(datos["longitude"], errors="coerce"),
    }).dropna()
    fechas_caso = set(pd.to_datetime(caso.get("fechas_utc", []), errors="coerce", utc=True).strftime("%Y-%m-%d"))
    if not fechas_caso:
        return False, 0
    recorte = valido[
        valido["fecha"].dt.strftime("%Y-%m-%d").isin(fechas_caso)
        & valido["latitude"].between(lat_min, lat_max)
        & valido["longitude"].between(lon_min, lon_max)
    ]
    return len(recorte) > 0, len(recorte)


def mostrar_evidencias(datos: pd.DataFrame | None = None) -> None:
    st.markdown("##### Evidencia externa verificada · 2023")
    st.info("Una noticia, declaración de Bomberos o informe SINAE confirma el contexto del incendio reportado, pero no valida cada detección FIRMS ni su perímetro.")
    try:
        catalogo = cargar_catalogo()
    except (OSError, json.JSONDecodeError) as error:
        st.error(f"No se pudo leer el catálogo documental: {error}")
        return

    casos = catalogo.get("casos", [])
    opciones = {f"{caso['nombre']} ({', '.join(caso.get('fechas_utc', []))})": caso for caso in casos}
    elegido = st.selectbox("Caso documentado", list(opciones), key="evidencia_documental_2023")
    caso = opciones[elegido]
    coincide, cantidad = coincidente_en_datos(caso, datos)

    col1, col2, col3 = st.columns(3)
    col1.metric("Fuentes externas", len(caso.get("fuentes", [])))
    col2.metric("Registros FIRMS en carga actual", cantidad)
    col3.metric("Relación documental", "Coincidencia regional/temporal" if coincide else "Sin coincidencia en la carga actual")

    st.write(caso.get("resumen", "Sin resumen disponible."))
    st.caption("Los recuentos y fechas siguientes proceden del catálogo histórico; pueden diferir de los archivos cargados.")
    st.dataframe(pd.DataFrame([{
        "Fechas UTC": ", ".join(caso.get("fechas_utc", [])),
        "MODIS": caso.get("esperados", {}).get("MODIS", 0),
        "VIIRS S-NPP": caso.get("esperados", {}).get("VIIRS S-NPP", 0),
        "VIIRS NOAA-20": caso.get("esperados", {}).get("VIIRS NOAA-20", 0),
    }]), use_container_width=True, hide_index=True)

    fuentes = caso.get("fuentes", [])
    if not fuentes:
        st.warning("No hay una fuente externa localizada incorporada para este expediente. Esto no demuestra que el incendio no ocurrió.")
        return

    filas = []
    for fuente in fuentes:
        filas.append({
            "Tipo": fuente.get("tipo", ""),
            "Medio": fuente.get("medio", ""),
            "Fecha publicación": fuente.get("fecha_publicacion", ""),
            "Fechas del hecho": f"{fuente.get('hecho_fecha_desde_local', '')} a {fuente.get('hecho_fecha_hasta_local', '')}",
            "Lugar reportado": fuente.get("lugar", ""),
            "Título": fuente.get("titulo", ""),
            "Enlace": fuente.get("url", ""),
        })
    st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    for numero, fuente in enumerate(fuentes, start=1):
        with st.expander(f"Fuente {numero} · {fuente.get('medio', '')}", expanded=(numero == 1)):
            st.markdown(f"**{fuente.get('titulo', '')}**")
            st.write(f"Tipo: {fuente.get('tipo', '')} · Lugar: {fuente.get('lugar', '')}")
            st.caption(f"Hecho reportado: {fuente.get('hecho_fecha_desde_local', '')} a {fuente.get('hecho_fecha_hasta_local', '')}")
            st.write(f"**Alcance:** {fuente.get('alcance', '')}")
            st.write(fuente.get("notas", ""))
            if fuente.get("url"):
                st.link_button("Abrir fuente original", fuente["url"])

    st.download_button(
        "Descargar catálogo completo de fuentes (JSON)",
        data=json.dumps(catalogo, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="IGNIS_evidencias_externas_2023.json",
        mime="application/json",
    )
    st.caption("La ausencia de fuentes localizadas en el catálogo no prueba ausencia de incendios. Cada fuente conserva su URL original para auditoría.")
