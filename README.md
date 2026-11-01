# IGNIS UY — Histórico v2.0 (piloto extendido)

Aplicación separada de IGNIS UY 1.7. No reemplaza ni modifica el repositorio original.

## Publicación en Streamlit Cloud

En el repositorio `ignis-uy-historico`, subir los archivos de este ZIP a la **raíz**:
- `ignis_historico.py`
- `requirements.txt`
- `logo_ignis.png`
- carpeta `biblioteca_ignis/` con sus archivos
- `README.md`

Archivo principal de Streamlit: `ignis_historico.py`. No subir el ZIP contenedor a GitHub como reemplazo de los archivos.

## Persistencia de 27 temporadas

**Importante: los datos cargados en Streamlit Cloud no se guardan automáticamente en el servidor.**

1. Cargar ZIP/CSV de NASA FIRMS.
2. Pulsar «Descargar Maestro IGNIS actualizado» y guardar `IGNIS_MAESTRO_HISTORICO.zip` en la PC.
3. En una nueva sesión, cargar primero el maestro anterior y después los ZIP/CSV nuevos.
4. Descargar **otra vez** el maestro actualizado.

La aplicación detecta duplicados exactos mediante una huella por fecha, latitud, longitud, instrumento, satélite, hora y observaciones instrumentales. Mantener los ZIP NASA originales. El maestro almacena observaciones normalizadas, sin los originales.

Para persistencia automatizada multiusuario necesitaríamos una base de datos con acceso autenticado (no incluido en este piloto). No almacenar contraseñas o tokens en el repositorio público.

## Alcances científicos

- Los recuentos son anomalías térmicas observadas, no incendios confirmados.
- Antes de 2012 VIIRS S-NPP no estaba operativo; mantener comparaciones por instrumento.
- No comparar totales de instrumentos distintos sin normalización por resolución/cobertura/horario.
- Las celdas sin detecciones cargadas no garantizan ausencia de actividad; pueden faltar datos u observaciones.
- El filtro nacional es un rectángulo geográfico aproximado, no un polígono oficial.
- La señal de actividad inusual es **exploratoria**, NO una alerta de emergencia ni predicción operacional.
- El catálogo documental de 2023 es independiente de las cargas de otros períodos.
- Las temporadas estivales se definen como diciembre del año anterior + enero y febrero del año titular.
- Año 2000 es parcial en los registros MODIS Terra; 2026 podría estar incompleto.

## Validación pendiente

Pruebas integrales en Streamlit Cloud con ZIP FIRMS de diferentes instrumentos; revisión de solapamientos, integridad, límites nacionales oficiales, cobertura instrumental y normalización para comparación histórica rigurosa.
