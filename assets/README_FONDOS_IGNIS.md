# Fondos de la portada de IGNIS UY

Estas cuatro imágenes fueron aportadas por el equipo del proyecto y optimizadas a WebP para su uso en la página de Inicio. Se alojan en el repositorio, no en un servicio externo.

| Ubicación | Archivo | Asunto |
|---|---|---|
| Portada principal | `bg_portada.webp` | Sudamérica, Uruguay resaltado y satélite |
| Observaciones satelitales | `bg_observaciones.webp` | Satélite escaneando la región |
| Atlas científico | `bg_atlas.webp` | Uruguay destacado sobre la Tierra |
| Trazabilidad | `bg_trazabilidad.webp` | Panel de documentos, análisis y escudo de verificación |

## Integración

Se cargan en `ignis_visual.py` mediante `_apply_local_home_backgrounds()`. La función usa `asset_uri(path, "image/webp")` y emite reglas CSS con degradados oscuros de contraste. Solo afecta a la página de Inicio. Si falta una imagen, se conserva el fondo anterior para esa sección; la portada mantiene además el SVG local como respaldo.

Los recursos **son ilustraciones visuales**. No constituyen imágenes satelitales fechadas, coordenadas validadas, ubicaciones reales de incendios ni evidencia de detecciones NASA FIRMS. Los puntos luminosos y los contornos ilustrativos no deben utilizarse para inferencia geoespacial.

No se han modificado algoritmos de armonización, mapas científicos, importación ZIP, validación externa ni filtros.
