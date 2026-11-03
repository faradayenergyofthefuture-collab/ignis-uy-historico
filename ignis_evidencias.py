"""Evidencia documental externa para los expedientes históricos de IGNIS."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

RUTA_CATALOGO = Path(__file__).resolve().parent / "biblioteca_ignis" / "evidencias.json"
RUTA_MAESTRO_HISTORICO = Path(__file__).resolve().parent / "catalogo_fuentes_2000_2026.json"


def normalizar_catalogo(catalogo):
    if not isinstance(catalogo, dict):
        raise ValueError("El maestro documental debe ser un objeto JSON.")
    fuentes = catalogo.get("fuentes")
    casos = catalogo.get("casos")
    if isinstance(fuentes, list) and fuentes:
        return {**catalogo, "casos": convertir_fuentes_a_casos(fuentes)}
    if isinstance(casos, list) and casos:
        return catalogo
    raise ValueError("El maestro documental debe contener una lista no vacía de 'fuentes' o 'casos'.")


def cargar_catalogo():
    if RUTA_MAESTRO_HISTORICO.exists():
        try:
            with RUTA_MAESTRO_HISTORICO.open("r", encoding="utf-8") as archivo:
                return normalizar_catalogo(json.load(archivo))
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise ValueError(
                "El maestro documental 2000–2026 está incompleto o vacío. "
                "No se debe mostrar el catálogo antiguo de 2023 como sustituto."
            ) from error

    with RUTA_CATALOGO.open("r", encoding="utf-8") as archivo:
        return normalizar_catalogo(json.load(archivo))


def convertir_fuentes_a_casos(fuentes):
    casos_por_año = {}
    for fuente in fuentes:
        año = int(fuente["anio"])
        fechas = sorted({fecha for fecha in (
            fuente.get("evento_desde", ""), fuente.get("evento_hasta", "")
        ) if fecha})
        caso = casos_por_año.setdefault(año, {
            "id": f"documental-{año}",
            "anio": año,
            "nombre": f"Incidentes documentados {año}",
            "departamento": fuente.get("lugar_reportado", "Uruguay"),
            "fechas_utc": fechas,
            "bbox": [-35.2, -30.0, -58.6, -53.0],
            "resumen": "Fuentes externas agregadas al maestro histórico; no constituyen perímetros ni validación individual de píxel.",
            "esperados": {},
            "fuentes": [],
        })
        caso["fechas_utc"] = sorted(set(caso["fechas_utc"] + fechas))
        caso["fuentes"].append({
            "tipo": fuente.get("clase", "Fuente externa"),
            "medio": fuente.get("organismo", "Organismo no indicado"),
            "titulo": fuente.get("titulo", "Fuente sin título"),
            "fecha_publicacion": fuente.get("fecha_publicacion", ""),
            "hecho_fecha_desde_local": fuente.get("evento_desde", ""),
            "hecho_fecha_hasta_local": fuente.get("evento_hasta", ""),
            "lugar": fuente.get("lugar_reportado", "Uruguay"),
            "url": fuente.get("url", ""),
            "alcance": fuente.get("alcance", "Fuente documental contextual"),
            "notas": fuente.get("nota", ""),
        })
    return list(casos_por_año.values())


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


def mostrar_evidencias(datos: pd.DataFrame | None = None, año: int | None = None) -> None:
    etiqueta_año = str(año) if año is not None else "todos los años"
    st.markdown(f"##### Evidencia externa verificada · {etiqueta_año}")
    st.info("Una noticia, declaración de Bomberos o informe SINAE confirma el contexto del incendio reportado, pero no valida cada detección FIRMS ni su perímetro.")

    with st.expander("Fuentes adicionales incorporadas por el usuario", expanded=False):
        maestro = st.file_uploader("Importar otro Maestro IGNIS documental (JSON, opcional)", type=["json"], key="maestro_documental")
        if maestro is not None:
            try:
                candidato = json.loads(maestro.getvalue().decode("utf-8-sig"))
                candidato = normalizar_catalogo(candidato)
                st.session_state["maestro_documental_2000_2026"] = candidato
                st.success(f"Maestro documental cargado: {len(candidato['casos'])} casos por año.")
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, ValueError) as error:
                st.error(f"No se pudo importar el Maestro documental: {error}")

    try:
        catalogo_sesion = st.session_state.get("maestro_documental_2000_2026")
        catalogo = normalizar_catalogo(catalogo_sesion) if catalogo_sesion is not None else cargar_catalogo()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        st.error(f"No se pudo leer el catálogo documental: {error}")
        return

    st.download_button(
        "Descargar catálogo anual incorporado (JSON)",
        data=json.dumps(catalogo, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="IGNIS_MAESTRO_DOCUMENTAL.json",
        mime="application/json",
        key="descargar_maestro_documental",
    )

    casos = catalogo.get("casos", [])
    if año is not None:
        casos = [caso for caso in casos if
                 int(caso.get("anio", año)) == año
                 or any(str(fecha).startswith(str(año)) for fecha in caso.get("fechas_utc", []))]
    if not casos:
        st.warning(f"No hay fuentes externas incorporadas y verificadas para el año {año}. Esto no demuestra ausencia de incendios.")
        st.caption("Para cada nuevo año deben añadirse casos con fecha, ubicación, enlace y alcance al catálogo biblioteca_ignis/evidencias.json.")
        return

    opciones = {f"{caso['nombre']} ({', '.join(caso.get('fechas_utc', []))})": caso for caso in casos}
    elegido = st.selectbox("Caso documentado", list(opciones), key=f"evidencia_documental_{año or 'todos'}")
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
        file_name="IGNIS_evidencias_externas.json",
        mime="application/json",
    )
    st.download_button(
        "Descargar índice plano de fuentes (CSV)",
        data=pd.DataFrame(filas).to_csv(index=False).encode("utf-8-sig"),
        file_name="IGNIS_fuentes_externas.csv",
        mime="text/csv",
    )
    st.caption("La ausencia de fuentes localizadas en el catálogo no prueba ausencia de incendios. Cada fuente conserva su URL original para auditoría.")
