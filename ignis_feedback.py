"""Canal público de contacto y aportes de Team IGNIS.

La app no almacena aportes en Streamlit ni los publica automáticamente.
La publicación requiere que la persona confirme el Issue en GitHub.
"""
from urllib.parse import urlencode
import requests
import streamlit as st

REPO = "sarapcoffee/ignis-uy-historico"
REPO_URL = f"https://github.com/{REPO}"
ISSUES_URL = f"{REPO_URL}/issues"


@st.cache_data(ttl=300, show_spinner=False)
def estado_issues():
    try:
        response = requests.get(
            f"https://api.github.com/repos/{REPO}",
            headers={"Accept": "application/vnd.github+json"},
            timeout=(3, 5),
        )
        response.raise_for_status()
        flag = response.json().get("has_issues")
        return flag if isinstance(flag, bool) else None
    except (requests.RequestException, ValueError):
        return None


def preparar_aporte(categoria: str, titulo: str, descripcion: str, referencia: str = ""):
    """Construye URL y borrador sin enviar nada ni gestionar credenciales."""
    titulo = " ".join(str(titulo).split())[:110]
    descripcion = str(descripcion).strip()[:1500]
    referencia = str(referencia or "").strip()[:350]
    mensaje = (
        "## Tipo de aporte\n" + categoria +
        "\n\n## Consulta o propuesta\n" + descripcion +
        "\n\n## Fuente o referencia (opcional)\n" +
        (referencia or "No proporcionada") +
        "\n\n---\nPreparado desde IGNIS UY. "
        "Las contribuciones quedan pendientes de revisión; "
        "no confirman incendios ni validan automáticamente datos FIRMS."
    )
    parametros = urlencode({
        "title": f"[Team IGNIS] {categoria}: {titulo}",
        "body": mensaje,
    })
    return f"{ISSUES_URL}/new?{parametros}", mensaje


def mostrar_contacto_team():
    st.markdown(
        '<div class="ignis-ui-kicker">Comunidad · Investigación abierta</div>',
        unsafe_allow_html=True,
    )
    st.title("Consultas y aportes al Team IGNIS")
    st.write(
        "Compartí sugerencias, preguntas, errores o referencias documentales. "
        "Las noticias y testimonios son aportes pendientes de revisión, "
        "no verificaciones automáticas de detecciones térmicas."
    )
    issues = estado_issues()
    if issues is False:
        st.warning(
            "GitHub Issues está desactivado. Para recibir contribuciones, "
            "el equipo debe habilitarlo en GitHub → Settings → General "
            "→ Features → Issues. Mientras tanto podés preparar un borrador."
        )
    elif issues is None:
        st.info(
            "No fue posible verificar si GitHub Issues está activo. "
            "El borrador podrá descargarse, sin afirmar que se envió."
        )
    else:
        st.success(
            "GitHub Issues está disponible: podés preparar tu aporte "
            "y publicarlo desde tu cuenta de GitHub."
        )

    st.caption(
        "Los Issues publicados son públicos. No incluyas contraseñas, claves API, "
        "teléfonos, domicilios ni información personal de terceros. "
        "Se necesita una cuenta de GitHub para publicar."
    )
    with st.form("team_ignis_aporte", clear_on_submit=False):
        tipo = st.selectbox(
            "Tipo de aporte",
            [
                "Consulta sobre datos",
                "Fuente documental o noticia",
                "Reportar un error",
                "Sugerencia de mejora",
                "Colaboración científica o técnica",
            ],
        )
        asunto = st.text_input(
            "Título breve", max_chars=110,
            placeholder="Ej.: Fuente de incendio en Durazno, enero de 2022",
        )
        detalle = st.text_area(
            "Consulta o propuesta", max_chars=1500, height=180,
            placeholder="Describí las fechas, coordenadas, evidencia o el error que encontraste.",
        )
        referencia = st.text_input(
            "Enlace de referencia (opcional)", max_chars=350,
            placeholder="https://...",
        )
        confirmado = st.checkbox(
            "Comprendo que el Issue será público y que todavía no se envió."
        )
        preparar = st.form_submit_button(
            "Preparar para GitHub", type="primary", use_container_width=True
        )

    if preparar:
        if len(asunto.strip()) < 8:
            st.error("Escribí un título de al menos 8 caracteres.")
        elif len(detalle.strip()) < 20:
            st.error("Explicá el aporte con al menos 20 caracteres.")
        elif referencia.strip() and not referencia.strip().startswith(("https://", "http://")):
            st.error("La referencia debe comenzar con https:// o http://.")
        elif not confirmado:
            st.error("Confirmá que comprendés la publicación pública.")
        else:
            url, borrador = preparar_aporte(tipo, asunto, detalle, referencia)
            st.session_state["ignis_team_draft"] = {"url": url, "body": borrador}

    draft = st.session_state.get("ignis_team_draft")
    if draft:
        st.subheader("Borrador preparado")
        st.caption("Todavía no se envió. Descargalo o, si Issues está activo, publicalo.")
        with st.expander("Ver el contenido"):
            st.code(draft["body"], language="markdown")
        st.download_button(
            "Descargar borrador (.md)", data=draft["body"].encode("utf-8"),
            file_name="team_ignis_aporte.md", mime="text/markdown",
            use_container_width=True, key="team_draft_download",
        )
        if issues is True:
            st.link_button(
                "Continuar y publicar en GitHub Issues",
                draft["url"], type="primary", use_container_width=True,
            )
            st.caption(
                "GitHub requiere iniciar sesión y confirmar «Submit new issue». "
                "IGNIS no puede comprobar aquí si lo publicaste."
            )
        else:
            st.info(
                "El enlace de publicación aparecerá cuando GitHub Issues "
                "esté habilitado y su estado pueda comprobarse."
            )

    st.divider()
    st.link_button("Ver repositorio IGNIS UY", REPO_URL, use_container_width=True)
    st.caption(
        "No garantizamos respuesta ni incorporación de fuentes sin revisión."
    )
