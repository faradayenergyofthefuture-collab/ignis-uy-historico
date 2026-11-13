# Fuentes de datos y procedencia — IGNIS UY

> **Estado de implementación verificado en el repositorio.** Una fuente citada como futura no se considera integrada.

| Fuente / servicio | Estado | Uso actual o propuesto | URL |
|---|---|---|---|
| NASA FIRMS: MODIS Collection 6.1 | Implementado | Importación manual histórica CSV/ZIP, metadatos del instrumento | https://www.earthdata.nasa.gov/data/tools/firms |
| NASA FIRMS: VIIRS S-NPP Collection 2 | Implementado | Registros históricos importados por el equipo | https://www.earthdata.nasa.gov/data/tools/firms |
| NASA FIRMS: VIIRS NOAA-20 | Implementado | Datos históricos importados y consultas NRT | https://www.earthdata.nasa.gov/data/tools/firms |
| NASA FIRMS: VIIRS NOAA-21 | NRT implementado; importación histórica en revisión | Monitor reciente mediante API, necesidad de ampliar y validar histórico | https://firms.modaps.eosdis.nasa.gov/api/ |
| NASA FIRMS Area API | Implementado, opt-in | Consulta reciente activada por usuario con `FIRMS_MAP_KEY` | https://firms.modaps.eosdis.nasa.gov/api/ |
| Fuentes nacionales y prensa (Bomberos/PAIF, SINAE/MIRA) | Módulo piloto; validación institucional pendiente | Asociación exploratoria con datos cargados, catálogo y evidencia documental | https://www.gub.uy/sistema-nacional-emergencias/ |
| NASA GIBS | Propuesto | Imágenes y capas por fecha para contexto independiente | https://gibs.earthdata.nasa.gov/ |
| NASA Worldview | Propuesto | Enlace de inspección de un área y fecha | https://worldview.earthdata.nasa.gov/ |
| NASA EONET | Propuesto | Eventos naturales como contexto, NO verdad absoluta de incendios | https://eonet.gsfc.nasa.gov/ |
| NASA POWER | Propuesto (variable auxiliar) | Contexto meteorológico; no detector de incendios | https://power.larc.nasa.gov/ |
| Blue Marble / Black Marble | Referencia visual, no prueba térmica | Fondos e inspiración para visualizaciones; distinguir arte de datos | https://visibleearth.nasa.gov/ |

## Qué significa cada estado

- **Implementado:** código presente en la aplicación. No implica prueba de disponibilidad continua del proveedor.
- **Piloto:** se pueden cruzar datos, pero la exactitud de las asociaciones no está validada por autoridades.
- **Propuesto:** recurso todavía no integrado al procesamiento o visualización; no debe citarse como usado.

## Procedencia

`ignis_historico.py` registra archivo de origen, fecha, latitud, longitud, instrumento, hora, FRP cuando existe y un identificador estable por registro. El resumen de cada archivo importado incluye SHA-256 de su contenido. La deduplicación de observaciones **no** identifica incendios únicos.

El Maestro IGNIS se guarda manualmente con descarga y reimportación entre sesiones. No existe un almacén histórico global automáticamente sincronizado ni cobertura demostrada para todos los meses.

La API NRT no garantiza equivalencia con el archivo científico definitivo. Cuando estén disponibles las colecciones científicas posteriores, deben preferirse para análisis históricos y registrarse sus versiones.

**Precaución:** ausencia de observaciones en archivos cargados ≠ satélite observó una zona sin fuego. Los cambios de satélite, órbita, sensibilidad, nubosidad, productos y calidad deben documentarse antes de comparar tendencias.

## Licencias y atribución

Los datos de anomalías térmicas proceden de NASA FIRMS / EOSDIS. IGNIS UY es un proyecto independiente y no representa un producto ni una validación oficial de NASA.

Referencia: [atribución y productos de NASA FIRMS](https://www.earthdata.nasa.gov/data/tools/firms).
