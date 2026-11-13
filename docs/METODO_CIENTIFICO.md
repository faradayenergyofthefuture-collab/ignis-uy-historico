# Método científico — IGNIS UY

## Unidad de análisis

Cada fila representa una **observación térmica satelital**, no un incendio confirmado ni una superficie quemada. El Maestro conserva fecha UTC, latitud, longitud, instrumento, satélite, hora de adquisición, FRP si está presente, confianza, procedencia e ID.

## 1. Coincidencia por celda-día

El análisis actual asigna cada observación a una cuadrícula:

```text
celda_lat = round(latitud / resolución_en_grados)
celda_lon = round(longitud / resolución_en_grados)
```

Para cada combinación `(día UTC, celda_lat, celda_lon)` se comprueba si hay al menos una observación MODIS y una VIIRS. Se cuenta **una** celda-día coincidente aunque existan varias detecciones en esa celda-día.

```text
C(r) = suma_{día, celda} 1[MODIS > 0 y VIIRS > 0]
```

La resolución **0,20° es un parámetro exploratorio, no una resolución nativa del sensor**. Cerca de 33° S representa aproximadamente 22 km de norte a sur y 19 km de este a oeste, con variaciones según latitud. Dos observaciones próximas pueden caer en celdas diferentes; dos observaciones lejanas pueden pertenecer a la misma celda.

El nuevo laboratorio `ignis_sensibilidad.py` ejecuta exactamente esta regla para 0,05°, 0,10°, 0,20° y 0,40° en el mismo subconjunto importado. Identifica cambios debidos a la escala; **no demuestra por sí mismo un tamaño óptimo**.

## 2. Pareo espacial y temporal

`ignis_coincidencias.py` busca pares candidatos MODIS–VIIRS del mismo día UTC mediante coordenadas sobre una esfera y un `cKDTree`. La distancia se calcula con el radio terrestre medio de 6.371,0088 km. Los umbrales de referencia son **5 km** y **30 minutos**, configurables en la interfaz.

Los candidatos se ordenan por menor diferencia temporal y distancia, con selección no repetida dentro de cada comparación MODIS–plataforma VIIRS. Un punto MODIS puede figurar en comparaciones separadas contra plataformas distintas. Los pares **no son incendios únicos**.

## 3. Estadística temporal

Se cuentan registros por `(año, mes, instrumento)` y se muestra la serie **sin normalización por oportunidades de observación**. La señal piloto de actividad inusual exige al menos tres años de referencia para el mismo mes/sensor, cinco registros y el doble de la mediana de otros años.

No se interpreta la ausencia de registros como un mes de cobertura completa con cero incendios.

## 4. Concentración frente a recurrencia

- **Concentración:** cantidad de observaciones en una celda espacial.
- **Recurrencia:** número de años distintos con observaciones en una celda.
- **Densidad visual:** histograma espacial suavizado con filtro gaussiano, no superficie quemada.

## 5. Fusión cielo–tierra

`ignis_fusion_terrestre.py` asocia candidatos por distancia y tiempo, con parámetros por defecto de 10 km y 24 horas. Cuando el registro externo solo tiene fecha, se usa coincidencia por día local sin inventar una hora exacta. Los CSV sintéticos se identifican y no son validación independiente.

## 6. Requisitos para una armonización cuantitativa futura

Una serie armonizada exige, como mínimo:

1. Disponibilidad instrumental y oportunidades de observación verificadas, separando productos y horas de sobrevuelo.
2. Períodos de solapamiento MODIS–VIIRS representativos para estimar correcciones.
3. Corrección o estratificación de cobertura y diferencias de detección; distinguir día y noche.
4. Validación en años/zonas excluidas del ajuste, métricas de error e intervalos de incertidumbre.
5. Criterios explícitos de no estimar cuando falta información suficiente.

Los cocientes de recuentos crudos **no deben etiquetarse como calibración**. Actualmente IGNIS no publica series cuantitativamente armonizadas ni probabilidades calibradas.

## Reproducibilidad

El laboratorio de sensibilidad es determinista, no requiere servicios externos ni modifica el Maestro; el CSV exportado incluye las cuatro escalas y el recorte del año/región/sensores actualmente seleccionados.

Ejecutar las pruebas:

```bash
python -m unittest discover -s tests -p "test_ignis_sensibilidad.py" -v
```

Ver también [fuentes](FUENTES_DATOS.md), [validación y límites](VALIDACION_Y_LIMITES.md) y los scripts indicados arriba.
