"""Agrupa detecciones FIRMS en candidatos documentales por fecha y proximidad."""
import csv
import json
import sys
import zipfile
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

TAMANO_CELDA = 0.10
VENTANA_DIAS = 2


def vecinos(celda):
    fila, columna = celda
    for dfila in (-1, 0, 1):
        for dcolumna in (-1, 0, 1):
            yield fila + dfila, columna + dcolumna


def agrupar_archivo(ruta_zip, ruta_salida):
    with zipfile.ZipFile(ruta_zip) as archivo:
        datos = pd.read_csv(archivo.open("observaciones.csv"))

    datos["fecha"] = pd.to_datetime(datos["fecha"], errors="coerce", utc=True)
    datos = datos.dropna(subset=["fecha", "latitude", "longitude"])
    datos["fila"] = (datos["latitude"] / TAMANO_CELDA).round().astype(int)
    datos["columna"] = (datos["longitude"] / TAMANO_CELDA).round().astype(int)
    candidatos = []

    for año, anual in datos.groupby(datos["fecha"].dt.year):
        por_dia_celda = defaultdict(list)
        for indice, fila in anual.iterrows():
            clave = (fila["fecha"].strftime("%Y-%m-%d"), fila["fila"], fila["columna"])
            por_dia_celda[clave].append(indice)

        dias = sorted(set(fecha for fecha, _, _ in por_dia_celda))
        componentes = []
        visitados = set()
        for clave in por_dia_celda:
            if clave in visitados:
                continue
            cola = deque([clave])
            visitados.add(clave)
            componente = []
            while cola:
                actual = cola.popleft()
                componente.append(actual)
                fecha_actual = datetime.strptime(actual[0], "%Y-%m-%d").date()
                for celda_vecina in vecinos(actual[1:]):
                    for diferencia in range(-VENTANA_DIAS, VENTANA_DIAS + 1):
                        fecha_vecina = fecha_actual + timedelta(days=diferencia)
                        clave_vecina = (fecha_vecina.strftime("%Y-%m-%d"), *celda_vecina)
                        if clave_vecina in por_dia_celda and clave_vecina not in visitados:
                            visitados.add(clave_vecina)
                            cola.append(clave_vecina)
            componentes.append(componente)

        for numero, componente in enumerate(componentes, start=1):
            indices = [indice for clave in componente for indice in por_dia_celda[clave]]
            grupo = datos.loc[indices]
            fechas = grupo["fecha"]
            sensores = grupo["instrumento"].value_counts()
            candidatos.append({
                "id": f"{int(año)}-{numero:04d}",
                "ano": int(año),
                "fecha_desde_utc": fechas.min().strftime("%Y-%m-%d"),
                "fecha_hasta_utc": fechas.max().strftime("%Y-%m-%d"),
                "lat_min": round(float(grupo["latitude"].min()), 4),
                "lat_max": round(float(grupo["latitude"].max()), 4),
                "lon_min": round(float(grupo["longitude"].min()), 4),
                "lon_max": round(float(grupo["longitude"].max()), 4),
                "detecciones": len(grupo),
                "modis": int(sensores.get("MODIS", 0)),
                "viirs_snpp": int(sensores.get("VIIRS S-NPP", 0)),
                "viirs_noaa20": int(sensores.get("VIIRS NOAA-20", 0)),
            })

    campos = list(candidatos[0]) if candidatos else ["id", "ano", "fecha_desde_utc", "fecha_hasta_utc", "lat_min", "lat_max", "lon_min", "lon_max", "detecciones"]
    with open(ruta_salida, "w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(candidatos)
    return candidatos


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: python generar_candidatos_documentales.py MAESTRO.zip CANDIDATOS.csv")
    candidatos = agrupar_archivo(sys.argv[1], sys.argv[2])
    print(json.dumps({
        "candidatos": len(candidatos),
        "por_ano": dict(pd.DataFrame(candidatos).groupby("ano").size())
    }, ensure_ascii=False))
