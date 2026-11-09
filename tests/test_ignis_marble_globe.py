"""Comprueba texturas día/noche, etiquetas y JavaScript del globo de IGNIS.

Se extrae solamente el render HTML mediante AST para no iniciar Streamlit
ni hacer solicitudes externas en CI.
"""
import ast
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPACE = ROOT / "ignis_espacio.py"


def render_test_html():
    tree = ast.parse(SPACE.read_text(encoding="utf-8"), filename=str(SPACE))
    node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_render_globe_html"
    )
    module = ast.Module(body=[copy.deepcopy(node)], type_ignores=[])
    environment = {"Dict": dict, "Any": object, "json": json}
    exec(compile(module, str(SPACE), "exec"), environment)
    return environment["_render_globe_html"]({
        "region": "uruguay",
        "show_satellites": True,
        "show_orbits": True,
        "show_hotspots": True,
        "show_bounds": True,
        "show_clouds": True,
        "earth_visualization": "Blue Marble + Black Marble",
        "satellites": [],
        "hotspots": [],
    })


class GlobeMarbleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SPACE.read_text(encoding="utf-8")
        cls.html = render_test_html()

    def test_python_syntax(self):
        ast.parse(self.source)

    def test_correct_day_night_assets(self):
        self.assertIn("earth_atmos_4096.jpg", self.html)
        self.assertIn("earth_lights_2048.png", self.html)
        self.assertIn("earth_clouds_1024.png", self.html)
        self.assertNotIn("const blackMarbleUrl = 'https://threejs.org/examples/textures/planets/earth_normal_2048.jpg'", self.html)

    def test_shader_material_and_twilight(self):
        self.assertIn("new THREE.ShaderMaterial", self.html)
        self.assertIn("smoothstep(-0.12,0.22,solar)", self.html)
        self.assertIn("uniform int mode", self.html)
        self.assertIn("gl_FragColor=vec4(rgb,1.0)", self.html)
        self.assertIn("\\n' +", self.source)

    def test_satellite_names_display(self):
        self.assertIn("makeSatelliteLabel", self.html)
        self.assertIn("new THREE.CanvasTexture(canvas)", self.html)
        self.assertIn("new THREE.Sprite(", self.html)

    def test_texture_controls(self):
        self.assertIn('key="ignis_space_earth_style"', self.source)
        self.assertIn('key="ignis_space_show_clouds"', self.source)
        self.assertIn('"earth_visualization": earth_visualization', self.source)

    def test_no_texture_only_rotation(self):
        self.assertNotIn("earth.rotation.y +=", self.html)
        self.assertIn("controls.update()", self.html)

    def test_node_module_syntax(self):
        if not shutil.which("node"):
            self.skipTest("Node.js no disponible")
        match = re.search(
            r'<script type="module">([\s\S]*?)</script>', self.html
        )
        self.assertIsNotNone(match)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ignis-globe.mjs"
            path.write_text(match.group(1), encoding="utf-8")
            result = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True, text=True, timeout=15
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
