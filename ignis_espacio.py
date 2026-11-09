import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
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
        "catalog": "54234",
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


def _parse_tle_pair(raw_text: str) -> Optional[tuple]:
    """Acepta TLE estándar de 2 líneas o 3LE con una línea de nombre."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    line1 = next((line for line in lines if line.startswith("1 ") and len(line) >= 60), None)
    line2 = next((line for line in lines if line.startswith("2 ") and len(line) >= 60), None)
    if not line1 or not line2:
        return None
    if line1[2:7].strip() != line2[2:7].strip():
        return None
    return line1, line2


def _fetch_celestrak_tle(catalog_num: str) -> Optional[str]:
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={catalog_num}&FORMAT=TLE"
    try:
        response = requests.get(url, timeout=(3, 4))
        response.raise_for_status()
        pair = _parse_tle_pair(response.text)
        return "\n".join(pair) if pair else None
    except requests.RequestException:
        return None


def _utc_to_jd_utc(dt: datetime) -> float:
    unix_seconds = dt.astimezone(timezone.utc).timestamp()
    return 2440587.5 + (unix_seconds / 86400.0)


def _generate_orbit_positions_from_tle(tle_text: str, steps: int = 80) -> List[Dict[str, float]]:
    if not HAS_SGP4 or Satrec is None:
        return []
    try:
        pair = _parse_tle_pair(tle_text)
        if not pair:
            return []
        sat = Satrec.twoline2rv(*pair)
    except Exception:
        return []

    points: List[Dict[str, float]] = []
    try:
        ref_dt = datetime.now(timezone.utc)
        for idx in range(steps):
            # Un tramo orbital de 105 minutos, no 24 h unidos por una sola línea.
            offset_minutes = idx * 105.0 / max(steps - 1, 1)
            sample_dt = ref_dt + timedelta(minutes=offset_minutes)
            jd_float = _utc_to_jd_utc(sample_dt)
            jd_int = int(math.floor(jd_float))
            jd_frac = jd_float - jd_int
            error, position, _ = sat.sgp4(jd_int, jd_frac)
            if error != 0 or position is None:
                continue
            x, y, z = position[:3]
            norm = float(np.linalg.norm([x, y, z]))
            if norm <= 0:
                continue
            theta = (280.46061837 + 360.98564736629 * (jd_float - 2451545.0) + 0.000387933 * ((jd_float - 2451545.0) ** 2)) % 360.0
            r_theta = math.radians(theta)
            x_rot = x * math.cos(r_theta) + y * math.sin(r_theta)
            y_rot = -x * math.sin(r_theta) + y * math.cos(r_theta)
            lat = math.degrees(math.asin(z / norm))
            lon = math.degrees(math.atan2(y_rot, x_rot))
            alt_km = norm - 6378.137
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue
            points.append({"lat": float(lat), "lon": float(lon), "alt_km": float(alt_km)})
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


@st.cache_data(ttl=3600, show_spinner=False)
def _build_satellite_payload(use_live_tle: bool = False) -> List[Dict[str, Any]]:
    """Renderiza inmediatamente en modo ilustrativo; TLE actuales bajo demanda.

    Los TLE consultados NO reconstruyen la fecha histórica de los puntos FIRMS.
    """
    fetched: Dict[str, Optional[str]] = {}
    if use_live_tle:
        # Cinco peticiones independientes a CelesTrak en paralelo.
        # El modo predeterminado evita cualquier espera de red.
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(
                _fetch_celestrak_tle,
                [sat["catalog"] for sat in SATELLITE_CATALOG],
            ))
        fetched = {sat["catalog"]: value
                   for sat, value in zip(SATELLITE_CATALOG, results)}

    payload: List[Dict[str, Any]] = []
    for sat in SATELLITE_CATALOG:
        positions: List[Dict[str, float]] = []
        tle_text = fetched.get(sat["catalog"])
        if tle_text:
            positions = _generate_orbit_positions_from_tle(tle_text)
        payload.append({
            "name": sat["name"],
            "sensor": sat["sensor"],
            "instrument": sat["instrument"],
            "orbit": sat["orbit"],
            "source": sat["source"],
            "color": sat["color"],
            "mode": "tle_actual" if positions else "ilustrativa",
            "positions": positions,
        })
    return payload


def _build_hotspot_payload(frame: pd.DataFrame, selected_date: Optional[datetime] = None, satellite_filter: str = "Todos") -> List[Dict[str, Any]]:
    hotspot_frame = frame.copy()
    hotspot_frame["fecha"] = pd.to_datetime(hotspot_frame["fecha"], errors="coerce", utc=True)
    if selected_date is not None:
        if hasattr(selected_date, "date"):
            selected_day = selected_date.date()
        else:
            selected_day = pd.Timestamp(selected_date).date()
        hotspot_frame = hotspot_frame[hotspot_frame["fecha"].dt.date == selected_day]
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
        <style>
          html, body {{
            width: 100%; height: 100%; margin: 0; overflow: hidden; background: #020812;
            font-family: Arial, sans-serif;
          }}
          #globe-shell {{
            position: relative; width: 100%; height: 100%; min-height: 640px; display: block; background: radial-gradient(circle at top, #071827 0%, #020812 55%, #01050a 100%);
            border-radius: 18px; overflow: hidden;
          }}
          #globe-root {{
            width: 100%; height: 100%; min-height: 640px; display: block; background: radial-gradient(circle at top, #071827 0%, #020812 55%, #01050a 100%);
          }}
          #ignis-globe-status {{
            position: absolute; left: 16px; top: 16px; z-index: 10;
            padding: 8px 12px; border-radius: 999px; font: 12px/1.2 Arial, sans-serif;
            color: #dfeaff; background: rgba(8, 16, 30, 0.75); border: 1px solid rgba(110, 138, 255, 0.65);
            backdrop-filter: blur(6px);
          }}
          .ignis-globe-watermark {{
            position:absolute; top:18px; right:18px; z-index:10;
            color:#effcff; padding:9px 13px; border-radius:11px;
            background:rgba(3,14,28,.75); border:1px solid rgba(61,180,223,.38);
            font:bold 12px Arial,sans-serif; letter-spacing:.09em;
            pointer-events:none;
          }}
          .ignis-globe-watermark span {{font-weight:400;color:#81cae5}}
          .ignis-globe-help {{
            position:absolute; bottom:19px; left:18px; z-index:10;
            color:#c8e0ef;padding:8px 12px;border-radius:10px;
            background:rgba(3,14,28,.76);font:12px Arial,sans-serif;
            pointer-events:none;
          }}
          canvas {{
            display: block; width: 100% !important; height: 100% !important;
          }}
        </style>
      </head>
      <body>
        <div id="globe-shell">
          <div id="ignis-globe-status">Preparando globo 3D...</div>
          <div class="ignis-globe-watermark">
            IGNIS UY <span>· EXPLORADOR 3D</span>
          </div>
          <div class="ignis-globe-help">Arrastrar para rotar · Rueda para acercar</div>
          <div id="globe-root"></div>
        </div>
        <script type="importmap">
          {{
            "imports": {{
              "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
              "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
            }}
          }}
        </script>
        <script type="module">
          import * as THREE from "three";
          import {{ OrbitControls }} from "three/addons/controls/OrbitControls.js";

          const payload = {payload};
          const status = document.getElementById('ignis-globe-status');
          const shell = document.getElementById('globe-shell');
          const root = document.getElementById('globe-root');
          const setStatus = (text, level = 'info') => {{
            status.textContent = text;
            status.style.borderColor = level === 'error' ? 'rgba(255, 124, 124, 0.8)' : 'rgba(110, 138, 255, 0.65)';
            status.style.color = level === 'error' ? '#ffd9d9' : '#dfeaff';
            status.style.background = level === 'error' ? 'rgba(44, 12, 14, 0.8)' : 'rgba(8, 16, 30, 0.75)';
          }};

          try {{
            if (!window.WebGLRenderingContext) {{
              throw new Error('WebGL no disponible en este navegador.');
            }}
            if (!root || !shell) {{
              throw new Error('No existe el contenedor de la vista 3D.');
            }}
            if (root.clientWidth < 50 || root.clientHeight < 50) {{
              throw new Error('El contenedor 3D tiene dimensiones inválidas.');
            }}

            setStatus('Cargando cartografía...');
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x020812);

            const camera = new THREE.PerspectiveCamera(35, root.clientWidth / root.clientHeight, 0.1, 2000);
            camera.position.set(0, 1.2, 6.4);

            const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
            renderer.setSize(root.clientWidth, root.clientHeight);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            root.appendChild(renderer.domElement);

            const controls = new OrbitControls(camera, renderer.domElement);
          controls.enableDamping = true;
          controls.dampingFactor = 0.06;
          controls.enablePan = false;
          controls.minDistance = 3.1;
          controls.maxDistance = 12;
          controls.enableZoom = true;
          controls.autoRotate = true;
          controls.autoRotateSpeed = 0.5;
          controls.target.set(-0.1, -0.25, 0);

          const ambient = new THREE.AmbientLight(0x9bbdff, 1.15);
          scene.add(ambient);

          const sunLight = new THREE.DirectionalLight(0xffffff, 1.8);
          sunLight.position.set(5, 3, 7);
          scene.add(sunLight);

          const starGeometry = new THREE.BufferGeometry();
          const starCount = 2200;
          const starPositions = new Float32Array(starCount * 3);
          for (let i = 0; i < starCount; i++) {{
            const radius = 25 + Math.random() * 18;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            starPositions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            starPositions[i * 3 + 1] = radius * Math.cos(phi);
            starPositions[i * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
          }}
          starGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
          const stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({{ color: 0xdfeaff, size: 0.08, transparent: true, opacity: 0.95 }}));
          scene.add(stars);

          const earthGroup = new THREE.Group();
          scene.add(earthGroup);

          const textureLoader = new THREE.TextureLoader();
          const blueMarbleUrl = 'https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg';
          const blackMarbleUrl = 'https://threejs.org/examples/textures/planets/earth_normal_2048.jpg';
          const earthTexture = textureLoader.load(blueMarbleUrl);
          const earthBump = textureLoader.load(blackMarbleUrl);
          const earth = new THREE.Mesh(
            new THREE.SphereGeometry(2.2, 96, 96),
            new THREE.MeshPhongMaterial({{
              map: earthTexture,
              bumpMap: earthBump,
              bumpScale: 0.12,
              shininess: 16,
              color: 0xdfeeff,
              emissive: new THREE.Color(0x071a2d),
              emissiveIntensity: 0.35
            }})
          );
          earthGroup.add(earth);

          earthTexture.onError = () => {{
            const fallback = textureLoader.load(blackMarbleUrl);
            earth.material.map = fallback;
            earth.material.needsUpdate = true;
          }};

          const atmosphere = new THREE.Mesh(
            new THREE.SphereGeometry(2.35, 96, 96),
            new THREE.MeshPhongMaterial({{
              color: 0x49a7ff,
              transparent: true,
              opacity: 0.18,
              side: THREE.BackSide
            }})
          );
          earthGroup.add(atmosphere);

          function latLonToVector3(lat, lon, radius) {{
            const phi = (90 - lat) * Math.PI / 180;
            const theta = (lon + 180) * Math.PI / 180;
            return new THREE.Vector3(
              -(radius * Math.sin(phi) * Math.cos(theta)),
              radius * Math.cos(phi),
              radius * Math.sin(phi) * Math.sin(theta)
            );
          }}

          const showSatellites = payload.show_satellites !== false;
          const showOrbits = payload.show_orbits !== false;
          const showHotspots = payload.show_hotspots !== false;
          const showBounds = payload.show_bounds !== false;

          if (showBounds) {{
            const uruguayPoints = [
              [-58.4, -34.9], [-58.1, -34.2], [-57.2, -33.5], [-56.4, -32.8], [-55.8, -32.0],
              [-54.7, -31.6], [-54.3, -32.2], [-54.7, -33.0], [-55.5, -34.0], [-56.1, -34.8]
            ].map(([lon, lat]) => latLonToVector3(lat, lon, 2.22));
            const outline = new THREE.BufferGeometry().setFromPoints(uruguayPoints);
            const outlineLine = new THREE.Line(
              outline,
              new THREE.LineBasicMaterial({{ color: 0x7ad9ff, transparent: true, opacity: 0.8 }})
            );
            earthGroup.add(outlineLine);
          }}

          // Anillos esquemáticos, SOLO cuando CelesTrak/SGP4 no aporta trayectoria.
          // No son órbitas verificadas ni posiciones de la fecha histórica FIRMS.
          function schematicOrbit(index) {{
            const r = 2.55;
            const inclination = 98 * Math.PI / 180;
            const node = index * Math.PI * 2 / 5;
            const result = [];
            for (let i = 0; i <= 128; i++) {{
              const t = (i / 128) * Math.PI * 2;
              const point = new THREE.Vector3(
                r * Math.sin(t) * Math.sin(inclination),
                r * Math.cos(t),
                r * Math.sin(t) * Math.cos(inclination)
              );
              point.applyAxisAngle(new THREE.Vector3(0, 1, 0), node);
              result.push(point);
            }}
            return result;
          }}

          let illustrativeOrbits = 0;
          let tleOrbits = 0;
          if (payload.satellites && (showSatellites || showOrbits)) {{
            payload.satellites.forEach((sat, index) => {{
              const color = new THREE.Color(sat.color);
              const valid = Array.isArray(sat.positions) && sat.positions.length >= 2;
              const schematic = !valid;
              const points = valid
                ? sat.positions.map((p) => latLonToVector3(
                    p.lat, p.lon, 2.2 * (1 + Math.max(0, Number(p.alt_km) || 0) / 6378.137)
                  ))
                : schematicOrbit(index);
              if (showOrbits) {{
                const orbitGeometry = new THREE.BufferGeometry().setFromPoints(points);
                const orbitMaterial = schematic
                  ? new THREE.LineDashedMaterial({{ color, transparent: true, opacity: 0.72, dashSize: 0.09, gapSize: 0.055 }})
                  : new THREE.LineBasicMaterial({{ color, transparent: true, opacity: 0.9 }});
                const orbitMesh = new THREE.Line(orbitGeometry, orbitMaterial);
                if (schematic) orbitMesh.computeLineDistances();
                earthGroup.add(orbitMesh);
                if (schematic) illustrativeOrbits++;
                else tleOrbits++;
              }}
              if (showSatellites) {{
                const marker = new THREE.Mesh(
                  new THREE.SphereGeometry(0.055, 16, 16),
                  new THREE.MeshBasicMaterial({{ color }})
                );
                marker.position.copy(points[0]);
                earthGroup.add(marker);
              }}
            }});
          }}

          if (showHotspots && payload.hotspots) {{
            payload.hotspots.forEach((point) => {{
              const mesh = new THREE.Mesh(
                new THREE.SphereGeometry(Math.min(0.08 + point.frp / 180, 0.2), 16, 16),
                new THREE.MeshBasicMaterial({{ color: new THREE.Color(point.color), transparent: true, opacity: 0.9 }})
              );
              mesh.position.copy(latLonToVector3(point.lat, point.lon, 2.31));
              earthGroup.add(mesh);
            }});
          }}

          const region = payload.region || 'global';
          if (region === 'uruguay') {{
            camera.position.set(0.9, 1.4, 5.5);
            controls.target.set(-0.2, -0.2, 0.1);
          }} else if (region === 'south_america') {{
            camera.position.set(1.9, 0.8, 5.4);
            controls.target.set(-0.6, -0.2, 0.1);
          }} else {{
            camera.position.set(0, 1.2, 6.4);
            controls.target.set(0, 0, 0);
          }}
          controls.update();

          const onResize = () => {{
            const width = root.clientWidth || 900;
            const height = root.clientHeight || 640;
            camera.aspect = width / height;
            camera.updateProjectionMatrix();
            renderer.setSize(width, height);
          }};
          window.addEventListener('resize', onResize);
          onResize();
          setTimeout(() => {{
            onResize();
            renderer.render(scene, camera);
          }}, 180);

          setStatus(payload.hotspots && payload.hotspots.length ? 'Cargando detecciones...' : '3D listo');

          function animate() {{
            requestAnimationFrame(animate);
            earth.rotation.y += 0.0018;
            atmosphere.rotation.y -= 0.0007;
            controls.update();
            renderer.render(scene, camera);
          }}
          animate();
          if (showOrbits && illustrativeOrbits > 0) {{
            setStatus('3D listo · órbitas punteadas ilustrativas (' + illustrativeOrbits + ')');
          }} else if (showOrbits && tleOrbits > 0) {{
            setStatus('3D listo · trayectorias TLE actuales');
          }} else {{
            setStatus('3D listo');
          }}
          }} catch (error) {{
            console.error('IGNIS 3D error:', error);
            const message = error && error.message ? error.message : 'Error no identificado al preparar la vista 3D.';
            setStatus('Error 3D: ' + message, 'error');
            if (root) {{
              root.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;padding:2rem;color:#fce5e5;text-align:center;font:14px Arial,sans-serif;background:linear-gradient(180deg,#0b1220,#090d18);">No se pudo inicializar la vista 3D. Revisa la compatibilidad WebGL del navegador o vuelve a cargar la página.</div>';
            }}
          }}
        </script>
      </body>
    </html>
    """


def render_ignis_space_module(df: Optional[pd.DataFrame]) -> None:
    """Espacio inmersivo: globo protagonista, controles laterales y fecha inferior."""
    st.markdown("""
    <style>
    .ignis-space-kicker{font-size:.76rem;font-weight:800;letter-spacing:.13em;
      color:#4fd1eb;text-transform:uppercase;margin-bottom:.4rem}
    .ignis-space-subtitle{color:#b5d1e3;font-size:.92rem;line-height:1.55;
      margin-bottom:1.1rem}
    .ignis-orbit-guide{background:linear-gradient(135deg,#102a45,#0b1b30);
      border:1px solid #326180;border-radius:14px;padding:13px 15px;
      font-size:.81rem;color:#c6deec;line-height:1.55}
    .ignis-orbit-guide strong{color:#f2fbff}
    </style>
    <div class="ignis-space-kicker">Explorador geoespacial · NASA FIRMS</div>
    <div class="ignis-space-subtitle">Navegá alrededor de la Tierra, compará
    las observaciones MODIS–VIIRS y explorá trayectorias satelitales.
    Las órbitas ilustrativas no representan pasadas históricas reales.</div>
    """, unsafe_allow_html=True)

    frame = _normalize_fire_frame(df)
    date_options = sorted(pd.to_datetime(frame["fecha"], utc=True).dt.date.unique())

    # La columna principal reserva el espacio del globo ANTES de mostrar
    # la línea temporal. El iframe se rellena luego de leer los filtros.
    controls_col, globe_col = st.columns([1, 3.1], gap="medium")
    with globe_col:
        globe_slot = st.empty()
        with st.container(border=True):
            st.caption("LÍNEA TEMPORAL · OBSERVACIONES FIRMS")
            if date_options:
                selected_date = st.select_slider(
                    "Fecha de observación", options=date_options,
                    value=date_options[-1], key="ignis_space_date",
                )
            else:
                selected_date = None
                st.caption("Sin fechas cargadas. El globo puede explorarse sin registros.")
            st.caption("La fecha cambia los focos térmicos, no los TLE actuales.")

    with controls_col:
        with st.container(border=True):
            st.markdown("#### 🛰️ Explorador orbital")
            st.caption("Configurá las capas del globo.")
            selected_region = st.selectbox(
                "Enfoque geográfico",
                options=["uruguay", "south_america", "global", "selected"],
                index=0, key="ignis_space_region",
                format_func=lambda item: {
                    "uruguay": "🇺🇾 Uruguay",
                    "south_america": "🌎 Sudamérica",
                    "global": "🌍 Tierra completa",
                    "selected": "📍 Zona seleccionada",
                }.get(item, item),
            )
            options = ["Todos"] + sorted(
                frame["satellite"].dropna().astype(str).unique().tolist()
            )
            selected_satellite = st.selectbox(
                "Filtrar observaciones", options=options, index=0,
                key="ignis_space_satellite",
            )
            st.caption("CAPAS VISIBLES")
            show_satellites = st.checkbox(
                "Satélites", value=True, key="ignis_space_show_satellites")
            show_orbits = st.checkbox(
                "Órbitas", value=True, key="ignis_space_show_orbits")
            show_hotspots = st.checkbox(
                "Focos térmicos", value=True, key="ignis_space_show_hotspots")
            show_bounds = st.checkbox(
                "Límites geográficos", value=True, key="ignis_space_show_bounds")
            orbit_mode = st.radio(
                "Fuente de trayectorias",
                ["Esquemas ilustrativos", "TLE actuales"],
                index=0, key="ignis_orbit_source",
                help="Los TLE actuales no reconstruyen órbitas en fechas históricas FIRMS.",
            )
        with st.container(border=True):
            st.caption("DATOS CARGADOS EN ESTA SESIÓN")
            q1, q2 = st.columns(2, gap="small")
            q1.metric("Registros", f"{len(frame):,}" if len(frame) else "—")
            q2.metric("Fechas", len(date_options))
            q3, q4 = st.columns(2, gap="small")
            q3.metric("Sensores", frame["instrumento"].nunique() if len(frame) else "—")
            q4.metric("Modo orbital", "TLE" if orbit_mode == "TLE actuales" else "Esquema")
        st.markdown(
            '<div class="ignis-orbit-guide"><strong>Cómo interpretar las líneas</strong>'
            '<p>— Continuas: trayectoria calculada con TLE reciente, cuando esté disponible.'
            '<p>┄ Punteadas: visualización ilustrativa, no una órbita validada.'
            '<p>Los puntos naranjas representan anomalías térmicas, no incendios confirmados.'
            '</div>', unsafe_allow_html=True,
        )

    filtered_frame = frame.copy()
    filtered_frame["fecha"] = pd.to_datetime(filtered_frame["fecha"], utc=True)
    if selected_date is not None:
        filtered_frame = filtered_frame[
            filtered_frame["fecha"].dt.date == selected_date
        ]
    else:
        filtered_frame = filtered_frame.iloc[0:0]
    if selected_satellite != "Todos":
        filtered_frame = filtered_frame[
            filtered_frame["satellite"].str.contains(
                selected_satellite, case=False, na=False)
        ]
    hotspots = _build_hotspot_payload(
        filtered_frame, selected_date=selected_date,
        satellite_filter=selected_satellite,
    )

    # La carga de TLE se hace por solicitud explícita. El modo normal no accede
    # a CelesTrak y el globo abre sin depender de esa red externa.
    use_live_tle = orbit_mode == "TLE actuales"
    if use_live_tle:
        with st.spinner("Cargando TLE actuales de CelesTrak…"):
            satellites = _build_satellite_payload(use_live_tle=True)
    else:
        satellites = _build_satellite_payload(use_live_tle=False)

    config = {
        "region": selected_region,
        "show_satellites": show_satellites,
        "show_orbits": show_orbits,
        "show_hotspots": show_hotspots,
        "show_bounds": show_bounds,
        "satellites": satellites,
        "hotspots": hotspots,
    }

    with globe_slot:
        components.html(_render_globe_html(config), height=690, scrolling=False)

    with globe_col:
        count = len(filtered_frame)
        st.caption(
            f"**{count:,} observaciones térmicas** para la fecha y sensor seleccionados. "
            "Modo orbital: TLE actuales si se solicitaron, de lo contrario esquemas "
            "ilustrativos. El globo permite arrastrar para rotar y desplazar la rueda "
            "para acercar."
        )
        if not frame.empty and frame["frp"].notna().any():
            with st.expander("Ver registros de la fecha seleccionada", expanded=False):
                fields = ["fecha", "latitude", "longitude", "instrumento",
                          "satellite", "frp", "confidence"]
                st.dataframe(filtered_frame[fields], use_container_width=True,
                             hide_index=True, height=260)

    st.caption(
        "Aviso científico: las trayectorias TLE son aproximaciones actuales y no "
        "corresponden a las fechas históricas FIRMS. Las trayectorias punteadas son "
        "únicamente esquemáticas. IGNIS no emite alertas oficiales."
    )
