"""Pruebas del globo 3D: columnas de FRP, tooltip, órbitas animadas y contorno.

No inicia Streamlit ni hace solicitudes externas: si Streamlit no está
instalado se sustituye por un doble mínimo solo dentro de esta prueba.
"""
import ast
import copy
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPACE = ROOT / "ignis_espacio.py"


def _load_space_module():
    """Importa ignis_espacio con un Streamlit mínimo si hace falta."""
    added = []
    if importlib.util.find_spec("streamlit") is None:
        st = types.ModuleType("streamlit")
        st.cache_data = lambda *a, **k: (lambda fn: fn)
        components = types.ModuleType("streamlit.components")
        v1 = types.ModuleType("streamlit.components.v1")
        st.components = components
        components.v1 = v1
        for name, mod in (("streamlit", st), ("streamlit.components", components),
                          ("streamlit.components.v1", v1)):
            sys.modules[name] = mod
            added.append(name)
    try:
        spec = importlib.util.spec_from_file_location("ignis_espacio_3d_test", SPACE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name in added:
            sys.modules.pop(name, None)


def _render_html(config):
    tree = ast.parse(SPACE.read_text(encoding="utf-8"))
    node = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_render_globe_html")
    env = {"Dict": dict, "Any": object, "json": json}
    exec(compile(ast.Module(body=[copy.deepcopy(node)], type_ignores=[]),
                 str(SPACE), "exec"), env)
    return env["_render_globe_html"](config)


class Globe3DTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_space_module()
        cls.html = _render_html({
            "region": "uruguay", "show_satellites": True, "show_orbits": True,
            "show_hotspots": True, "show_bounds": True, "show_clouds": True,
            "earth_visualization": "Blue Marble + Black Marble",
            "satellites": [], "hotspots": [], "outline": [],
        })

    def test_hotspots_use_one_instanced_mesh(self):
        self.assertIn("new THREE.InstancedMesh(", self.html)
        self.assertNotIn("SphereGeometry(Math.min(0.08", self.html)

    def test_tooltip_ignores_hotspots_behind_earth(self):
        self.assertIn("intersectObjects([earth, hotspotMesh]", self.html)
        self.assertIn("tip.textContent", self.html)  # nunca innerHTML con datos
        self.assertNotIn("tip.innerHTML", self.html)

    def test_legend_and_orbit_controls_present(self):
        for ident in ("ignis-legend", "ignis-orbit-ctl", "ignis-play", "ignis-speed"):
            self.assertIn(ident, self.html)

    def test_outline_comes_from_payload_with_fallback(self):
        self.assertIn("payload.outline", self.html)
        self.assertIn("fallbackOutline", self.html)

    def test_tooltip_newline_is_valid_js(self):
        self.assertIn("join('\\n')", self.html)

    def test_node_module_syntax(self):
        if not shutil.which("node"):
            self.skipTest("Node.js no disponible")
        match = re.search(r'<script type="module">([\s\S]*?)</script>', self.html)
        self.assertIsNotNone(match)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ignis-globe.mjs"
            path.write_text(match.group(1), encoding="utf-8")
            result = subprocess.run(["node", "--check", str(path)],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_outline_loaded_from_geojson(self):
        ring = self.module._uruguay_outline()
        self.assertGreater(len(ring), 10)
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        self.assertTrue(-59 < min(lons) and max(lons) < -53)
        self.assertTrue(-35.5 < min(lats) and max(lats) < -30)

    def test_hotspot_cap_keeps_highest_frp_sorted_by_date(self):
        cap = self.module.MAX_HOTSPOTS_3D
        n = cap + 500
        frame = pd.DataFrame({
            "fecha": pd.date_range("2023-01-01", periods=n, freq="min", tz="UTC"),
            "latitude": [-32.5] * n,
            "longitude": [-56.0] * n,
            "frp": list(range(n)),
            "instrumento": ["VIIRS"] * n,
            "satellite": ["N"] * n,
            "confidence": ["n"] * n,
        })
        items = self.module._build_hotspot_payload(frame)
        self.assertEqual(len(items), cap)
        self.assertEqual(min(i["frp"] for i in items), float(n - cap))
        dates = [i["date"] for i in items]
        self.assertEqual(dates, sorted(dates))

    def test_no_cap_when_under_limit(self):
        frame = pd.DataFrame({
            "fecha": pd.date_range("2023-01-01", periods=10, freq="h", tz="UTC"),
            "latitude": [-32.5] * 10, "longitude": [-56.0] * 10,
            "frp": [5.0] * 10, "instrumento": ["MODIS"] * 10,
            "satellite": ["Terra"] * 10, "confidence": ["80"] * 10,
        })
        self.assertEqual(len(self.module._build_hotspot_payload(frame)), 10)


if __name__ == "__main__":
    unittest.main()
