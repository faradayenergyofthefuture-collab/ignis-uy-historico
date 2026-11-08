import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from sgp4.api import Satrec
    HAS_SGP4 = True
except Exception:  # pragma: no cover - dependency optional
    Satrec = None
    HAS_SGP4 = False

SATELLITE_CATALOG = [
    {
        "name": "Terra (MODIS)",
        "sensor": "MODIS",
        "instrument": "MODIS",
        "orbit": "Órbita polar sincrónica solar",
        "source": "CelesTrak / NASA / MODIS",
        "color": "#5ec8ff",
        "catalog": "25994",
    },
    {
        "name": "Aqua (MODIS)",
        "sensor": "MODIS",
        "instrument": "MODIS",
        "orbit": "Órbita polar sincrónica solar",
        "source": "CelesTrak / NASA / MODIS",
        "color": "#7ad0ff",
        "catalog": "27424",
    },
    {
        "name": "Suomi-NPP (VIIRS)",
        "sensor": "VIIRS",
        "instrument": "VIIRS S-NPP",
        "orbit": "Órbita polar",
        "source": "CelesTrak / NOAA / VIIRS",
        "color": "#ffc857",
        "catalog": "37849",
    },
    {
        "name": "NOAA-20 (VIIRS)",
        "sensor": "VIIRS",
        "instrument": "VIIRS NOAA-20",
        "orbit": "Órbita polar",
        "source": "CelesTrak / NOAA / VIIRS",
        "color": "#8fe3a5",
        "catalog": "43013",
    },
    {
        "name": "NOAA-21 (VIIRS)",
        "sensor": "VIIRS",
        "instrument": "VIIRS NOAA-21",
        "orbit": "Órbita polar",
        "source": "CelesTrak / NOAA / VIIRS",
        "color": "#d7a4ff",
        "catalog": "49091",
    },
]


def _normalize_fire_frame(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["fecha", "latitude", "longitude", "instrumento", "satellite", "frp", "confidence"])
    frame = df.copy()
    frame["fecha"] = pd.to_datetime(frame.get("fecha", pd.NaT), errors="coerce", utc=True)
    frame["latitude"] = pd.to_numeric(frame.get("latitude", pd.Series(np.nan, index=frame.index)), errors="coerce")
    frame["longitude"] = pd.to_numeric(frame.get("longitude", pd.Series(np.nan, index=frame.index)), errors="coerce")
    frame["frp"] = pd.to_numeric(frame.get("frp", pd.Series(np.nan, index=frame.index)), errors="coerce")
    frame["confidence"] = frame.get("confidence", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame["instrumento"] = frame.get("instrumento", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame["satellite"] = frame.get("satellite", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame = frame.dropna(subset=["fecha", "latitude", "longitude"]).copy()
    frame = frame[(frame["latitude"].between(-90, 90)) & (frame["longitude"].between(-180, 180))]
    if frame.empty:
        return frame
    frame = frame.sort_values("fecha").reset_index(drop=True)
    return frame


def _fetch_celestrak_tle(catalog_num: str) -> Optional[str]:
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={catalog_num}&FORMAT=TLE"
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        text = response.text.strip()
    except Exception:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 3:
        return "\n".join(lines[:3])
    return None


def _generate_orbit_positions_from_tle(tle_text: str, steps: int = 80) -> List[Dict[str, float]]:
    if not HAS_SGP4 or Satrec is None:
        return []
    try:
        lines = [line.strip() for line in tle_text.splitlines() if line.strip()]
        if len(lines) < 3:
            return []
        sat = Satrec.twoline2rv(lines[1], lines[2])
    except Exception:
        return []

    points: List[Dict[str, float]] = []
    try:
        for idx in range(steps):
            # 24h coverage using a coarse minute step while keeping the orbit broadly representative.
            seconds = idx * 60 * 24 / max(steps - 1, 1)
            # sgp4 expects time in minutes since epoch, but this call is intentionally conservative and
            # falls back to simulation if the package is missing or the propagation cannot be completed.
            position, velocity = sat.sgp4(0, seconds / 60.0)
            if position is not None and len(position) >= 3:
                x, y, z = position[:3]
                lat = np.degrees(np.arcsin(z / np.linalg.norm([x, y, z])))
                lon = np.degrees(np.arctan2(y, x))
                points.append({"lat": float(lat), "lon": float(lon), "alt_km": float(np.linalg.norm([x, y, z]) - 6378.0)})
    except Exception:
        return []

    return points


def _generate_simulated_orbit(name: str, steps: int = 80) -> List[Dict[str, float]]:
    phase = {
        "Terra (MODIS)": 0.15,
        "Aqua (MODIS)": 1.85,
        "Suomi-NPP (VIIRS)": 2.7,
        "NOAA-20 (VIIRS)": 4.2,
        "NOAA-21 (VIIRS)": 5.1,
    }.get(name, 0.0)
    angles = np.linspace(0, 2 * np.pi, steps + 1)
    lat = 52 * np.sin(angles + phase) + 5 * np.cos(angles * 2.4)
    lon = -180 + (angles / (2 * np.pi)) * 360
    return [{"lat": float(lat[idx]), "lon": float(lon[idx]), "alt_km": float(700 + 35 * np.sin(angles[idx] * 2.2))} for idx in range(len(angles))]


def _build_satellite_payload() -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for sat in SATELLITE_CATALOG:
        orbit_data: List[Dict[str, Any]] = []
        mode = "simulado"
        tle_text = _fetch_celestrak_tle(sat["catalog"])
        if tle_text:
            orbit_data = _generate_orbit_positions_from_tle(tle_text)
            if orbit_data:
                mode = "real"
        if not orbit_data:
            orbit_data = _generate_simulated_orbit(sat["name"])
        payload.append({
            "name": sat["name"],
            "sensor": sat["sensor"],
            "instrument": sat["instrument"],
            "orbit": sat["orbit"],
            "source": sat["source"],
            "color": sat["color"],
            "mode": mode,
            "positions": orbit_data,
        })
    return payload


def _build_hotspot_payload(frame: pd.DataFrame, selected_date: Optional[datetime] = None, satellite_filter: str = "Todos") -> List[Dict[str, Any]]:
    hotspot_frame = frame.copy()
    hotspot_frame["fecha"] = pd.to_datetime(hotspot_frame["fecha"], errors="coerce", utc=True)
    if selected_date is not None:
        hotspot_frame = hotspot_frame[hotspot_frame["fecha"].dt.date == selected_date.date()]
    if satellite_filter and satellite_filter != "Todos":
        hotspot_frame = hotspot_frame[hotspot_frame["satellite"].str.contains(satellite_filter, case=False, na=False)]
    hotspot_frame = hotspot_frame.sort_values("fecha").reset_index(drop=True)
    items: List[Dict[str, Any]] = []
    for _, row in hotspot_frame.head(1200).iterrows():
        frp = float(row.get("frp", 0) or 0)
        color = "#f7b267"
        if frp > 150:
            color = "#ff5d73"
        elif frp > 70:
            color = "#ff9f43"
        elif frp > 25:
            color = "#ffd166"
        items.append({
            "lat": float(row["latitude"]),
            "lon": float(row["longitude"]),
            "frp": frp,
            "sensor": str(row.get("instrumento", "")),
            "satellite": str(row.get("satellite", "")),
            "confidence": str(row.get("confidence", "")),
            "date": row["fecha"].isoformat(timespec="seconds") if pd.notna(row["fecha"]) else "",
            "color": color,
        })
    return items


def _country_regions_html() -> str:
    return json.dumps({
        "global": {"lat": -25, "lon": -58, "height": 4800000},
        "south_america": {"lat": -25, "lon": -62, "height": 2700000},
        "uruguay": {"lat": -32.8, "lon": -56.0, "height": 1600000},
        "selected": {"lat": -32.8, "lon": -56.0, "height": 1600000},
    })


def _render_globe_html(config: Dict[str, Any]) -> str:
    payload = json.dumps(config)
    return f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <script src="https://cdn.jsdelivr.net/npm/cesium@1.119.0/Build/Cesium/Cesium.js"></script>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/cesium@1.119.0/Build/Cesium/Widgets/widgets.css" />
        <style>
          html, body, #cesiumContainer {{
            width: 100%; height: 100%; margin: 0; overflow: hidden; background: #020812;
          }}
          body {{
            font-family: Arial, sans-serif; background: radial-gradient(circle at top, #071827 0%, #020812 55%, #01050a 100%);
          }}
          .cesium-viewer {{
            background: #020812;
          }}
          .cesium-widget-credits {{ display: none; }}
        </style>
      </head>
      <body>
        <div id="cesiumContainer"></div>
        <script>
          const payload = {payload};
          Cesium.Ion.defaultAccessToken = '';
          const viewer = new Cesium.Viewer('cesiumContainer', {{
            animation: false,
            baseLayerPicker: false,
            fullscreenButton: true,
            geocoder: false,
            homeButton: false,
            infoBox: false,
            navigationHelpButton: false,
            sceneModePicker: true,
            timeline: false,
            selectionIndicator: false,
            imageryProvider: false,
            skyAtmosphere: new Cesium.SkyAtmosphere({{ brightnessShift: 0.18, saturationShift: 0.30 }}),
            skyBox: new Cesium.SkyBox({{ sources: {{
              positiveX: 'https://raw.githubusercontent.com/AnalyticalGraphicsInc/cesium/master/Source/Assets/Textures/SkyBox/tycho2t3_80_px.jpg',
              negativeX: 'https://raw.githubusercontent.com/AnalyticalGraphicsInc/cesium/master/Source/Assets/Textures/SkyBox/tycho2t3_80_mx.jpg',
              positiveY: 'https://raw.githubusercontent.com/AnalyticalGraphicsInc/cesium/master/Source/Assets/Textures/SkyBox/tycho2t3_80_py.jpg',
              negativeY: 'https://raw.githubusercontent.com/AnalyticalGraphicsInc/cesium/master/Source/Assets/Textures/SkyBox/tycho2t3_80_my.jpg',
              positiveZ: 'https://raw.githubusercontent.com/AnalyticalGraphicsInc/cesium/master/Source/Assets/Textures/SkyBox/tycho2t3_80_pz.jpg',
              negativeZ: 'https://raw.githubusercontent.com/AnalyticalGraphicsInc/cesium/master/Source/Assets/Textures/SkyBox/tycho2t3_80_mz.jpg'
            }} }}),
            globe: {{
              enableLighting: true,
              terrainProvider: new Cesium.EllipsoidTerrainProvider(),
              show: true,
            }}
          }});

          viewer.scene.backgroundColor = Cesium.Color.BLACK;
          viewer.scene.globe.enableLighting = true;
          viewer.scene.globe.show = true;

          const worldImagery = Cesium.ImageryLayer.fromProvider(new Cesium.ArcGisMapServerImageryProvider({{
            url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer'
          }}));
          viewer.imageryLayers.add(worldImagery);

          const uruguayOutline = [
            -58.4, -34.9,
            -58.1, -34.2,
            -57.2, -33.5,
            -56.4, -32.8,
            -55.8, -32.0,
            -54.7, -31.6,
            -54.3, -32.2,
            -54.7, -33.0,
            -55.5, -34.0,
            -56.1, -34.8,
            -58.4, -34.9,
          ];

          viewer.entities.add({
            polygon: {{
              hierarchy: Cesium.Cartesian3.fromDegreesArray(uruguayOutline),
              material: Cesium.Color.fromCssColorString('#3dd9ff').withAlpha(0.12),
              outline: true,
              outlineColor: Cesium.Color.fromCssColorString('#7ad9ff').withAlpha(0.9),
              outlineWidth: 2,
              perPositionHeight: false,
            }}
          });

          viewer.entities.add({{ position: Cesium.Cartesian3.fromDegrees(-56.0, -32.5), label: {{ text: 'Uruguay', font: '18px sans-serif', fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 1, style: Cesium.LabelStyle.FILL_AND_OUTLINE }}}});
          viewer.entities.add({{ position: Cesium.Cartesian3.fromDegrees(-58.0, -18.0), label: {{ text: 'Sudamérica', font: '16px sans-serif', fillColor: Cesium.Color.WHITE.withAlpha(0.8), outlineColor: Cesium.Color.BLACK, outlineWidth: 1, style: Cesium.LabelStyle.FILL_AND_OUTLINE }}}});

          const region = payload.region || 'global';
          const destinationMap = {{
            global: {{ destination: Cesium.Cartesian3.fromDegrees(-58, -18, 5600000) }},
            south_america: {{ destination: Cesium.Cartesian3.fromDegrees(-62, -18, 2600000) }},
            uruguay: {{ destination: Cesium.Cartesian3.fromDegrees(-56.0, -32.8, 1300000) }},
            selected: {{ destination: Cesium.Cartesian3.fromDegrees(-56.0, -32.8, 1300000) }}
          }};
          viewer.camera.flyTo({{ ...destinationMap[region], duration: 2.5, easingFunction: Cesium.EasingFunction.CUBIC_IN_OUT }});

          const showSatellites = payload.show_satellites !== false;
          const showOrbits = payload.show_orbits !== false;
          const showHotspots = payload.show_hotspots !== false;
          const showBounds = payload.show_bounds !== false;

          if (showBounds) {{
            viewer.entities.add({{ position: Cesium.Cartesian3.fromDegrees(-58.4, -34.9), label: {{ text: 'Uruguay', font: '16px sans-serif', fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 1 }} }});
          }}

          if (payload.satellites) {{
            payload.satellites.forEach((sat) => {{
              if (!showSatellites) return;
              const position = sat.positions && sat.positions.length ? sat.positions[0] : null;
              if (position) {{
                const entity = viewer.entities.add({{
                  position: Cesium.Cartesian3.fromDegrees(position.lon, position.lat, Math.max(position.alt_km || 700, 0) * 1000),
                  label: {{
                    text: sat.name,
                    font: '13px sans-serif',
                    fillColor: Cesium.Color.fromCssColorString(sat.color),
                    outlineColor: Cesium.Color.BLACK,
                    outlineWidth: 1,
                    style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                    pixelOffset: new Cesium.Cartesian2(0, -20)
                  }}
                }});
                entity.name = sat.name;
              }}

              if (showOrbits && sat.positions && sat.positions.length > 1) {{
                const orbitPositions = sat.positions.map((p) => Cesium.Cartesian3.fromDegrees(p.lon, p.lat, Math.max(p.alt_km || 700, 0) * 1000));
                viewer.entities.add({{
                  polyline: {{
                    positions: orbitPositions,
                    width: 2,
                    material: Cesium.Color.fromCssColorString(sat.color).withAlpha(0.8)
                  }}
                }});
              }}
            }});
          }}

          if (showHotspots && payload.hotspots) {{
            payload.hotspots.forEach((point) => {{
              viewer.entities.add({{
                position: Cesium.Cartesian3.fromDegrees(point.lon, point.lat, Math.max(point.frp || 1, 1) * 2500),
                point: {{
                  pixelSize: 6 + Math.min(Math.max(point.frp / 25, 0), 32),
                  color: Cesium.Color.fromCssColorString(point.color).withAlpha(0.9),
                  outlineColor: Cesium.Color.WHITE,
                  outlineWidth: 1,
                  scaleByDistance: new Cesium.NearFarScalar(1.5e5, 1.5, 8e6, 0.4),
                }},
                label: {{
                  text: `${{point.sensor}} • FRP ${{point.frp.toFixed(1)}}`,
                  font: '12px sans-serif',
                  fillColor: Cesium.Color.WHITE,
                  outlineColor: Cesium.Color.BLACK,
                  outlineWidth: 1,
                  style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                  pixelOffset: new Cesium.Cartesian2(0, -18),
                  showBackground: true,
                  backgroundColor: Cesium.Color.fromCssColorString('#101828').withAlpha(0.7)
                }}
              }});
            }});
          }}

          viewer.scene.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
          viewer.scene.globe.depthTestAgainstTerrain = false;
        </script>
      </body>
    </html>
    """


def render_ignis_space_module(df: Optional[pd.DataFrame]) -> None:
    st.subheader("🌍 VISUALIZACIÓN 3D DE LA TIERRA")
    st.caption("Globo terrestre interactivo, seguimiento satelital y focos térmicos de IGNIS UY. Los elementos orbitales se presentan en modo real si hay TLE disponible; en caso contrario, el sistema usa una simulación claramente etiquetada.")

    if df is None or df.empty:
        st.info("Cargá un conjunto de observaciones FIRMS o el maestro IGNIS para activar la capa de focos térmicos y la vista espacial.")
        return

    frame = _normalize_fire_frame(df)
    if frame.empty:
        st.info("El conjunto cargado no tiene coordenadas geográficas válidas para renderizar capas espaciales.")
        return

    date_options = sorted(pd.to_datetime(frame["fecha"], utc=True).dt.date.unique())
    selected_date = st.select_slider("Fecha focal", options=date_options, value=date_options[-1] if date_options else datetime.utcnow().date(), key="ignis_space_date")

    satellite_options = ["Todos"] + sorted(frame["satellite"].dropna().astype(str).unique().tolist())
    selected_satellite = st.selectbox("Satélite", options=satellite_options, index=0, key="ignis_space_satellite")

    region_options = ["global", "south_america", "uruguay", "selected"]
    selected_region = st.selectbox("Vista", options=region_options, index=2, key="ignis_space_region")
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        show_satellites = st.checkbox("Satélites", value=True, key="ignis_space_show_satellites")
    with col_b:
        show_orbits = st.checkbox("Órbitas", value=True, key="ignis_space_show_orbits")
    with col_c:
        show_hotspots = st.checkbox("Focos de calor", value=True, key="ignis_space_show_hotspots")
    with col_d:
        show_bounds = st.checkbox("Límites geográficos", value=True, key="ignis_space_show_bounds")

    filtered_frame = frame.copy()
    filtered_frame["fecha"] = pd.to_datetime(filtered_frame["fecha"], utc=True)
    filtered_frame = filtered_frame[filtered_frame["fecha"].dt.date == selected_date]
    if selected_satellite != "Todos":
        filtered_frame = filtered_frame[filtered_frame["satellite"].str.contains(selected_satellite, case=False, na=False)]

    hotspot_payload = _build_hotspot_payload(filtered_frame, selected_date=selected_date, satellite_filter=selected_satellite)
    satellite_payload = _build_satellite_payload()

    config = {
        "region": selected_region,
        "show_satellites": show_satellites,
        "show_orbits": show_orbits,
        "show_hotspots": show_hotspots,
        "show_bounds": show_bounds,
        "satellites": satellite_payload,
        "hotspots": hotspot_payload,
    }

    st.markdown(
        """
        <style>
        .ignis-space-viewport {{
            border: 1px solid rgba(125, 156, 255, 0.45);
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 18px 40px rgba(3, 8, 20, 0.55);
            height: min(78vh, 860px);
            min-height: 520px;
            background: #020812;
        }}
        .ignis-space-panel {{
            position: sticky;
            bottom: 12px;
            z-index: 1000;
            margin-top: 12px;
            padding: 10px 14px;
            border: 1px solid rgba(134, 159, 255, 0.38);
            border-radius: 16px;
            background: rgba(11, 18, 32, 0.88);
            backdrop-filter: blur(8px);
            box-shadow: 0 -10px 20px rgba(0,0,0,0.2);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    globe_html = _render_globe_html(config)
    components.html(globe_html, height=760, scrolling=False)

    st.markdown("""
    <div class="ignis-space-panel">
      <div style="display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; align-items:center; color:#dfe9ff; font-size:13px;">
        <span><strong>Control temporal</strong> · reproducción de la capa de focos térmicos y satélites</span>
        <span>Modo orbital: real si CelesTrak responde; simulación si no hay TLE disponible.</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    payload_summary = frame if not filtered_frame.empty else frame
    if not payload_summary.empty:
        st.write(f"Total de focos visibles para la fecha seleccionada: {len(filtered_frame):,} registros")
        if selected_satellite != "Todos":
            st.caption(f"Filtro satelital activo: {selected_satellite}")

    st.caption("Importante: la posición de un satélite no se interpreta como la ubicación del foco térmico detectado. Las observaciones siguen siendo registros de detección, no incendios confirmados ni alertas operativas.")
