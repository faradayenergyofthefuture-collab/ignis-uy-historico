# IGNIS UY Histórico V3 — PDF y nueva cabecera

Proyecto experimental de investigación NASA FIRMS. Basado en V2.

## Instalación / Streamlit

Repositorio `ignis-uy-historico`, rama `main`, archivo principal NUEVO `principal.py`. Subir a raíz los archivos de este paquete y conservar la carpeta `biblioteca_ignis/`.

## Novedades V3

- Encabezado corregido con altura suficiente; fondo espacial **decorativo e ilustrativo** derivado de la maqueta conceptual. No representa detecciones científicas.
- Trazabilidad documental en la pestaña «Alertas y trazabilidad»: fuentes de Bomberos, SINAE, prensa y otros medios vinculadas por caso, fecha y recorte. Los enlaces y la fecha de publicación se conservan en el catálogo para revisión; una fuente confirma contexto, no cada píxel FIRMS.
- Logo IGNIS y escudo EMA aportado por el equipo. Inscripción en NASA Space Apps 2026 expresada como texto, sin afirmar patrocinio o aprobación institucional.
- Séptima pestaña «Informe PDF»: informe descargable del **año, región e instrumentos seleccionados**, con contexto histórico disponible, recuentos, serie por instrumento, ubicaciones, actividad inusual piloto y limitaciones.
- Se conserva la carga acumulativa del Maestro IGNIS de V2. La persistencia es manual (descargar/reimportar maestro), no automática.

## Datos en vivo

La pestaña de carga incorpora consultas NRT de NASA FIRMS para Uruguay mediante una `FIRMS_MAP_KEY`. Configurala en Streamlit Cloud como secreto o copiá `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` para ejecutarlo localmente. Las respuestas cubren hasta los últimos 10 días y se cachean una hora. Los datos históricos continúan cargándose mediante ZIP, CSV o Maestro IGNIS.

## Importante

No se ha demostrado la armonización cuantitativa entre sensores. Los gráficos del prototipo muestran detecciones; ninguna detección por sí sola confirma un incendio. Los meses sin detecciones en los archivos no prueban que el satélite haya observado sin incendios.

Los archivos `logo_ignis.png`, `logo_ema.png` y `hero_espacio.jpg` deben quedar en la raíz del repositorio.
