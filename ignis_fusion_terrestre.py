"""IGNIS UY · Fusión satelital-terrestre, versión piloto 1.1 (2026-11-05).

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
    salida["fecha_local"] = salida.fecha_utc.dt.tz_convert("America/Montevideo").dt.date
    return salida[columnas].reset_index(drop=True)


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
    # Preagrupar por día local para evitar producto cartesiano costoso.
    c = candidatos.copy()
    c["fecha_local"] = c.fecha_utc.dt.tz_convert("America/Montevideo").dt.date
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
    b = bomberos.reset_index(drop=True)
    s = sinae.reset_index(drop=True)
    x = pd.concat([b,s],ignore_index=True) if len(b)+len(s) else pd.DataFrame()
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


def configurar_columnas(st, df: pd.DataFrame, prefijo: str) -> dict[str,str|None]:
    cols=df.columns.tolist()
    opciones=["— No disponible —"]+cols
    resultado={}
    nombres={"fecha":"Fecha del evento", "hora":"Hora (si está separada)",
             "lat":"Latitud WGS84", "lon":"Longitud WGS84", "wkt":"WKT POINT alternativo",
             "id":"ID de evento", "detalle":"Tipo / descripción", "estado":"Estado de verificación",
             "origen":"Organismo / origen"}
    # Mapeo transparente sin asumir esquema propietario, incluye vista previa de columnas.
    with st.expander(f"Asignación de columnas {prefijo} · revisar antes de procesar",expanded=True):
        for campo in ("fecha","hora","lat","lon","wkt","id","detalle","estado","origen"):
            pred=encontrar_columna(cols,campo)
            if campo == "lat" and "__geo_lat" in cols:pred="__geo_lat"
            if campo == "lon" and "__geo_lon" in cols:pred="__geo_lon"
            valor=st.selectbox(nombres[campo],opciones,index=(opciones.index(pred) if pred in opciones else 0),
                               key=f"fus_{prefijo}_{campo}")
            resultado[campo]=None if valor==opciones[0] else valor
    return resultado


def mostrar_fusion_terrestre(maestro: pd.DataFrame | None = None) -> None:
    """Una sola pestaña Streamlit. Se invoca desde `with tabs[-1]:`."""
    import streamlit as st
    import streamlit.components.v1 as components

    st.header("🌎 Fusión cielo–tierra · piloto IGNIS")
    st.caption("NASA FIRMS + Bomberos/PAIF + SINAE/MIRA · motor de comparación exploratoria")
    st.info("El módulo NO está conectado a Bomberos, PAIF ni MIRA; admite cargas manuales "
            "autorizadas. NO predice incendios, NO verifica automáticamente humo, "
            "NO envía alarmas ni despacha drones.")
    st.markdown("**1 · NASA FIRMS — datos satelitales del Maestro IGNIS**")
    try:
        nasa=normalizar_nasa(maestro)
    except Exception as e:
        nasa=pd.DataFrame()
        st.error("No se pudo leer la tabla FIRMS actual: "+str(e))
    if nasa.empty:
        st.warning("Para correlacionar con satélites, cargá primero el Maestro IGNIS en la pestaña 1.")
    else:
        st.success(f"NASA FIRMS: {len(nasa):,} observaciones normalizadas en el recorte geográfico aproximado de Uruguay.")
        st.caption("Proceden de los archivos realmente cargados, no de una nueva conexión automática.")
    nrt=st.file_uploader("NASA FIRMS CSV/ZIP adicional (opcional: exportación NRT reciente)",
                         type=["csv","zip"],key="fus_nasa_nrt")
    if nrt is not None:
        try:
            nuevo=normalizar_nasa(leer_firms_adicional(nrt.name,nrt.getvalue()))
            antes=len(nasa)
            nasa=pd.concat([nasa,nuevo],ignore_index=True).drop_duplicates(
                subset=["fecha_utc","lat","lon","instrumento"],keep="first").reset_index(drop=True)
            st.success(f"NASA adicional: {len(nasa)-antes:,} registros netos. No se incorporan automáticamente al Maestro.")
        except Exception as e:
            st.error("NASA adicional no cargado: "+str(e))
    st.markdown("**2 · Entradas terrestres e institucionales**")
    c1,c2=st.columns(2)
    with c1:
        st.markdown("**Bomberos / PAIF**")
        file_b=st.file_uploader("Cargá eventos de cámaras / reportes autorizados",type=["csv","json","geojson"],key="fus_bom_file")
        st.download_button("Modelo CSV de evento terrestre (SINTÉTICO)",tabla_ejemplo("terrestre"),
                           "IGNIS_plantilla_terrestre_SIMULADA.csv",mime="text/csv",key="fus_bom_plantilla")
    with c2:
        st.markdown("**SINAE / MIRA**")
        file_s=st.file_uploader("Cargá el CSV oficial de MIRA u otro extracto autorizado",type=["csv","json","geojson"],key="fus_sin_file")
        st.download_button("Modelo CSV de registro SINAE (SINTÉTICO)",tabla_ejemplo("sinae"),
                           "IGNIS_plantilla_sinae_SIMULADA.csv",mime="text/csv",key="fus_sin_plantilla")
    st.markdown(f"**Fuente pública SINAE:** [Dataset de focos MIRA, 2018–2022]({FUENTE_MIRA}) · "
                "CSV histórico, último recurso publicado en 2022.")
    st.caption("El archivo oficial puede tener columnas diferentes al ejemplo: la pestaña permite mapearlas. "
               "La disponibilidad del CSV no implica permiso de acceso a sistemas internos.")

    b=pd.DataFrame();s=pd.DataFrame()
    for uploaded,categoria,prefijo in ((file_b,"BOMBEROS_PAIF","bom"),(file_s,"SINAE_MIRA","sin")):
        if uploaded is None:
            continue
        try:
            raw=leer_tabla_bytes(uploaded.name,uploaded.getvalue())
            st.caption(f"{categoria}: {len(raw):,} filas recibidas. Columnas: {', '.join(raw.columns[:18])}")
            config=configurar_columnas(st,raw,prefijo)
            tz=st.radio(f"Zona horaria de campos sin offset ({prefijo})",["America/Montevideo","UTC"],
                        horizontal=True,key=f"fus_tz_{prefijo}")
            data,conteo=adaptar_externo(raw,categoria,config,tz)
            simulado_por_defecto = categoria == "BOMBEROS_PAIF"
            marcar_simulado = st.checkbox(
                f"Identificar esta carga de {prefijo.upper()} como SIMULADA",
                value=simulado_por_defecto,
                help="Desmarcá solo si disponés de registros auténticos y autorizados. "
                     "Los ejemplos de prueba llevan marcadores SIMULADO incluso si desmarcás.",
                key=f"fus_sim_flag_{prefijo}",
            )
            if marcar_simulado and not data.empty:
                data["es_simulado"] = True
                data["estado_origen"] = data["estado_origen"].astype(str) + " · DEMOSTRACIÓN SINTÉTICA"
            if conteo["omitidos"]:
                st.warning(f"{categoria}: {conteo['omitidos']} filas omitidas por fecha o coordenadas no válidas. "
                           "Latitud/longitud deben ser grados WGS84; no se convierten coordenadas proyectadas.")
            st.success(f"{categoria}: {len(data):,} registros válidos para análisis.")
            if categoria=="BOMBEROS_PAIF":b=data
            else:s=data
        except Exception as e:
            st.error(f"{categoria}: {str(e)}")
    demo=st.checkbox("Mostrar una DEMOSTRACIÓN SINTÉTICA del motor (no son alertas reales)",
                     value=False,key="fus_demo")
    if demo:
        bb,ss=demo_sintetica(nasa)
        if bb.empty:
            st.warning("Cargá primero el Maestro para generar una coincidencia sintética controlada.")
        else:
            b=pd.concat([b,bb],ignore_index=True)
            s=pd.concat([s,ss],ignore_index=True)
            st.warning("MODO DEMOSTRACIÓN: se agregaron registros INVENTADOS cerca de una observación FIRMS real. "
                       "El resultado sirve para probar código, NO para demostrar capacidad de detección.")
    st.markdown("**3 · Comparación espacial y temporal**")
    a,c,d=st.columns(3)
    radio=a.slider("Distancia máxima (km)",min_value=1,max_value=30,value=10,key="fus_radio")
    horas=c.slider("Separación horaria máxima (h)",min_value=1,max_value=72,value=24,key="fus_horas")
    dias=d.selectbox("Sin hora: margen (días)",[0,1],index=0,key="fus_dias")
    st.caption("Si un registro solo contiene una fecha, la asociación se limita a días locales compatibles; "
               "NO se adjudican diferencias en minutos. Los umbrales son parámetros de exploración, "
               "no validación estadística.")
    if b.empty and s.empty:
        st.info("Cargá un CSV institucional o activá el modo de demostración para producir resultados.")
        return
    resultado=fusionar(nasa,b,s,float(radio),float(horas),int(dias))
    a,c,d=st.columns(3)
    a.metric("Registros externos procesados",len(resultado))
    c.metric("Con FIRMS cercano",int((resultado.n_firms>0).sum()) if len(resultado) else 0)
    d.metric("Terrestre + SINAE asociados",int((resultado.n_sinae>0).sum()) if len(resultado) else 0)
    if not resultado.empty and resultado.simulado.str.startswith("SÍ").any():
        st.error("Resultados incluyen eventos SINTÉTICOS. No los presentes como incendios observados o verificados.")
    st.dataframe(resultado,use_container_width=True,hide_index=True)
    st.download_button("⬇️ Descargar asociaciones exploratorias (CSV)",
                       resultado.to_csv(index=False).encode("utf-8-sig"),
                       file_name="IGNIS_fusion_exploratoria_NO_OPERATIVA.csv",mime="text/csv",
                       key="fus_csv_out")
    st.markdown("**4 · Mapa integrado**")
    try:
        html=dibujar_mapa(nasa,b,s,resultado)
        components.html(html,height=570,scrolling=False)
    except Exception as exc:
        st.error(f"No se pudo dibujar el mapa: {exc}")
    st.caption("Mapa de contexto, no cobertura real de cámaras. Celdas 0,2° = años con observaciones FIRMS; "
               "marcas de eventos = archivos cargados. No constituye evaluación territorial de riesgo.")
    st.warning("**Interpretación:** Coincidencia geográfica y temporal NO demuestra incendio ni "
               "independencia de fuentes. MIRA puede incluir registros cotejados previamente con FIRMS. "
               "Sin coincidencia FIRMS NO significa falsa alarma. No usar para despacho de emergencias.")
    with st.expander("Metodología, límites y fuentes verificables"):
        st.markdown(
            f"- NASA FIRMS: observaciones de los archivos cargados; no se calibran radiométricamente MODIS y VIIRS.\n"
            f"- SINAE/MIRA: [publicación oficial de datos históricos]({FUENTE_MIRA}); "
            f"la vigencia y la estructura concreta del recurso se verifican al cargar el archivo.\n"
            f"- Bomberos: [descripción institucional del sistema costero]({FUENTE_CAMARAS}). "
            f"No se conoce públicamente el formato de exportación del CAMI ni se accede a sus cámaras.\n"
            f"- PAIF: [65 cámaras forestales en temporada 2025–2026]({FUENTE_PAIF}); "
            f"no se asume un API público ni coordenadas exactas.\n"
            "- Las fuentes SINAE pueden incorporar reportes basados en FIRMS, de modo que no "
            "siempre constituyen validación independiente.\n"
            "- Una alerta operativa y una predicción exigirían validación formal, permisos, "
            "fiabilidad comprobada, análisis de latencias y protocolos institucionales."
        )
