"""Regresión del menú con 15 iconos únicos y del hero SVG de IGNIS."""
import ast
import copy
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def render_reference_css():
    """Ejecuta solo _reference_styles sin importar Streamlit."""
    path = ROOT / "ignis_visual.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    func = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_reference_styles")
    module = ast.Module(body=[copy.deepcopy(func)], type_ignores=[])
    namespace = {}
    exec(compile(module, str(path), "exec"), namespace)
    return namespace["_reference_styles"]()


class PremiumIconAndHeroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.visual = (ROOT / "ignis_visual.py").read_text(encoding="utf-8")
        cls.main = (ROOT / "ignis_historico.py").read_text(encoding="utf-8")
        cls.svg = (ROOT / "assets" / "ignis_hero_premium.svg").read_text(
            encoding="utf-8"
        )
        cls.css = render_reference_css()

    def test_python_compiles(self):
        for name in ("ignis_historico.py", "ignis_visual.py"):
            with self.subTest(name=name):
                path = ROOT / name
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_svg_is_valid(self):
        root = ET.fromstring(self.svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(root.get("viewBox"), "0 0 1600 590")

    def test_sixteen_navigation_styles_are_not_needed(self):
        # Exactly 15 pages; prevents an extra/missing icon.
        nav_start = self.main.index("NAV_PAGES = [")
        nav_end = self.main.index("]\n", nav_start)
        nav_lines = self.main[nav_start:nav_end].splitlines()
        self.assertEqual(sum(line.strip().startswith('"') for line in nav_lines), 15)

    def test_each_icon_is_targeted_at_option_wrapper(self):
        for i in range(1, 16):
            selector = f'> div:nth-child({i}) label::after'
            fallback = f'> label:nth-child({i})::after'
            with self.subTest(i=i):
                self.assertIn(selector, self.css)
                self.assertIn(fallback, self.css)
        self.assertNotIn("f'label:nth-child({i})::after'", self.visual)

    def test_icons_are_distinct(self):
        # Each visual option should have a different embedded outline SVG.
        matches = re.findall(r'-webkit-mask-image:url\("data:image/svg\+xml,([^"]+)"\)', self.css)
        self.assertGreaterEqual(len(matches), 18)  # 15 menu + 3 actions
        self.assertEqual(len(set(matches[:15])), 15)

    def test_radio_circles_hidden_but_focus_visible(self):
        self.assertIn("clip-path:inset(50%)", self.visual)
        self.assertIn("label:focus-within", self.visual)
        self.assertIn('key="ignis_nav"', self.main)

    def test_enhanced_satellite_is_present(self):
        for detail in ("id=\"satBody\"", "id=\"cellShine\"",
                       "multilayer 3D chassis", "golden electronics",
                       "fill=\"url(#satBody)\"", "fill=\"url(#cellShine)\""):
            with self.subTest(detail=detail):
                self.assertIn(detail, self.svg)

    def test_planet_depth_without_fake_data(self):
        self.assertIn("id=\"terrainCloud\"", self.svg)
        self.assertIn("id=\"earthHighlights\"", self.svg)
        self.assertIn("Illustration deliberately stylized", self.svg)
        self.assertIn("La imagen espacial es ilustrativa", self.visual)

    def test_existing_routes_and_features_unchanged(self):
        for key in ("hero_to_history", "hero_to_dashboard", "hero_to_upload"):
            self.assertIn(f'key="{key}"', self.visual)
        self.assertIn("def render_scientific_atlas", self.visual)
        self.assertIn("def render_control_center", self.visual)
        self.assertIn("render_ignis_space_module", self.main)


if __name__ == "__main__":
    unittest.main()
