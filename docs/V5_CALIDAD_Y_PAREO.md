# IGNIS V5.2 — auditoría, pareo único y contexto NASA

## Alcance de esta entrega

Este módulo mejora la calidad de la investigación y las herramientas de exploración. **No** implementa corrección de sensibilidad, cobertura nubosa u oportunidades de observación ni estima número de incendios únicos.

### 1. Importación FIRMS por fila (`ignis_firms_sensor.py`)

Hasta ahora, cada archivo CSV importado se clasificaba en su conjunto: si mezclaba VIIRS S-NPP, NOAA-20 y NOAA-21, un único nombre podía sustituir las identidades individuales.

Ahora el campo `instrumento` se determina **por fila**, primero por los metadatos `instrument` y `satellite` y, cuando faltan, por un identificador inequívoco de archivo. Una plataforma no identificable se conserva explícitamente como `VIIRS (plataforma no identificada)`; un instrumento desconocido no se convierte arbitrariamente en MODIS/VIIRS y genera una advertencia.

La procedencia de los archivos, los identificadores estables y el ZIP del Maestro se preservan.

### 2. Pareo V5 (`ignis_pareo_v5.py`)

Complementa (no sustituye silenciosamente) el método anterior `ignis_coincidencias.emparejar`.

1. Convierte `fecha + acq_time` a un **instante UTC completo**, rechazando horas HHMM inválidas.
2. Filtra coordenadas fuera de rango, fechas inválidas e instrumentos no reconocidos.
3. Busca candidatos en esfera mediante `cKDTree` con `radio_km` y diferencia temporal `ventana_min`.
4. Considera registros de días contiguos, incluso **a ambos lados de medianoche UTC**, y del cambio de año cuando corresponde.
5. Ordena candidatos por diferencia temporal y después distancia.
6. Selecciona pares sin reutilizar ninguna observación de ambas familias en el resultado total, incluso entre plataformas VIIRS distintas.
7. Mantiene las dos horas, distancias, coordenadas y FRP **sin calibrar** en el CSV descargable.

Limitación: la selección es **greedy** (voraz), no una solución matemática de asignación de costo mínimo global. Un par satisface umbrales de compatibilidad; no demuestra que dos observaciones sean el mismo incendio.

Los resultados V5 pueden diferir de los resultados históricos por el cruce de medianoche o la unicidad global; no deben reemplazarse las tablas antiguas sin indicar la versión del algoritmo.

### 3. Auditoría (`ignis_calidad.py`)

Cuenta registros totales, coordenadas válidas, fechas válidas, horas UTC válidas, instrumentos reconocidos, FRP informado y posibles identificadores duplicados. Genera un inventario mensual de registros importados y días **con detecciones** por plataforma.

**La columna «Días con detecciones» NO es la cantidad de días de sobrevuelo o exposición satelital.** Los meses sin registros se etiquetan «SIN REGISTROS IMPORTADOS» en lugar de afirmar actividad nula. La auditoría no justifica extrapolación temporal ni calibración de recuentos.

### 4. NASA Worldview (`ignis_worldview.py`)

En Atlas y monitoreo NRT se ofrecen enlaces directos a [NASA Worldview](https://worldview.earthdata.nasa.gov/) con fecha y extensión geográfica correspondientes a una observación.

Los parámetros `t` y `v` están documentados en el [repositorio oficial de Worldview](https://github.com/nasa-gibs/worldview/blob/main/doc/url_parameters.md).

El usuario debe seleccionar las capas satelitales apropiadas dentro de Worldview. La fecha y el área no garantizan disponibilidad de imagen útil ni ausencia de nubes; la visualización no confirma un incendio.

### 5. Reproducibilidad

Desde la raíz:

```bash
python -m pip install "numpy>=1.24" "pandas>=2" "scipy>=1.11"
python -m unittest discover -s tests -p 'test_ignis_sensibilidad.py' -v
python -m unittest discover -s tests -p 'test_ignis_pareo_calidad_v5.py' -v
```

Se ejecutan en CI con Python 3.11 y 3.12. Los casos sintéticos contemplan medianoche, cambio de año, satélites mezclados, valores HHMM inválidos, ausencia de cobertura, IDs duplicados y enlaces Worldview.

## Qué sigue pendiente

- Ingestión histórica automatizada con versiones y hashes de producto científico y registro verificable de cobertura real.
- Calibración cuantitativa MODIS–VIIRS con oportunidades de observación equivalentes, día/noche, períodos de solapamiento y control de cambios instrumentales.
- Validación retrospectiva fuera de muestra, límites de incertidumbre y criterios de abstención.
- Capas térmicas NASA GIBS embebidas: aún se ofrece únicamente el **enlace** de verificación Worldview.
- Comparación con eventos confirmados de Bomberos/SINAE usando evidencias reales, no CSV de ensayo.

NASA indica que las observaciones NRT pueden ser reemplazadas por datos de calidad científica en el archivo histórico: [NASA FIRMS Archive](https://firms2.modaps.eosdis.nasa.gov/download/). No es correcto combinar silenciosamente productos NRT y definitivos para una calibración.

**Principio científico:** datos importados ≠ cobertura total; anomalías ≠ incendios confirmados; coincidencias ≠ calibración instrumental.
