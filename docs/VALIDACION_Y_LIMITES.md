# Validación, sensibilidad y limitaciones de IGNIS UY

## Evidencia disponible

El repositorio contiene `biblioteca_ignis/validacion_seis_casos.csv` y `biblioteca_ignis/sensibilidad_seis_casos.csv`, que permiten revisar seis casos uruguayos (Cerro del Toro, Durazno, Artigas, Canelones, Lavalleja y Treinta y Tres) con diferentes radios y ventanas temporales.

Los campos de *pares candidatos* documentan asociaciones entre registros, **no** pruebas independientes de que los incendios se hayan confirmado ni de exactitud instrumental. Los archivos deben identificarse con su versión y método: no asumir que equivalen automáticamente al pareo actual si fueron generados con otro algoritmo o rango.

## Qué valida el laboratorio de sensibilidad

- Que la cuenta de celdas-día depende de la resolución espacial elegida.
- Que una coincidencia requiere ambas familias, misma fecha UTC y misma celda según el criterio de redondeo.
- Que duplicar observaciones no duplica la cuenta de celdas-día.
- Que registros de fechas diferentes no se transforman en coincidencias.
- Que no se inventa cobertura en períodos sin datos.

## Qué **no** valida

- Exactitud de la detección de incendios en terreno.
- Probabilidad de coincidencia de un mismo incendio.
- Igual sensibilidad, cobertura y resolución de MODIS y VIIRS.
- Tendencia temporal de incendios en Uruguay a partir de recuentos crudos.
- Intervalos del 95 % o desempeño predictivo.
- Sustitución de métodos de detección y alertas oficiales.

## Riesgos conocidos

1. **Sesgo de muestreo:** el histórico de la demo es parcial, concentrado en meses estivales; días sin observaciones importadas son ambiguos.
2. **Modificación del sensor:** nuevos satélites y cambios de órbita crean cambios artificiales de recuentos.
3. **Cuadrícula:** la resolución y el anclaje de celdas afectan la coincidencia; `0,2°` es una convención exploratoria.
4. **Pareos:** un par candidato satisface umbrales, pero no prueba identidad del evento.
5. **Territorio:** los mapas usan un contorno y cajas geográficas aproximadas.
6. **Datos externos:** noticias y registros institucionales requieren verificación; en la demostración de fusión hay fuentes sintéticas.
7. **IA:** Ask IGNIS es un motor estadístico con reglas, no un LLM de pronóstico.

## Próximos experimentos de validación (no implementados aún)

- Completar cobertura diaria por instrumento, región y producto científico.
- Calibración entre sensores bajo oportunidades de observación comparables.
- Validación retrospectiva por exclusión de sensores, años y regiones.
- Métricas de error, incertidumbre e intervalos reproducibles.
- Contraste sistemático con datos externos reales, auditando falsos positivos y omisiones.

**Principio del proyecto:** anomalía térmica ≠ incendio confirmado. IGNIS UY no emite alertas oficiales, pronósticos validados ni órdenes operativas.
