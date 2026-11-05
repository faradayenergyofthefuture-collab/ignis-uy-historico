"""IGNIS UY · Fusión satelital-terrestre, versión cartográfica 2.0 (2026-11-05).

Importación aislada: ``from ignis_fusion_terrestre import mostrar_fusion_terrestre``.
No se conecta a sistemas operativos ni envía alertas externas. No reescribe el Maestro.

Entradas:
- NASA FIRMS: DataFrame ``combined`` existente, columnas fecha/latitude/longitude,
  instrumento/acq_time/id_registro.
- Bomberos/PAIF: CSV o JSON/GeoJSON manual, con mapeo de campos.
- SINAE/MIRA: CSV o JSON/GeoJSON manual, con mapeo de campos.

Salida: asociaciones exploratorias espaciales y temporales, NO detección
validada, no predicción de incendios ni alerta operativa.
"""
from __future__ import annotations

import io
import hashlib
import zipfile
import json
import math
import re
import unicodedata
from datetime import timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

TZ_LOCAL = ZoneInfo("America/Montevideo")
BBOX_UY = (-35.6, -29.9, -58.9, -52.9)
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_ROWS = 100_000

FUENTE_MIRA = (
    "https://catalogodatos.gub.uy/dataset/"
    "sinae01-focos-de-incendios-registrados-en-el-sistema-mira/"
    "resource/76860165-d9a9-4d00-800e-a31ad514d22b"
)
FUENTE_CAMARAS = (
    "https://www.gub.uy/ministerio-interior/comunicacion/noticias/"
    "nuevo-sistema-inteligente-para-deteccion-incendios-geolocalizacion"
)
FUENTE_PAIF = (
    "https://www.spf.com.uy/es/actualidad/temporada-2025-26-del-operativo-paif"
)

ALIASES = {
    "fecha": ["fecha", "fecha_utc", "fecha_hora", "fecha_y_hora", "fecha_evento",
              "fechainicio", "fecha_inicio", "datetime", "date", "timestamp",
              "fecha_registro", "fecha_ocurrencia", "fecha_de_inicio", "fecha_deteccion"],
    "hora": ["hora", "hora_utc", "hora_deteccion", "time", "acq_time"],
    "lat": ["latitud", "latitude", "lat", "y", "coord_y", "coordenada_y", "lat_wgs84"],
    "lon": ["longitud", "longitude", "lon", "long", "lng", "x", "coord_x",
            "coordenada_x", "lon_wgs84"],
    "wkt": ["geometry", "geometria", "wkt", "geom", "the_geom", "punto"],
    "id": ["evento_id", "id_evento", "id", "objectid", "fid", "codigo", "identificador"],
    "detalle": ["tipo_deteccion", "tipo_incendio", "tipo", "subtipo", "descripcion",
                "detalle", "observacion", "observaciones", "situacion", "clase"],
    "estado": ["estado", "confirmado", "estatus", "resultado", "verificacion"],
    "origen": ["fuente", "origen", "institucion", "reportado_por", "organismo"],
}


def canon(s: object) -> str:
    s = unicodedata.normalize("NFKD", str(s).strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def encontrar_columna(columns: list[str], tipo: str) -> str | None:
    dic = {canon(c): c for c in columns}
    for alias in ALIASES[tipo]:
        if canon(alias) in dic:
            return dic[canon(alias)]
    return None


def leer_tabla_bytes(nombre: str, contenido: bytes) -> pd.DataFrame:
    """Lee CSV/JSON/GeoJSON SIN conexiones de red ni ejecución de contenido."""
    if len(contenido) > MAX_UPLOAD_BYTES:
        raise ValueError("Archivo demasiado grande para esta demostración (máximo 12 MB).")
    extension = Path(nombre).suffix.lower()
    if extension == ".csv":
        errors = []
        for enc in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(io.BytesIO(contenido), sep=None, engine="python", encoding=enc,
                                 dtype=str, on_bad_lines="error")
                break
            except Exception as e:
                errors.append(str(e))
        else:
            raise ValueError("No se pudo leer CSV: " + errors[-1][:160])
    elif extension in (".json", ".geojson"):
        data = json.loads(contenido.decode("utf-8-sig"))
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict) and data.get("type") == "FeatureCollection":
            records = []
            for f in data.get("features", []):
                p = f.get("properties") or {}
                geo = f.get("geometry") or {}
                if geo.get("type") == "Point" and len(geo.get("coordinates", [])) >= 2:
                    lon, lat = geo["coordinates"][:2]
                    p = {**p, "__geo_lat": lat, "__geo_lon": lon}
                records.append(p)
            df = pd.DataFrame(records)
        else:
            for key in ("eventos", "events", "records", "features", "data"):
                if isinstance(data, dict) and isinstance(data.get(key), list):
                    df = pd.DataFrame(data[key])
                    break
            else:
                df = pd.DataFrame([data])
    else:
        raise ValueError("Formato no admitido: cargá CSV, JSON o GeoJSON.")
    if len(df) > MAX_ROWS:
        raise ValueError("Demasiadas filas (máximo 100.000 registros por carga).")
    if df.empty:
        raise ValueError("El archivo no contiene filas de datos.")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def leer_firms_adicional(nombre: str, contenido: bytes) -> pd.DataFrame:
    """NASA FIRMS CSV/ZIP adicional, para importar observaciones NRT manualmente.
    NO consulta una API ni modifica el Maestro original.
    """
    if len(contenido) > MAX_UPLOAD_BYTES:
        raise ValueError("NASA CSV/ZIP excede el límite de 12 MB de esta demostración.")
    tablas=[]
    if nombre.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            csvs=[info for info in z.infolist() if info.filename.lower().endswith(".csv")]
            if len(csvs)>20 or sum(x.file_size for x in csvs)>40*1024*1024:
                raise ValueError("ZIP NASA demasiado grande para esta demostración.")
            for f in csvs:
                tablas.append(leer_tabla_bytes(f.filename,z.read(f)))
    else:
        tablas=[leer_tabla_bytes(nombre,contenido)]
    preparados=[]
    for df in tablas:
        cols={canon(c):c for c in df.columns}
        def col(name,default=None):
            return df[cols[name]] if name in cols else default
        if not set(["latitude","longitude"]).issubset(cols):
            continue
        fecha=col("acq_date",col("fecha"))
        if fecha is None:
            continue
        out=pd.DataFrame({
            "fecha":fecha.astype(str),
            "latitude":pd.to_numeric(col("latitude"),errors="coerce"),
            "longitude":pd.to_numeric(col("longitude"),errors="coerce"),
            "instrumento":col("instrument",pd.Series("NASA FIRMS",index=df.index)).fillna("NASA FIRMS").astype(str),
            "acq_time":col("acq_time",pd.Series("",index=df.index)).fillna("").astype(str),
        })
        satellite=col("satellite",pd.Series("",index=df.index)).fillna("").astype(str)
        ids=(out.fecha+"|"+out.latitude.astype(str)+"|"+out.longitude.astype(str)+"|"+
             satellite+"|"+out.acq_time+"|"+out.instrumento)
        out["id_registro"]=ids.map(lambda x:hashlib.sha256(x.encode()).hexdigest()[:24])
        preparados.append(out)
    if not preparados:
        raise ValueError("NASA FIRMS: no se hallaron columnas latitude, longitude y acq_date/fecha.")
    return pd.concat(preparados,ignore_index=True)


def parsear_hora(v: object) -> str | None:
    if v is None or pd.isna(v):
        return None
    s = str(v).strip().replace(".0", "")
    if not s:
        return None
    if re.fullmatch(r"\d{1,4}", s):
        s = s.zfill(4)
        h, m = int(s[:2]), int(s[2:])
        return f"{h:02d}:{m:02d}" if h < 24 and m < 60 else None
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", s)
    if match and int(match[1]) < 24 and int(match[2]) < 60:
        return f"{int(match[1]):02d}:{int(match[2]):02d}"
    return None


def fecha_hora(v: object, hora: object | None = None, origen_tz: str = "America/Montevideo") -> tuple[pd.Timestamp | pd.NaT, bool]:
    """UTC + marca de fecha sin hora. No fabrica precisión horaria."""
    if v is None or pd.isna(v) or not str(v).strip():
        return pd.NaT, True
    s = str(v).strip()
    es_dia = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}", s))
    hh = parsear_hora(hora)
    if es_dia and hh:
        s = f"{s} {hh}"
        es_dia = False
    try:
        dt = pd.to_datetime(s, dayfirst=bool(re.match(r"\d{1,2}/", s)), errors="coerce")
        if pd.isna(dt):
            return pd.NaT, es_dia
        dt = pd.Timestamp(dt)
        if dt.tzinfo is None:
            dt = dt.tz_localize(origen_tz, ambiguous="NaT", nonexistent="NaT")
        return dt.tz_convert("UTC"), es_dia
    except (ValueError, TypeError):
        return pd.NaT, es_dia


def extraer_wkt_point(v: object) -> tuple[float, float]:
    if pd.isna(v):
        return float("nan"), float("nan")
    m = re.search(r"POINT\s*(?:Z\s*)?\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", str(v), re.I)
    if not m:
        return float("nan"), float("nan")
    return float(m[2]), float(m[1])  # lat, lon


def adaptar_externo(raw: pd.DataFrame, categoria: str, columnas: dict[str, str | None],
                     origen_tz: str = "America/Montevideo") -> tuple[pd.DataFrame, dict]:
    """Adaptador universal. Evita atribuir a Bomberos campos no confirmados."""
    if categoria not in ("BOMBEROS_PAIF", "SINAE_MIRA"):
        raise ValueError("Categoría de fuente incorrecta.")
    if not columnas.get("fecha"):
        raise ValueError("Elegí la columna de fecha para permitir el cruce.")
    df = raw.copy()
    lat_col, lon_col = columnas.get("lat"), columnas.get("lon")
    if lat_col and lon_col:
        lat = pd.to_numeric(df[lat_col].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        lon = pd.to_numeric(df[lon_col].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    elif columnas.get("wkt"):
        pares = df[columnas["wkt"]].map(extraer_wkt_point)
        lat = pares.map(lambda t: t[0])
        lon = pares.map(lambda t: t[1])
    else:
        raise ValueError("Seleccioná latitud y longitud (WGS84) o una columna WKT POINT.")
    result = []
    for i, (idx, row) in enumerate(df.iterrows()):
        f, es_dia = fecha_hora(row[columnas["fecha"]],
                             row[columnas["hora"]] if columnas.get("hora") else None,
                             origen_tz)
        def valor(n: str, default: str = "") -> str:
            col = columnas.get(n)
            if not col:
                return default
            x = row[col]
            return default if pd.isna(x) else str(x).strip()[:500]
        result.append({
            "id": valor("id", f"{categoria}_{i+1:05d}"),
            "fecha_utc": f,
            "solo_fecha": bool(es_dia),
            "lat": float(lat.loc[idx]) if pd.notna(lat.loc[idx]) else np.nan,
            "lon": float(lon.loc[idx]) if pd.notna(lon.loc[idx]) else np.nan,
            "categoria": categoria,
            "detalle": valor("detalle"),
            "estado_origen": valor("estado", "Sin especificar"),
            "fuente_decl": valor("origen", categoria),
            "es_simulado": any("SIMULAD" in t.upper() or "SINTETIC" in t.upper()
                                for t in (valor("id"),valor("estado"),valor("origen"))),
        })
    out = pd.DataFrame(result)
    n_initial = len(out)
    out = out.dropna(subset=["fecha_utc", "lat", "lon"]).copy()
    out = out[out.lat.between(BBOX_UY[0], BBOX_UY[1]) &
              out.lon.between(BBOX_UY[2], BBOX_UY[3])]
    out = out.drop_duplicates(subset=["categoria", "id", "fecha_utc", "lat", "lon"])
    out = forzar_fechas_utc(out, categoria)
    return out.reset_index(drop=True), {"leidos": n_initial, "validos": len(out), "omitidos": n_initial-len(out)}


def normalizar_nasa(maestro: pd.DataFrame | None) -> pd.DataFrame:
    columnas = ["id", "fecha_utc", "solo_fecha", "lat", "lon", "instrumento", "fecha_local"]
    if maestro is None or maestro.empty:
        return pd.DataFrame(columns=columnas)
    df = maestro.copy()
    faltan = set(["fecha", "latitude", "longitude"]) - set(df.columns)
    if faltan:
        raise ValueError("El Maestro no tiene columnas esperadas: " + ", ".join(sorted(faltan)))
    lat = pd.to_numeric(df["latitude"], errors="coerce")
    lon = pd.to_numeric(df["longitude"], errors="coerce")
    salida = pd.DataFrame({
        "id": df["id_registro"].astype(str) if "id_registro" in df else [f"FIRMS_{i}" for i in range(len(df))],
        "lat": lat,
        "lon": lon,
        "instrumento": df["instrumento"].fillna("NASA FIRMS").astype(str) if "instrumento" in df else "NASA FIRMS",
    })
    # Procesamiento vectorizado: 17.946 registros en una fracción de segundo.
    fechas_texto = df["fecha"].astype(str).str.strip()
    if "acq_time" in df.columns:
        horas_raw = df["acq_time"].fillna("").astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        horas = horas_raw.str.zfill(4)
        validas = horas.str.fullmatch(r"(?:[01]\d|2[0-3])[0-5]\d")
    else:
        horas = pd.Series("0000",index=df.index)
        validas = pd.Series(False,index=df.index)
    texto_horas = horas.str.slice(0,2) + ":" + horas.str.slice(2,4)
    sin_hora = ~validas.fillna(False)
    marcas = pd.to_datetime(fechas_texto + " " + texto_horas.where(~sin_hora, "00:00"),
                            format="%Y-%m-%d %H:%M",errors="coerce",utc=True)
    salida["fecha_utc"] = marcas
    salida["solo_fecha"] = sin_hora.to_numpy(dtype=bool)
    salida = salida.dropna(subset=["fecha_utc", "lat", "lon"])
    salida = salida[salida.lat.between(BBOX_UY[0], BBOX_UY[1]) &
                    salida.lon.between(BBOX_UY[2], BBOX_UY[3])].copy()
    salida = forzar_fechas_utc(salida, "NASA FIRMS")
    salida["fecha_local"] = salida["fecha_utc"].dt.tz_convert("America/Montevideo").dt.date
    return salida[columnas].reset_index(drop=True)


def forzar_fechas_utc(df: pd.DataFrame, etiqueta: str) -> pd.DataFrame:
    """Fuerza fechas UTC con dtype datetime incluso si pandas recibió objetos.

    Necesario para evitar errores de `.dt` al concatenar DataFrames de
    orígenes y tipos distintos en versiones nuevas de pandas/Streamlit Cloud.
    No inventa fechas ni horarios: las filas imposibles se excluyen.
    """
    if df is None or df.empty:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if "fecha_utc" not in df:
        raise ValueError(f"{etiqueta}: falta la columna fecha_utc")
    salida = df.copy()
    try:
        fechas = pd.to_datetime(salida["fecha_utc"], utc=True,
                                errors="coerce", format="mixed")
    except (TypeError, ValueError):
        fechas = pd.to_datetime(salida["fecha_utc"], utc=True, errors="coerce")
    salida["fecha_utc"] = fechas
    salida = salida.dropna(subset=["fecha_utc"]).copy()
    if not salida.empty and "fecha_local" in salida:
        salida["fecha_local"] = salida["fecha_utc"].dt.tz_convert("America/Montevideo").dt.date
    return salida


def haversine_vector(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Distancia en km, Tierra esférica; suficiente para preselección exploratoria."""
    r = 6371.0088
    a1, o1 = np.deg2rad(lat), np.deg2rad(lon)
    a2, o2 = np.deg2rad(lats), np.deg2rad(lons)
    z = np.sin((a2-a1)/2)**2 + np.cos(a1)*np.cos(a2)*np.sin((o2-o1)/2)**2
    return 2*r*np.arcsin(np.sqrt(np.clip(z, 0, 1)))


def buscar_asociaciones(fuentes: pd.DataFrame, candidatos: pd.DataFrame,
                        radio_km: float, ventana_h: float, ventana_dias_sin_hora: int = 0,
                        excluir_mismo_id: bool = False) -> dict[int, dict]:
    """Devuelve por índice del registro origen sus candidatos dentro del umbral.

    Solo fecha: comparar DÍA LOCAL, sin afirmar coincidencia en minutos.
    Con hora: comparar instante UTC, sin usar el dato histórico como predictor.
    """
    result = {}
    if fuentes.empty or candidatos.empty:
        return result
    # El DataFrame puede traer fechas como object después de una concatenación
    # (especialmente con pandas recientes). Convertirlas explícitamente a UTC.
    fuentes = forzar_fechas_utc(fuentes, "orígenes").copy()
    c = forzar_fechas_utc(candidatos, "candidatos").copy()
    if fuentes.empty or c.empty:
        return result
    c["fecha_local"] = c["fecha_utc"].dt.tz_convert("America/Montevideo").dt.date
    by_day = {k: d for k,d in c.groupby("fecha_local", sort=False)}
    for idx, fila in fuentes.iterrows():
        f = pd.Timestamp(fila["fecha_utc"])
        local = f.tz_convert("America/Montevideo").date()
        # Incluso en detecciones horarias, cubrir cambios de día local.
        dias = 1 + int(math.ceil(ventana_h/24))
        pool = []
        for offset in range(-dias-ventana_dias_sin_hora, dias+ventana_dias_sin_hora+1):
            d = local + timedelta(days=offset)
            if d in by_day:
                pool.append(by_day[d])
        if not pool:
            continue
        sub = pd.concat(pool)
        if excluir_mismo_id:
            sub = sub[sub.id.astype(str) != str(fila["id"])]
        if sub.empty:
            continue
        dist = haversine_vector(float(fila["lat"]), float(fila["lon"]),
                               sub.lat.to_numpy(dtype=float), sub.lon.to_numpy(dtype=float))
        en_espacio = dist <= radio_km
        if not np.any(en_espacio):
            continue
        sub = sub.loc[en_espacio].copy()
        sub["km"] = dist[en_espacio]
        sub["delta_min"] = np.abs((sub.fecha_utc-f).dt.total_seconds()/60)
        fila_dia = bool(fila["solo_fecha"])
        candidato_dia = sub.solo_fecha.to_numpy(dtype=bool)
        # Si cualquiera de las dos fechas no trae hora, exigir coincidencia de día local.
        hay_hora = ~candidato_dia & ~fila_dia
        misma_fecha = (sub.fecha_local.to_numpy() == local)
        if ventana_dias_sin_hora:
            same_days = np.array([abs((d-local).days) <= ventana_dias_sin_hora for d in sub.fecha_local])
        else:
            same_days = misma_fecha
        valida = np.where(hay_hora, sub.delta_min.to_numpy() <= ventana_h*60, same_days)
        sub = sub.loc[valida].sort_values(["km", "delta_min"])
        if sub.empty:
            continue
        result[idx] = {
            "n": len(sub), "mejor_id": str(sub.iloc[0]["id"]),
            "dist_km": float(sub.iloc[0]["km"]),
            "delta_min": (float(sub.iloc[0]["delta_min"])
                          if not fila_dia and not bool(sub.iloc[0]["solo_fecha"]) else np.nan),
            "precision": ("coincidencia de día (hora desconocida)"
                          if fila_dia or bool(sub.iloc[0]["solo_fecha"]) else "tiempo UTC"),
            "ids": sub.id.astype(str).tolist()[:20],
            "instrumentos": ", ".join(sorted(sub.instrumento.unique())) if "instrumento" in sub else "",
        }
    return result


def fusionar(nasa: pd.DataFrame, bomberos: pd.DataFrame, sinae: pd.DataFrame,
             radio_km: float = 10.0, ventana_h: float = 24.0,
             dias_sin_hora: int = 0) -> pd.DataFrame:
    """Una fila por registro externo, no por incendio único.

    Conservable con un evento Bomberos que enlace SINAE y NASA; las filas SINAE
    vinculadas no se duplican como evento autónomo.
    """
    salidas=[]
    b = forzar_fechas_utc(bomberos, "Bomberos/PAIF").reset_index(drop=True)
    s = forzar_fechas_utc(sinae, "SINAE/MIRA").reset_index(drop=True)
    nasa = forzar_fechas_utc(nasa, "NASA FIRMS").reset_index(drop=True)
    x = pd.concat([b,s],ignore_index=True) if len(b)+len(s) else pd.DataFrame()
    if not x.empty:
        x = forzar_fechas_utc(x, "eventos combinados").reset_index(drop=True)
    if x.empty:
        return pd.DataFrame(columns=["id_evento","fuentes","fecha_utc","lat","lon","resultado",
                                     "n_firms","n_sinae","distancia_km","minutos","precision",
                                     "instrumentos","detalle","estado_origen","simulado"])
    matches_firms = buscar_asociaciones(x,nasa,radio_km,ventana_h,dias_sin_hora)
    matches_sinae = buscar_asociaciones(b,s,radio_km,ventana_h,dias_sin_hora)
    used_sinae=set()
    for i, r in x.iterrows():
        b_row = i < len(b)
        match_s = matches_sinae.get(i) if b_row else None
        if match_s:
            used_sinae.update(match_s["ids"])
        if not b_row and str(r["id"]) in used_sinae:
            continue
        sat = matches_firms.get(i)
        ns = match_s["n"] if match_s else 0
        es_s = (r["categoria"] == "SINAE_MIRA")
        if sat and (ns or (es_s and len(b)>0 and any(str(r["id"]) in v["ids"] for v in matches_sinae.values()))):
            estado = "NASA + terrestre + SINAE (revisar)"
        elif sat:
            estado = "NASA + " + ("SINAE (revisar)" if es_s else "terrestre (revisar)")
        elif ns:
            estado = "Terrestre + SINAE, sin FIRMS"
        else:
            estado = "SINAE sin FIRMS cercano" if es_s else "Terrestre sin FIRMS cercano"
        fuentes = {"SINAE/MIRA"} if es_s else {"Bomberos/PAIF"}
        if ns:
            fuentes.add("SINAE/MIRA")
        if sat:
            fuentes.add("NASA FIRMS")
        salidas.append({
            "id_evento":str(r["id"]), "fuentes":" + ".join(sorted(fuentes)),
            "fecha_utc":str(r["fecha_utc"]),"lat":round(float(r["lat"]),5),
            "lon":round(float(r["lon"]),5), "resultado":estado,
            "n_firms":int(sat["n"]) if sat else 0, "n_sinae":int(ns),
            "distancia_km":round(sat["dist_km"],2) if sat else np.nan,
            "minutos":round(sat["delta_min"],1) if sat and pd.notna(sat["delta_min"]) else np.nan,
            "precision":sat["precision"] if sat else ("fecha sin hora" if r["solo_fecha"] else "con hora"),
            "instrumentos":sat["instrumentos"] if sat else "",
            "detalle":str(r["detalle"]), "estado_origen":str(r["estado_origen"]),
            "simulado":"SÍ — NO USAR COMO EVIDENCIA" if bool(r.get("es_simulado",False)) else "No",
        })
    return pd.DataFrame(salidas)


def demo_sintetica(nasa: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Datos de prueba, etiquetados SIEMPRE como ficticios; no avalan eficacia."""
    if nasa.empty:
        # Sin Maestro, se muestra capacidad de carga, NO inventar coincidencia.
        return pd.DataFrame(),pd.DataFrame()
    post2018 = nasa[nasa.fecha_utc.dt.year >= 2018]
    sat = post2018.iloc[0] if not post2018.empty else nasa.iloc[0]
    f = pd.Timestamp(sat["fecha_utc"])
    fake1={"id":"SIMULADO_CAMARA_001","fecha_utc":f+pd.Timedelta(minutes=15),
           "solo_fecha":False,"lat":float(sat.lat)+0.006,"lon":float(sat.lon)+0.005,
           "categoria":"BOMBEROS_PAIF","detalle":"SIMULACIÓN: cámara detecta posible humo",
           "estado_origen":"SIMULADO — sin verificación", "fuente_decl":"SIMULADO", "es_simulado":True}
    fake2={"id":"SIMULADO_SINAE_001","fecha_utc":f+pd.Timedelta(minutes=23),
           "solo_fecha":False,"lat":float(sat.lat)+0.007,"lon":float(sat.lon)+0.005,
           "categoria":"SINAE_MIRA","detalle":"SIMULACIÓN: reporte de evento (inventado)",
           "estado_origen":"SIMULADO — sin verificación", "fuente_decl":"SIMULADO", "es_simulado":True}
    return pd.DataFrame([fake1]),pd.DataFrame([fake2])


def tabla_ejemplo(tipo: str) -> bytes:
    # Ejemplos de estructura, no incidentes reales ni datos institucionales.
    if tipo == "terrestre":
        datos=[dict(evento_id="SIMULADO_CAMARA_001",fecha_utc="2026-01-12T15:45:00Z",
                    latitud=-34.75,longitud=-55.70,fuente="EJEMPLO_SINTETICO_NO_REAL",
                    tipo_deteccion="posible_humo",estado="pendiente_revision")]
    else:
        datos=[dict(evento_id="SIMULADO_SINAE_001",fecha_utc="2026-01-12",
                    latitud=-34.75,longitud=-55.70,fuente="EJEMPLO_SINTETICO_NO_REAL",
                    tipo_incendio="no_determinado",estado="ejemplo")]
    return pd.DataFrame(datos).to_csv(index=False).encode("utf-8-sig")


def dibujar_mapa(nasa: pd.DataFrame, bom: pd.DataFrame, sin: pd.DataFrame,
                 resultados: pd.DataFrame) -> str:
    import folium
    mapa = folium.Map(location=[-32.95,-56.25], zoom_start=6, tiles="CartoDB dark_matter",control_scale=True)
    # Contexto histórico: año-celda 0,2 grados (no puntos de incendio confirmados).
    if not nasa.empty:
        g=nasa.copy()
        g["ano"] = g.fecha_utc.dt.year
        g["ilat"] = np.floor(g.lat / 0.2).astype(int)
        g["ilon"] = np.floor(g.lon / 0.2).astype(int)
        r=g.groupby(["ilat","ilon"]).ano.nunique().sort_values(ascending=False)
        layer=folium.FeatureGroup(name="Recurrencia histórica FIRMS (celdas)",show=True)
        for (il,io),n in r.head(550).items():
            if n < 3:
                continue
            color=("#ff995f" if n>=18 else "#ebca75" if n>=11 else
                   "#67d5c4" if n>=6 else "#479bad")
            folium.Rectangle([[il*.2,io*.2],[(il+1)*.2,(io+1)*.2]],
                             fill=True,fill_color=color,fill_opacity=.53,
                             color=color,weight=0.4,
                             tooltip=f"{n} años con observación NASA FIRMS en celda de 0,2°").add_to(layer)
        layer.add_to(mapa)
    for df,color,title in ((bom,"#ffbe6d","Detección terrestre cargada"),
                           (sin,"#6bd2fa","Registro SINAE/MIRA cargado")):
        if df.empty:
            continue
        layer=folium.FeatureGroup(name=f"{title} ({len(df)})",show=True)
        for _, r in df.head(500).iterrows():
            texto=(f"{escape(title)}<br>ID: {escape(str(r['id']))}<br>"
                   f"Fecha: {escape(str(r['fecha_utc']))}<br>"
                   f"Tipo: {escape(str(r['detalle']))}<br>"
                   f"Estado original: {escape(str(r['estado_origen']))}")
            folium.CircleMarker([float(r.lat),float(r.lon)],radius=6,color=color,
                                fill=True,fill_color=color,fill_opacity=.90,
                                tooltip=f"{title} · {r['id']}",popup=folium.Popup(texto,max_width=330)).add_to(layer)
        layer.add_to(mapa)
    if not resultados.empty:
        layer=folium.FeatureGroup(name="Coincidencias para revisión",show=True)
        for _,r in resultados[resultados.n_firms>0].head(300).iterrows():
            texto=escape(str(r.resultado))+'<br>FIRMS cercanos: '+str(r.n_firms)
            folium.CircleMarker([r.lat,r.lon],radius=11,weight=2,color="#f9e77d",
                                fill=False,tooltip=texto,popup=texto).add_to(layer)
        layer.add_to(mapa)
    # No graficar posiciones de cámaras ni límites de cobertura que no consten oficialmente.
    folium.LayerControl(collapsed=False).add_to(mapa)
    return mapa.get_root().render()




# ---------------------------------------------------------------------------
# INTERFAZ MAPA V2 — Un único módulo aislado; el resto de IGNIS no se modifica.
# ---------------------------------------------------------------------------

PASO_GRADOS = 0.2
CASOS_DOCUMENTADOS = [
    {"nombre":"Algorta / Orgoroso · episodio litoral 2021–2022",
     "lat":-32.4222, "lon":-57.3922, "inicio":"2021-12-29", "fin":"2022-01-05",
     "fuente":"SINAE", "url":"https://www.gub.uy/sistema-nacional-emergencias/comunicacion/comunicados/informe-situacion-incendios-forestales-31-12-2021"},
    {"nombre":"Algorta · nuevo episodio 2023",
     "lat":-32.4222,"lon":-57.3922,"inicio":"2023-01-04","fin":"2023-01-05",
     "fuente":"SINAE", "url":"https://www.gub.uy/sistema-nacional-emergencias/comunicacion/noticias/informe-situacion-sobre-incendio-forestal-rio-negro"},
    {"nombre":"La Esmeralda, Rocha · 2005",
     "lat":-34.1575,"lon":-53.6931,"inicio":"2005-01-17","fin":"2005-01-25",
     "fuente":"SINAE", "url":"https://www.gub.uy/sistema-nacional-emergencias/comunicacion/publicaciones/incendios"},
    {"nombre":"La Esmeralda, Rocha · 2019",
     "lat":-34.1575,"lon":-53.6931,"inicio":"2019-12-10","fin":"2019-12-17",
     "fuente":"SINAE", "url":"https://www.gub.uy/sistema-nacional-emergencias/comunicacion/noticias/eventos-adversos-significativos-ocurridos-uruguay-entre-anos-2015-2019"},
    {"nombre":"Fortín de Santa Rosa · temporada 2021–2022",
     "lat":-34.7719,"lon":-55.8056,"inicio":"2021-12-29","fin":"2022-01-03",
     "fuente":"SINAE", "url":"https://www.gub.uy/sistema-nacional-emergencias/comunicacion/comunicados/informe-situacion-incendios-forestales-31-12-2021"},
]
# SOLO centros aproximados de localidades nombradas en comunicaciones / licitación.
# ¡NO equivalen a las posiciones de las cámaras o de las torres instaladas!
REFERENCIAS_CAMARAS = [
    {"nombre":"Santa Ana, Colonia", "lat":-34.4214,"lon":-57.5935,
     "nota":"Localidad citada por Ministerio del Interior; posición de cámara sin verificar"},
    {"nombre":"Boca del Cufré, San José", "lat":-34.456,"lon":-57.111,
     "nota":"Zona Cufré citada por Ministerio del Interior; posición de cámara sin verificar"},
    {"nombre":"Parque del Plata, Canelones", "lat":-34.7560,"lon":-55.7226,
     "nota":"Localidad mencionada en documentación de licitación; instalación no verificada"},
    {"nombre":"Punta Ballena, Maldonado", "lat":-34.8889,"lon":-55.0406,
     "nota":"Localidad citada por Ministerio del Interior; posición de cámara sin verificar"},
]
ZONAS = {
    "Todo Uruguay": (-35.28,-29.90,-58.70,-53.00),
    "Litoral oeste · recorte aproximado":(-34.0,-30.65,-58.70,-56.65),
    "Centro · recorte aproximado":(-34.3,-31.3,-57.55,-54.9),
    "Costa sur y este · recorte aproximado":(-35.28,-33.35,-58.7,-53.0),
    "Norte · recorte aproximado":(-32.0,-29.90,-58.65,-53.35),
}


def _normalizar_gps_uy(df: pd.DataFrame, lat_col="lat", lon_col="lon") -> pd.DataFrame:
    if df is None or df.empty:
        return df.copy() if isinstance(df,pd.DataFrame) else pd.DataFrame()
    out=df.copy()
    out[lat_col]=pd.to_numeric(out[lat_col],errors="coerce")
    out[lon_col]=pd.to_numeric(out[lon_col],errors="coerce")
    out=out.dropna(subset=[lat_col,lon_col])
    return out.loc[out[lat_col].between(BBOX_UY[0],BBOX_UY[1]) &
                   out[lon_col].between(BBOX_UY[2],BBOX_UY[3])].copy()


def _recortar(df: pd.DataFrame, zona: str, lat="lat",lon="lon") -> pd.DataFrame:
    if df is None or df.empty:return df.copy() if isinstance(df,pd.DataFrame) else pd.DataFrame()
    a,b,c,d=ZONAS[zona]
    return df.loc[df[lat].between(a,b)&df[lon].between(c,d)].copy()


def _contorno_uy() -> list[tuple[float,float]]:
    # Archivo real del repositorio IGNIS; sólo contorno nacional de baja resolución.
    p=Path(__file__).resolve().parent/'uruguay_contorno.geojson'
    if p.exists():
        try:
            data=json.loads(p.read_text(encoding="utf-8"))
            coords=data['features'][0]['geometry']['coordinates'][0]
            return [(float(x),float(y)) for x,y in coords]
        except (KeyError,IndexError,ValueError,TypeError, OSError):
            pass
    # Respaldo del mismo contorno simplificado incluido en el repositorio.
    return [(-57.62513342958296, -30.21629485445426), (-56.976025763564735, -30.109686374636127), (-55.97324459494094, -30.883075860316303), (-55.601510179249345, -30.853878676071393), (-54.57245154480512, -31.494511407193748), (-53.78795162618219, -32.047242526987624), (-53.209588995971544, -32.727666110974724), (-53.6505439927181, -33.20200408298183), (-53.373661668498244, -33.768377780900764), (-53.806425950726535, -34.39681487400223), (-54.93586605489773, -34.952646579733624), (-55.67408972840329, -34.75265878676407), (-56.21529700379607, -34.85983570733742), (-57.1396850246331, -34.430456231424245), (-57.81786068381551, -34.4625472958775), (-58.42707414410439, -33.909454441057576), (-58.349611172098875, -33.26318897881541), (-58.13264767112145, -33.040566908502015), (-58.14244035504076, -32.044503676076154), (-57.87493730328188, -31.016556084926208), (-57.62513342958296, -30.21629485445426)]


def _contiene_punto(lon:float, lat:float, poligono:list[tuple[float,float]]) -> bool:
    # Ray casting independiente de shapely. Contorno simplificado = aproximación.
    if not poligono:return True
    dentro=False
    for i in range(len(poligono)-1):
        x1,y1=poligono[i];x2,y2=poligono[i+1]
        if (y1>lat)!=(y2>lat):
            xcr=x1+(lat-y1)*(x2-x1)/(y2-y1)
            if lon<xcr:dentro=not dentro
    return dentro


def _crear_malla(nasa:pd.DataFrame) -> pd.DataFrame:
    cols=["ilat","ilon","lat_c","lon_c","registros","anios","dias","primer_ano","ultimo_ano","sensores"]
    if nasa is None or nasa.empty:return pd.DataFrame(columns=cols)
    d=forzar_fechas_utc(nasa,"NASA malla").copy()
    if d.empty:return pd.DataFrame(columns=cols)
    d['anio']=d['fecha_utc'].dt.year
    d['dia']=d['fecha_utc'].dt.date
    d['ilat']=np.floor(d['lat'].astype(float)/PASO_GRADOS).astype(int)
    d['ilon']=np.floor(d['lon'].astype(float)/PASO_GRADOS).astype(int)
    g=d.groupby(['ilat','ilon'],observed=True).agg(
        registros=('id','count'),anios=('anio','nunique'),dias=('dia','nunique'),
        primer_ano=('anio','min'),ultimo_ano=('anio','max'),
        sensores=('instrumento',lambda x:", ".join(sorted(set(x.astype(str)))))
    ).reset_index()
    g['lat_c']=(g.ilat+0.5)*PASO_GRADOS
    g['lon_c']=(g.ilon+0.5)*PASO_GRADOS
    # Se evita pintar celdas fuera del contorno nacional simplificado.
    polygon=_contorno_uy()
    if polygon:
        validos=[_contiene_punto(float(r.lon_c),float(r.lat_c),polygon) for r in g.itertuples()]
        g=g.loc[validos].copy()
    return g.sort_values(['anios','registros'],ascending=False).reset_index(drop=True)[cols]


def _paleta(n:int) -> str:
    if n>=18:return "#f48b5a"
    if n>=11:return "#e1bf73"
    if n>=6:return "#62c9bb"
    if n>=3:return "#458fa6"
    return "#24516a"


def _mapa_plotly(malla:pd.DataFrame, nasa:pd.DataFrame, bom:pd.DataFrame,
                  sin:pd.DataFrame, zona:str, ano:int|None,
                  ver_referencias:bool=True,ver_casos:bool=True,
                  celdas_activas:set|None=None):
    import plotly.graph_objects as go
    figura=go.Figure()
    geo=_contorno_uy()
    if geo:
        figura.add_trace(go.Scatter(
            x=[x for x,y in geo], y=[y for x,y in geo],mode='lines',
            fill='toself',fillcolor='rgba(26,48,70,.50)',
            line=dict(color='#c7e7fa',width=2),name='Contorno simplificado',hoverinfo='skip',
            showlegend=False))
    else:
        figura.add_trace(go.Scatter(x=[],y=[],mode='lines',showlegend=False))
    if not malla.empty:
        m=malla.sort_values(['ilon','ilat']).reset_index(drop=True)
        activas=(set() if celdas_activas is None else celdas_activas)
        bordes=['#ffed97' if (int(r.ilat),int(r.ilon)) in activas else 'rgba(4,17,30,.5)' for r in m.itertuples()]
        hover=(m['anios'].astype(str)+' años con detecciones FIRMS<br>'+
               m['registros'].astype(str)+' registros en la celda<br>'+
               'Centro: '+m['lat_c'].round(2).astype(str)+'°, '+m['lon_c'].round(2).astype(str)+'°<br>'+
               'Hacé clic para inspeccionar')
        figura.add_trace(go.Scatter(
            x=m['lon_c'],y=m['lat_c'],mode='markers',name='Celdas FIRMS',
            marker=dict(symbol='square',size=23,color=[_paleta(int(v)) for v in m.anios],
                        line=dict(color=bordes,width=1.2 if celdas_activas is not None else 0.6),opacity=.96),
            customdata=np.array(m[['ilat','ilon']].values,object),
            text=hover,hovertemplate='%{text}<extra></extra>',showlegend=False))
    else:
        figura.add_trace(go.Scatter(x=[],y=[],mode='markers',name='Celdas FIRMS',showlegend=False))
    if ver_referencias:
        ref=[r for r in REFERENCIAS_CAMARAS
             if ZONAS[zona][0]<=r['lat']<=ZONAS[zona][1] and ZONAS[zona][2]<=r['lon']<=ZONAS[zona][3]]
        if ref:
            figura.add_trace(go.Scatter(
                x=[x['lon'] for x in ref],y=[x['lat'] for x in ref],
                mode='markers',name='Localidades de referencia, NO torres',
                marker=dict(symbol='diamond-open',size=14,color='#4fc2ff',line=dict(width=2)),
                text=[f"{x['nombre']}<br>{x['nota']}" for x in ref],
                hovertemplate='%{text}<extra></extra>'))
    if ver_casos:
        cases=[x for x in CASOS_DOCUMENTADOS if
               ZONAS[zona][0]<=x['lat']<=ZONAS[zona][1] and
               ZONAS[zona][2]<=x['lon']<=ZONAS[zona][3] and
               (ano is None or int(x['inicio'][:4])<=ano<=int(x['fin'][:4]))]
        if cases:
            figura.add_trace(go.Scatter(
                x=[c['lon'] for c in cases],y=[c['lat'] for c in cases],
                mode='markers', name='Localidad de incendio documentado',
                marker=dict(symbol='circle-open',size=17,color='#ff8aa5',line=dict(width=2.5)),
                text=[c['nombre']+'<br>'+c['inicio']+' a '+c['fin']+
                      '<br>Posición de localidad, NO punto exacto del incendio' for c in cases],
                hovertemplate='%{text}<extra></extra>'))
    for d,color,name in ((bom,'#ffbd60','Terrestre cargado'),(sin,'#f17ce2','SINAE cargado')):
        if d is not None and not d.empty:
            d=d.head(1000)
            figura.add_trace(go.Scatter(
                x=d['lon'],y=d['lat'],mode='markers',name=name,
                marker=dict(symbol='x',size=11,color=color,line=dict(width=2)),
                text=[f"{name} • {r.id}<br>{str(r.fecha_utc)}<br>{'SIMULADO' if r.es_simulado else 'Estado por verificar'}" for r in d.itertuples()],
                hovertemplate='%{text}<extra></extra>'))
    a,b,c,d=ZONAS[zona]
    figura.update_layout(
        paper_bgcolor='#081426',plot_bgcolor='#081426',font=dict(color='#e9f5ff',size=12),
        height=690,margin=dict(t=15,b=25,l=15,r=15),
        hovermode='closest',clickmode='event+select',
        legend=dict(x=.01,y=.01,xanchor='left',yanchor='bottom',bgcolor='rgba(8,21,38,.7)',font=dict(size=10)),
        xaxis=dict(range=[c-.05,d+.05],title='Longitud (°O)',gridcolor='#1c3348',zeroline=False,
                   scaleanchor='y',scaleratio=1),
        yaxis=dict(range=[a-.05,b+.05],title='Latitud (°S)',gridcolor='#1c3348',zeroline=False)
    )
    return figura


def _seleccion_de_grafico(evento:object) -> tuple[int,int]|None:
    try:
        seleccion=evento.get('selection',{}) if isinstance(evento,dict) else getattr(evento,'selection',{})
        puntos=seleccion.get('points',[]) if isinstance(seleccion,dict) else getattr(seleccion,'points',[])
        for punto in puntos:
            if int(punto.get('curve_number',-1))!=1:continue
            cd=punto.get('customdata')
            if cd is not None and len(cd)>=2:
                return (int(cd[0]),int(cd[1]))
    except (TypeError,ValueError,AttributeError,IndexError):
        pass
    return None


def _descripcion_celda(malla:pd.DataFrame,c:tuple[int,int]) -> str:
    m=malla[(malla.ilat==c[0])&(malla.ilon==c[1])]
    if m.empty:return str(c)
    r=m.iloc[0]
    return (f"{r.lat_c:.2f}°S, {abs(r.lon_c):.2f}°O · "
            f"{int(r.anios)} años · {int(r.registros)} observaciones")


def _interpretacion_celda(hist:pd.DataFrame, b:pd.DataFrame, s:pd.DataFrame,
                           resultados:pd.DataFrame, sim:bool) -> str:
    if hist.empty:return 'No hay observaciones en la celda según el maestro cargado.'
    anios=int(hist.fecha_utc.dt.year.nunique())
    partes=[f"La celda presenta anomalías térmicas FIRMS durante {anios} años distintos de los archivos incorporados."]
    if not b.empty:partes.append(f"Se cargaron {len(b)} registros terrestres en esta celda.")
    if not s.empty:partes.append(f"Se cargaron {len(s)} registros SINAE en esta celda.")
    if not resultados.empty and (resultados.n_firms>0).any():
        partes.append('El motor halló al menos una proximidad espacial y temporal que debe revisarse; no confirma un incendio.')
    elif not b.empty or not s.empty:
        partes.append('La ausencia de una coincidencia bajo los filtros actuales no demuestra que la detección sea falsa.')
    if sim:partes.append('IMPORTANTE: parte de la evidencia terrestre/institucional es SIMULADA.')
    partes.append('Los recuentos no están corregidos por revisitas, nubosidad ni diferencias MODIS–VIIRS.')
    return ' '.join(partes)


def _configuracion_automatica(st, raw:pd.DataFrame,prefijo:str, nombre:str) -> dict[str,str|None]:
    cols=list(raw.columns)
    config={key:encontrar_columna(cols,key) for key in ('fecha','hora','lat','lon','wkt','id','detalle','estado','origen')}
    if '__geo_lat' in cols: config['lat']='__geo_lat'
    if '__geo_lon' in cols: config['lon']='__geo_lon'
    auto=bool(config['fecha'] and ((config['lat'] and config['lon']) or config['wkt']))
    if auto:
        st.success(f"{nombre}: columnas de fecha y ubicación reconocidas automáticamente.")
    else:
        st.warning(f"{nombre}: faltan campos por identificar. Abrí «Ajustar columnas».")
    with st.expander(f"Ajustar columnas de {nombre} (opcional si aparece el aviso verde)",expanded=not auto):
        opciones=['— No disponible —']+cols
        etiquetas={"fecha":"Fecha / fecha y hora", "hora":"Hora separada", "lat":"Latitud WGS84", "lon":"Longitud WGS84",
                  "wkt":"Geometría WKT POINT alternativa", "id":"ID del evento",
                  "detalle":"Tipo / descripción", "estado":"Estado de la observación", "origen":"Organismo o procedencia"}
        for k in ('fecha','hora','lat','lon','wkt','id','detalle','estado','origen'):
            pred=config.get(k)
            o=st.selectbox(etiquetas[k],opciones,index=opciones.index(pred) if pred in opciones else 0,
                           key=f"fus_v2_map_{prefijo}_{k}")
            config[k]=None if o==opciones[0] else o
    return config


def _leer_fuente(st, uploaded, categoria:str,prefijo:str) -> pd.DataFrame:
    if uploaded is None:return pd.DataFrame()
    try:
        raw=leer_tabla_bytes(uploaded.name,uploaded.getvalue())
        cols=_configuracion_automatica(st,raw,prefijo,categoria.replace('_',' / '))
        tz_sugerido='UTC' if cols['fecha'] and 'utc' in canon(cols['fecha']) else 'America/Montevideo'
        with st.expander(f"Fecha, procedencia y controles de {categoria.replace('_',' / ')}"):
            tz=st.selectbox('Zona horaria si el archivo no incluye zona explícita',
                            ['America/Montevideo','UTC'],index=0 if tz_sugerido=='America/Montevideo' else 1,
                            key=f'fus_v2_tz_{prefijo}')
            marcado_auto=('simulad' in uploaded.name.lower() or 'sintet' in uploaded.name.lower())
            marcar=st.checkbox('Marcar como SIMULADO (datos de ensayo)',value=marcado_auto,
                               key=f'fus_v2_sim_{prefijo}')
        data,resumen=adaptar_externo(raw,categoria,cols,tz)
        if not data.empty and (marcar or marcado_auto):
            data['es_simulado']=True
            data['estado_origen']=data['estado_origen'].astype(str)+' · SIMULADO'
        if resumen['omitidos']:
            st.warning(f"{categoria}: {resumen['omitidos']} filas sin fecha o posición WGS84 válidas se excluyeron.")
        st.caption(f"{categoria}: {len(data)} registros válidos (de {resumen['leidos']})")
        return data
    except Exception as exc:
        st.error(f"{categoria}: {type(exc).__name__}: {exc}")
        return pd.DataFrame()


def mostrar_fusion_terrestre(maestro:pd.DataFrame|None=None) -> None:
    """Pestaña única para la integración del tridente y mapa exploratorio seleccionable.

    Llamada sin cambios desde el principal: mostrar_fusion_terrestre(combined)
    """
    import streamlit as st
    st.header('🌎 IGNIS | Mapa de fusión cielo–tierra')
    st.caption('NASA MODIS/VIIRS + evidencia terrestre Bomberos/PAIF + registros SINAE/MIRA')
    st.info('Prototipo exploratorio. No está conectado a Bomberos, PAIF ni MIRA; NO genera '
            'alertas operativas, NO predice incendios y NO despacha recursos.')
    try:
        nasa=normalizar_nasa(maestro)
        nasa=forzar_fechas_utc(nasa,'Maestro NASA')
    except Exception as exc:
        nasa=pd.DataFrame()
        st.error(f"No se pudo interpretar el Maestro: {type(exc).__name__}: {exc}")
    if nasa.empty:
        st.warning('Primero cargá el Maestro IGNIS en «Carga de datos» (pestaña 1). '
                   'También podés incorporar un CSV FIRMS adicional en «Fuentes de datos».')
    with st.expander('📁 Fuentes de datos · cargar NASA, Bomberos y SINAE',expanded=nasa.empty):
        st.caption('Si ya cargaste el Maestro en la primera pestaña, NO lo vuelvas a subir: '
                   'se recupera automáticamente aquí. Los archivos institucionales son opcionales.')
        nasa_extra=st.file_uploader('NASA FIRMS CSV/ZIP adicional (opcional; NO es necesario si usás el Maestro)',
                                   type=['csv','zip'],key='fus_v2_extra_nasa')
        if nasa_extra is not None:
            try:
                nuevo=normalizar_nasa(leer_firms_adicional(nasa_extra.name,nasa_extra.getvalue()))
                nasa=pd.concat([nasa,nuevo],ignore_index=True).drop_duplicates(
                    subset=['fecha_utc','lat','lon','instrumento']).reset_index(drop=True)
                nasa=forzar_fechas_utc(nasa,'NASA adicional').reset_index(drop=True)
                st.success(f"NASA listo: {len(nasa):,} observaciones únicas en el recorte amplio.")
            except Exception as exc:
                st.error(f"NASA adicional: {type(exc).__name__}: {exc}")
        cb,cs=st.columns(2)
        with cb:
            st.markdown('**Bomberos / PAIF**')
            b_file=st.file_uploader('CSV, JSON o GeoJSON de eventos terrestres',
                                    type=['csv','json','geojson'],key='fus_v2_bomberos')
            st.download_button('Descargar CSV sintético para ensayar',tabla_ejemplo('terrestre'),
                               file_name='IGNIS_BOMBEROS_DEMO_SIMULADO.csv',mime='text/csv',
                               key='fus_v2_plantilla_bomberos')
        with cs:
            st.markdown('**SINAE / MIRA**')
            s_file=st.file_uploader('CSV, JSON o GeoJSON de eventos institucionales',
                                    type=['csv','json','geojson'],key='fus_v2_sinae')
            st.download_button('Descargar CSV sintético para ensayar',tabla_ejemplo('sinae'),
                               file_name='IGNIS_SINAE_DEMO_SIMULADO.csv',mime='text/csv',
                               key='fus_v2_plantilla_sinae')
            st.markdown(f'[Dataset oficial histórico SINAE (2018–2022)]({FUENTE_MIRA})')
        b=_leer_fuente(st,b_file,'BOMBEROS_PAIF','b')
        s=_leer_fuente(st,s_file,'SINAE_MIRA','s')
        demo=st.checkbox('Añadir demostración con eventos terrestres SINTÉTICOS cerca de un punto NASA',
                         value=False,key='fus_v2_demo')
        if demo and not nasa.empty:
            b_demo,s_demo=demo_sintetica(nasa)
            b=pd.concat([b,b_demo],ignore_index=True)
            s=pd.concat([s,s_demo],ignore_index=True)
            st.warning('Se agregaron datos inventados para probar el motor. NO son señales reales de Bomberos o SINAE.')
    if nasa.empty:
        st.info('El mapa y los informes aparecerán cuando cargues al menos un archivo FIRMS real.')
        return

    # La visualización se centra en el mapa, no en la configuración de columnas.
    st.markdown('### 🗺️ Mapa histórico de Uruguay · elegí una cuadrícula')
    years=sorted(int(v) for v in nasa.fecha_utc.dt.year.dropna().unique())
    col_z,col_y=st.columns([2,1])
    zona=col_z.selectbox('Zona de consulta',list(ZONAS),key='fus_v2_zona')
    year_opt=col_y.selectbox('Período',['Histórico completo']+years,
                             index=0,key='fus_v2_anio')
    ano=year_opt if isinstance(year_opt,int) else None
    ver_torres=st.checkbox('Localidades vinculadas a la red costera de Bomberos (no torres verificadas)',
                          value=True,key='fus_v2_ver_refs')
    ver_casos=st.checkbox('Incendios documentados: puntos de referencia de localidades',
                         value=True,key='fus_v2_ver_casos')

    recorte=_recortar(nasa,zona)
    periodo=(recorte.loc[recorte.fecha_utc.dt.year==ano].copy()
             if ano is not None else recorte)
    hist_malla=_crear_malla(recorte)
    malla_periodo=_crear_malla(periodo)
    visible=hist_malla
    activas=None if ano is None else set(zip(malla_periodo.ilat.astype(int),malla_periodo.ilon.astype(int)))
    # Los casos en el mapa no representan el perímetro quemado ni la posición de inicio.
    b_zona=_recortar(b,zona) if not b.empty else b
    s_zona=_recortar(s,zona) if not s.empty else s
    b_vista=b_zona.loc[b_zona.fecha_utc.dt.year==ano].copy() if ano is not None and not b_zona.empty else b_zona
    s_vista=s_zona.loc[s_zona.fecha_utc.dt.year==ano].copy() if ano is not None and not s_zona.empty else s_zona
    mk1,mk2,mk3=st.columns(3)
    mk1.metric('Observaciones FIRMS en el período',f"{len(periodo):,}")
    mk2.metric('Años con datos en la zona',f"{recorte.fecha_utc.dt.year.nunique():,}")
    mk3.metric('Celdas visibles de 0,2°',f"{len(visible):,}")
    st.caption('Los colores representan AÑOS con al menos una detección térmica por celda, '
               'no cantidad de incendios. Los archivos del Maestro no cubren necesariamente todos los meses. '
               'No se corrige por diferencias instrumentales, nubosidad ni revisitas.')
    fig=_mapa_plotly(visible,periodo,b_vista,s_vista,zona,ano,ver_torres,ver_casos,activas)
    try:
        seleccion=st.plotly_chart(fig,use_container_width=True,on_select='rerun',
                                  selection_mode='points',key='fus_v2_click_'+str(zona)+str(ano))
    except TypeError:
        # Compatibilidad con ediciones antiguas de Streamlit sin selección nativa.
        st.plotly_chart(fig,use_container_width=True)
        seleccion=None
    clicked=_seleccion_de_grafico(seleccion)
    st.caption('◼ Azul: 3–5 años · Turquesa: 6–10 · Amarillo: 11–17 · Naranja: 18+ '
               '· ◇ Azul: LOCALIDAD de referencia (NO ubicación de cámara) '
               '· ○ Rosa: localidad de incendio documentado (NO punto exacto).')
    if ano is not None:
        st.caption('Las celdas con borde amarillo contienen observaciones en el año elegido; '
                   'el color interior conserva la recurrencia del histórico.')
    st.caption('Hacé clic sobre una celda coloreada. Si tu navegador no admite selección, '
               'elegila en el selector que aparece debajo.')

    # Si no hay observaciones dentro de la zona/período, no arriesgar un index inválido.
    if visible.empty:
        st.warning('No hay celdas con observaciones FIRMS para esa selección; '
                   'esto no demuestra que no ocurrieran incendios.')
        return
    opciones=list(zip(visible.ilat.astype(int),visible.ilon.astype(int)))
    key='fus_v2_celda'
    if clicked is not None and clicked in opciones:
        st.session_state[key]=clicked
    if key not in st.session_state or st.session_state[key] not in opciones:
        st.session_state[key]=opciones[0]
    seleccion_celda=st.selectbox('Cuadrícula para inspeccionar',opciones,
                  format_func=lambda k:_descripcion_celda(visible,k),key=key)

    lat0,lat1=seleccion_celda[0]*PASO_GRADOS,(seleccion_celda[0]+1)*PASO_GRADOS
    lon0,lon1=seleccion_celda[1]*PASO_GRADOS,(seleccion_celda[1]+1)*PASO_GRADOS
    t_hist=recorte.loc[recorte.lat.ge(lat0)&recorte.lat.lt(lat1)&
                       recorte.lon.ge(lon0)&recorte.lon.lt(lon1)].copy()
    t_per=t_hist.loc[t_hist.fecha_utc.dt.year==ano].copy() if ano is not None else t_hist
    def dentro_celda(df:pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:return pd.DataFrame()
        return df.loc[df.lat.ge(lat0)&df.lat.lt(lat1)&df.lon.ge(lon0)&df.lon.lt(lon1)].copy()
    bom_cell=dentro_celda(b_vista)
    sin_cell=dentro_celda(s_vista)
    st.markdown('### 🔎 Informe automático de la cuadrícula elegida')
    a,b1,c1=st.columns(3)
    a.metric('Detecciones en la celda',len(t_per))
    b1.metric('Años con actividad observada',t_hist.fecha_utc.dt.year.nunique())
    c1.metric('Días distintos observados',t_hist.fecha_utc.dt.date.nunique())
    st.caption(f"Perímetro aproximado: latitudes {lat0:.2f} a {lat1:.2f}; "
               f"longitudes {lon0:.2f} a {lon1:.2f} grados WGS84. "
               'Es una celda geográfica, NO una superficie quemada.')
    if not t_hist.empty:
        por_anio=t_hist.groupby(t_hist.fecha_utc.dt.year).size().rename('Observaciones').reset_index()
        por_anio.columns=['Año','Observaciones']
        instrumentos=t_per.groupby('instrumento').size().rename('Registros').reset_index()
        x1,x2=st.columns([1,1])
        with x1:
            st.markdown('**Histórico anual de la celda**')
            st.bar_chart(por_anio.set_index('Año'))
        with x2:
            st.markdown('**Sensores presentes en el período**')
            st.dataframe(instrumentos,use_container_width=True,hide_index=True)
    else:
        st.info('No hay datos satelitales en esta cuadrícula para el período activo.')
    st.markdown('**Antecedentes documentados cercanos (referencias, no verificación de cada píxel)**')
    centroid=(lat0+lat1)/2,(lon0+lon1)/2
    casos=[]
    for x in CASOS_DOCUMENTADOS:
        dist=float(haversine_vector(centroid[0],centroid[1],np.array([x['lat']]),np.array([x['lon']]))[0])
        if dist<=30 and (ano is None or int(x['inicio'][:4])<=ano<=int(x['fin'][:4])):
            casos.append((x,dist))
    if casos:
        for x,dist in casos:
            st.markdown(f"- **{x['nombre']}** · localidad a unos {dist:.1f} km del centro de la celda "
                        f"· [{x['fuente']} (fuente documental)]({x['url']})")
    else:
        st.caption('No hay un caso en nuestra pequeña biblioteca documental a menos de 30 km. '
                   'Eso NO significa ausencia de incendios o de registros institucionales.')

    st.markdown('### 🛰️ Fusión exploratoria NASA · Bomberos · SINAE')
    ca,cb,cc=st.columns(3)
    radio=ca.select_slider('Distancia máxima (km)',options=[1,3,5,10,15,20,30],value=10,
                            key='fus_v2_radio')
    horas=cb.select_slider('Separación máxima (h)',options=[1,3,6,12,24,48,72],value=24,
                           key='fus_v2_horas')
    dias=cc.selectbox('Si sólo hay fecha: margen (días)',[0,1],key='fus_v2_dias')
    # Motor sobre toda la zona/periodo (no solamente la celda), luego filtro por celda.
    ext_n=len(b_vista)+len(s_vista)
    if ext_n>2000:
        st.warning(f'{ext_n:,} eventos externos en la selección: por rendimiento analizamos '
                   'solo los 2.000 primeros, sin interpretar el resultado como exhaustivo.')
    bb=b_vista.head(1000) if not b_vista.empty else b_vista
    ss=s_vista.head(1000) if not s_vista.empty else s_vista
    if ext_n and not periodo.empty:
        try:
            fusion=fusionar(periodo,bb,ss,float(radio),float(horas),int(dias))
        except Exception as exc:
            st.error(f"Error controlado del motor: {type(exc).__name__}: {exc}. "
                     'Comprobá fecha, zona y tipos de columnas del CSV.')
            fusion=pd.DataFrame()
    elif ext_n:
        # Sin FIRMS igualmente se conservan las observaciones externas para revisión.
        try:
            fusion=fusionar(pd.DataFrame(),bb,ss,float(radio),float(horas),int(dias))
        except Exception as exc:
            st.warning(f'No se pudo calcular coincidencias: {exc}')
            fusion=pd.DataFrame()
    else:
        fusion=pd.DataFrame()
    if not fusion.empty:
        celda_fusion=fusion.loc[fusion.lat.ge(lat0)&fusion.lat.lt(lat1)&
                               fusion.lon.ge(lon0)&fusion.lon.lt(lon1)].copy()
        n_match=int((fusion.n_firms>0).sum())
        n_triple=int(fusion.resultado.astype(str).str.contains(r'NASA \+ terrestre \+ SINAE',regex=True).sum())
        xx,yy,zz=st.columns(3)
        xx.metric('Eventos externos en la zona',len(fusion))
        yy.metric('Con NASA próximo',n_match)
        zz.metric('Coincidencias triples',n_triple)
        if fusion.simulado.astype(str).str.startswith('SÍ').any():
            st.warning('Incluye registros sintéticos. Una coincidencia simulada prueba el cruce del software, '
                       'no la capacidad operativa de detectar incendios.')
        if not celda_fusion.empty:
            st.dataframe(celda_fusion,use_container_width=True,hide_index=True)
        else:
            st.info('No hay eventos externos cargados en la cuadrícula elegida; '
                    'las asociaciones de otras celdas se pueden descargar.')
        st.download_button('⬇️ Descargar resultados del tridente (CSV)',
            fusion.to_csv(index=False).encode('utf-8-sig'),
            file_name='IGNIS_FUSION_EXPLORATORIA_NO_OPERATIVA.csv',
            mime='text/csv',key='fus_v2_descargar_fusion')
        salida_local=celda_fusion
    else:
        salida_local=pd.DataFrame()
        st.info('Para comprobar coincidencias cargá un CSV terrestre/SINAE autorizado o '
                'activá la demostración sintética dentro de «Fuentes de datos». '
                'El mapa histórico funciona aunque no cargues archivos externos.')
    sim=bool((not bom_cell.empty and bom_cell.es_simulado.any()) or
             (not sin_cell.empty and sin_cell.es_simulado.any()))
    st.markdown('**Lectura de la celda:** '+_interpretacion_celda(t_hist,bom_cell,sin_cell,salida_local,sim))
    resumen=pd.DataFrame([{
        'lat_min':lat0,'lat_max':lat1,'lon_min':lon0,'lon_max':lon1,
        'anio_filtro':ano if ano is not None else 'TODOS',
        'observaciones_periodo':len(t_per),
        'anios_historicos':t_hist.fecha_utc.dt.year.nunique(),
        'dias_historicos':t_hist.fecha_utc.dt.date.nunique(),
        'registros_bomberos':len(bom_cell),'registros_sinae':len(sin_cell),
        'casos_documentados_cercanos':len(casos),
        'es_informe_operativo':False,
    }])
    st.download_button('⬇️ Descargar ficha de la celda (CSV)',
        resumen.to_csv(index=False).encode('utf-8-sig'),
        file_name='IGNIS_CELDA_ELEGIDA_EXPLORATORIA.csv',mime='text/csv',key='fus_v2_ficha')
    with st.expander('Metodología, procedencia y limitaciones'):
        st.markdown(
            f"- NASA FIRMS: histórico realmente incorporado al Maestro; no equivale a incendios confirmados.\n"
            f"- [Ministerio del Interior — red costera de Bomberos]({FUENTE_CAMARAS}): "
            "se documentan 20 cámaras, pero NO hay lista verificada de sus coordenadas en el proyecto. "
            "Los diamantes marcan centros de localidades de referencia, no torres ni radios reales de vigilancia.\n"
            f"- [SINAE/MIRA — catálogo CSV histórico 2018–2022]({FUENTE_MIRA}); "
            "los eventos pueden derivarse también de otras fuentes, incluso de observaciones espaciales.\n"
            "- Biblioteca de casos: ubicaciones aproximadas de LOCALIDADES y fechas documentadas; "
            "no se dispone de polígonos quemados, coordenadas de inicio ni cobertura exhaustiva.\n"
            "- PAIF: otra red de 65 cámaras forestales (temporada 2025–2026); no se afirma "
            "que haya ausencia de cobertura fuera de Colonia–Rocha.\n"
            "- La malla es de 0,2°; los colores indican años con alguna observación, no tasas de incendio. "
            "Los recortes de zona son APROXIMADOS, no límites departamentales.\n"
            "- La correlación se basa en coincidencia temporal y espacial configurable: "
            "no valida independencia de fuentes, precisión de sensores ni tiempos de alerta."
        )
