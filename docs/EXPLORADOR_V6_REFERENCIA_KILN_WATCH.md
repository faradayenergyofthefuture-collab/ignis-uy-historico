# IGNIS UY V6 — Explorador inspirado funcionalmente en Kiln Watch

## Visión
Kiln Watch demuestra el valor de una narrativa científica clara, calendarios interactivos, capas NASA y documentación pública de métodos, datos e IA. IGNIS adopta esos principios con identidad propia y foco en Uruguay, sin copiar código, fondos ni diseño de Kiln Watch.

Referencias:
- Kiln Watch (demo): https://kiln-watch-seven.vercel.app/
- Kiln Watch (código): https://github.com/Aalvee-Aarham/nasaspaceappschallenge-2026-team-off-the-binary
- NASA FIRMS / EOSDIS: https://www.earthdata.nasa.gov/data/tools/firms
- NASA GIBS: https://gibs.earthdata.nasa.gov/
- NASA Worldview: https://worldview.earthdata.nasa.gov/

## Cambios implementados

| Concepto de referencia | IGNIS V6 | Límite |
|---|---|---|
| Relato del problema instrumental | Portada con historia MODIS / VIIRS, indicadores y serie anual | Diferencias pueden ser sesgo de muestras |
| Calendario histórico interactivo | Dos calendarios año×mes y selección de período por controles | Recuentos crudos, no armonización |
| Explorador de puntos | Mapa por mes y año, desglose y exportación | Puntos limitados para rendimiento |
| NASA GIBS | Overlay WMS de anomalías térmicas por fecha bajo demanda | No siempre hay capa disponible; no valida incendios |
| NASA Worldview | Enlace para inspección de fecha y zona | Inspección contextual no confirma incendio |
| Datos y procedencia | Tabla de recursos usados y previstos; método e IA explicados | Fuentes previstas no son fuentes actuales |
| Descargas abiertas | ZIP con CSV, manifest, filtros y hashes SHA-256 | No equivale a producto científico calibrado |
| Demo pública sin archivos | Datos sintéticos opcionales con marcas visibles de simulación | Nunca se agregan al Maestro |
| Validación y calibración | Piloto de razón de tasas con cobertura externa y evaluación temporal | No es armonización validada |

## Importante: cómo funciona la demo

Cuando el Maestro está vacío, el Observatorio ofrece una demostración 100 % sintética con datos artificiales. Esta opción no altera el Maestro, no lanza alertas, no permite presentar cifras de NASA y se exporta con metadatos explícitos de simulación. Para evitar relaciones falsas, la superposición de GIBS con puntos sintéticos está deshabilitada.

## Laboratorio de tasa instrumental

El prototipo de calibración requiere un CSV *externo* de oportunidades de observación con encabezados:

fecha_utc,familia,oportunidades,fuente

Una fila por fecha UTC y familia (MODIS o VIIRS), con oportunidades positivas y procedencia descriptiva verificable por el equipo.

- Solo usa fechas donde ambas familias disponen de oportunidades declaradas.
- Los días co-observados sin detecciones tienen recuento cero según el Maestro, siempre condicionados a la cobertura *externa aportada*.
- Necesita al menos 10 meses comparables, con 3 días co-observados por mes; de lo contrario se abstiene.
- Estima en los meses cronológicamente iniciales la razón agregada entre tasas de detección por oportunidad.
- Reserva los meses finales para calcular errores absolutos frente a la referencia MODIS, sin utilizar sus resultados para ajustar el factor.
- Calcula un intervalo bootstrap del 95 % del factor (NO un intervalo de incendios).
- La aplicación NO verifica que la cobertura externa sea completa o físicamente comparable. El resultado conserva etiqueta EXPERIMENTAL incluso si supera las pruebas de software.

Esto no sustituye corrección de sensibilidad, nubosidad, tipo de píxel, hora de sobrevuelo o producto científico. La comparación se hace por *familia instrumental* y aún no separa Terra/Aqua o día/noche.

## Ejecución

1. Ejecutar: streamlit run principal.py
2. Abrir Explorador V6 desde la portada o menú lateral.
3. Importar ZIP/CSV FIRMS o Maestro IGNIS en Carga de datos; usar filtros habituales.
4. Consultar Historia, Explorador, NASA GIBS, Método y fuentes, Descargar y Calibración piloto.
5. Revisar límites científicos antes de interpretar cualquier recuento.

### Pruebas locales

- python -m unittest discover -s tests -p test_ignis_explorer_v6.py -v
- python -m unittest discover -s tests -p test_ignis_harmonizacion_piloto.py -v

También se ejecutan en GitHub Actions para Python 3.11 y 3.12.

## Pendientes para equiparar la ciencia de Kiln Watch

- Histórico territorial completo con cobertura temporal y espacial instrumentada.
- Calibración cuantitativa con escala de referencia, estratos día/noche y tests de exclusión de satélites.
- Resultados robustos frente a cambios de colección, nubes y órbitas.
- Intervalos de incertidumbre de producto científico verdaderamente calibrados.
- API abierta o MCP y herramientas de IA externas con evidencia de uso.
- Validación contra registros de incendios reales independientes.

**La prioridad científica es una serie comparable y demostrable, no simular que ya existe.**

## Declaración

IGNIS UY es un prototipo independiente. Observación térmica no equivale a incendio confirmado. La investigación usa datos NASA FIRMS, pero NASA no valida ni patrocina implícitamente las afirmaciones de IGNIS. La referencia de Kiln Watch es académica y de diseño de producto; no representa colaboración con su equipo.
