# IGNIS UY — Del espacio a la evidencia territorial

**Prototipo de investigación científica independiente** que organiza observaciones de anomalías térmicas de NASA FIRMS en Uruguay, explora coincidencias entre MODIS y VIIRS y permite contrastar registros con evidencias documentales y terrestres.

> **Importante:** una detección FIRMS no equivale a un incendio único ni confirma superficie quemada. La armonización **cuantitativa** entre sensores y la validación operativa siguen pendientes.

## Qué está implementado

- Importación de NASA FIRMS MODIS/VIIRS (CSV/ZIP), deduplicación de observaciones y exportación/reimportación manual del Maestro IGNIS.
- Consultas recientes de NASA FIRMS mediante MAP_KEY, iniciadas bajo demanda.
- Mapas, series temporales, calendarios por instrumento y PDF científico.
- Coincidencia exploratoria por **día UTC y celda de 0,20°**; pareo alternativo por **5 km y 30 min** (umbrales configurables).
- **Laboratorio de sensibilidad de cuadrículas**: comparar 0,05°, 0,10°, 0,20° y 0,40° con el mismo recorte y exportar resultados a CSV.
- Monitoreo reciente que incluye NOAA-21; identificación histórica NOAA-21 desde los metadatos del CSV o su nombre.
- Trazabilidad documental, asociación experimental NASA–Bomberos/PAIF–SINAE/MIRA, sección de aportes e interfaz Ask IGNIS **basada en reglas** (no es un LLM).

Los archivos disponibles en una sesión no garantizan cobertura temporal o instrumental completa. Las salidas **no son alertas oficiales**.

## Cómo ejecutar

Python 3.11 recomendado.

```bash
python -m pip install -r requirements.txt
streamlit run principal.py
```

Configurar `FIRMS_MAP_KEY` en los secrets de Streamlit para consultas recientes (ver `.streamlit/secrets.toml.example`). **Nunca publicar claves en el repositorio.** Los ZIP/CSV históricos se cargan desde la interfaz y el Maestro se descarga como respaldo para la siguiente sesión.

### Pruebas de ciencia

```bash
python -m unittest discover -s tests -p "test_ignis_sensibilidad.py" -v
```

Las pruebas sintéticas de sensibilidad no sustituyen validación con incendios confirmados.

## Documentación y atribución

| Documento | Contenido |
|---|---|
| [Fuentes de datos](docs/FUENTES_DATOS.md) | NASA FIRMS y otros servicios: usado, piloto o propuesto |
| [Método científico](docs/METODO_CIENTIFICO.md) | Fórmulas, criterios, discretización, pares y requisitos de calibración |
| [Validación y límites](docs/VALIDACION_Y_LIMITES.md) | Casos, alcance de pruebas, sesgos e incertidumbre pendiente |
| [Uso de IA](docs/USO_DE_IA.md) | Capacidades reales de Ask IGNIS y registro de herramientas por completar |
| [Hoja de ruta](docs/HOJA_DE_RUTA.md) | Fases hacia cobertura, armonización cuantitativa y visualización NASA GIBS |
| [Contribuciones](TEAM_IGNIS_CONTRIBUCIONES.md) | Consultas públicas mediante GitHub Issues |

**Datos:** NASA [Fire Information for Resource Management System (FIRMS)](https://www.earthdata.nasa.gov/data/tools/firms), parte de EOSDIS. Se reconoce la procedencia de las observaciones MODIS y VIIRS. IGNIS UY no es una aplicación de NASA ni cuenta con aprobación institucional implícita.

**Estado del desafío:** esta versión **no** demuestra corrección completa de los saltos en la serie histórica debidos a cambios de sensores. Los recuentos de detecciones se muestran sin normalización por cobertura y las pruebas de coincidencia son exploratorias.

El README y los datos exportados documentan lo que el prototipo realiza realmente; cualquier modelo calibrado deberá publicar metodología, pruebas fuera de muestra e intervalos antes de presentarse como resultado científico.
