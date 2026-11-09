"""Regresiones estructurales de la interfaz A/B/C de IGNIS UY.

No requiere Streamlit ni acceso a servicios externos.
Ejecutar: python -m unittest discover -s tests -p 'test_ignis_visual.py' -v
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IgnisVisualSmokeTests(unittest.TestCase):

    def test_python_syntax(self):
        for filename in ["ignis_historico.py", "ignis_visual.py"]:
            with self.subTest(filename=filename):
                path = ROOT / filename
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_expected_views_are_separate_functions(self):
        tree = ast.parse((ROOT / "ignis_visual.py").read_text(encoding="utf-8"))
        defined = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        expected = {"apply_visual_theme", "render_project_home",
                    "render_control_center", "render_scientific_atlas"}
        self.assertTrue(expected.issubset(defined))

    def test_main_app_wires_all_three(self):
        content = (ROOT / "ignis_historico.py").read_text(encoding="utf-8")
        self.assertIn("render_project_home(BASE, asset_uri", content)
        self.assertIn("render_control_center(combined, sample, selected", content)
        self.assertIn("render_scientific_atlas(sample, selected", content)
        self.assertNotIn("st.tabs(", content)

    def test_navigation_uses_callbacks(self):
        content = (ROOT / "ignis_visual.py").read_text(encoding="utf-8")
        self.assertIn("on_click=navigate", content)
        self.assertNotIn('st.session_state["ignis_nav"]', content)

    def test_uses_existing_assets(self):
        for name in ["logo_ignis.png", "hero_espacio.jpg", "uruguay_contorno.geojson"]:
            self.assertTrue((ROOT / name).exists(), msg=name)

    def test_no_fabricated_hotspots(self):
        content = (ROOT / "ignis_visual.py").read_text(encoding="utf-8")
        self.assertIn("if sample.empty:", content)
        self.assertIn("if not view.empty:", content)
        self.assertIn("map_fn(mapped", content)
        self.assertIn("La ausencia de registros", content)

    def test_official_links(self):
        content = (ROOT / "ignis_visual.py").read_text(encoding="utf-8")
        self.assertIn("https://ema.fau.mil.uy/", content)
        self.assertIn("https://www.spaceappschallenge.org/2026/", content)

    def test_theme_is_cyan(self):
        config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('primaryColor = "#27B9D9"', config)


if __name__ == "__main__":
    unittest.main()
