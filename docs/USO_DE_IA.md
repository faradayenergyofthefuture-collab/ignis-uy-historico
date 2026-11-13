# Uso de inteligencia artificial — IGNIS UY

La documentación debe reflejar **herramientas realmente usadas por el equipo**, no herramientas mencionadas por otros proyectos ni atribuciones inferidas de archivos de código.

## Componente actual de la aplicación

| Función | Tecnología verificada | Uso |
|---|---|---|
| Ask IGNIS (`ignis_ask.py`) | Reglas explícitas en Python + Pandas | Responde consultas estadísticas exclusivamente sobre los archivos cargados en la sesión |
| Cálculos geoespaciales e históricos | Python, NumPy, Pandas, SciPy | Conteos, coordenadas, umbrales, gráficos y resultados deterministas |
| IA generativa en ejecución | **No identificada** | No etiquetar Ask IGNIS como GPT, Gemini u otro LLM |

No hay evidencia de que un modelo de IA genere números de los informes o detecte incendios. Las salidas cuantitativas corresponden al código.

## Registro que debe completar el equipo antes de la entrega

Para cada herramienta generativa utilizada durante planificación, investigación, diseño, programación o revisión, especificar:

| Herramienta / modelo y versión | Fase | Función realizada | Entradas aportadas | Revisión humana | Responsable |
|---|---|---|---|---|---|
| Por completar y verificar | Por completar | Por completar | Por completar | Por completar | Por completar |

No se deben inventar modelos o versiones, atribuir validación científica a una IA, ni incluir secretos, datos personales o credenciales en documentación pública.

El uso de asistentes de programación **no sustituye pruebas, evaluación científica ni responsabilidad del equipo**.

Para agregar posteriormente un analista generativo: mantener una capa determinista de herramientas y proporcionar citas y filtros de cada resultado; el modelo solo explica los datos ya calculados y debe indicar incertidumbre.
