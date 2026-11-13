# Hoja de ruta por fases — IGNIS UY V5

Este documento separa entregables **realmente implementados** de objetivos pendientes. Inspirarse en otros proyectos es válido, pero copiar interfaces o afirmar resultados no reproducidos no lo es.

## Fase 1: cimientos científicos y trazabilidad — incluida en esta PR

- Inventario verificable de fuentes usadas y propuestas.
- Método y limitaciones explícitos, uso de IA sin atribuciones inventadas.
- Laboratorio de sensibilidad de cuadrículas de 0,05° a 0,40°, exportable a CSV.
- Pruebas unitarias y CI de ciencia.
- Importación histórica VIIRS NOAA-21 identificada desde satélite y nombre de archivo.

## Fase 2: cobertura y adquisición histórica — pendiente

- Ingesta histórica verificada por colección y satélite; archivo de metadatos de cobertura temporal y espacial.
- Actualización controlada con checksums, identificadores estables y versionado de cada producto.
- DuckDB/Parquet para acelerar consultas sin sustituir datos originales.
- Distinguir NRT de colecciones científicas y registrar versiones.

## Fase 3: armonización cuantitativa — pendiente

- Definir escala de referencia y períodos reales de solapamiento.
- Estimar ajustes **solo** con exposición instrumentada y datos comparables.
- Separar día/noche y meses/zonas; controlar cambios de sensores.
- Validación retrospectiva por años/sensores no utilizados en entrenamiento.
- Métricas de error, intervalos de incertidumbre y reglas de abstención.

## Fase 4: experiencia y recursos externos — pendiente

- Capas NASA GIBS por día y enlaces contextuales a Worldview.
- Contexto EONET y/o fuentes documentales independientes; eventos no son verdad absoluta de cada píxel.
- API pública con respuestas reproducibles si el pipeline alcanza estabilidad.
- Analista generativo opcional, **nunca** sustituto de cálculos verificados.

### Criterio de aceptación científico

No mostrar etiquetas como «calibrado», «validado», «probabilidad de incendio» o «alerta operativa» hasta disponer de método, datos, validación independiente y documentación de incertidumbre.
