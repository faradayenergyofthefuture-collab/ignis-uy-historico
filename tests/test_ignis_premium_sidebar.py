"""Pruebas estáticas para el panel lateral premium de IGNIS.

Validan la navegación y preservan claves de widgets existentes sin
iniciar Streamlit ni solicitar servicios externos.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PremiumSidebarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (ROOT / "ignis_historico.py").read_text(encoding="utf-8")
        cls.visual = (ROOT / "ignis_visual.py").read_text(encoding="utf-8")

    def test_python_compiles(self):
        for filename in ("ignis_historico.py", "ignis_visual.py"):
            with self.subTest(filename=filename):
                ast.parse((ROOT / filename).read_text(encoding="utf-8"))

    def test_navigation_state_stays_the_same(self):
        self.assertIn('st.session_state.setdefault("ignis_nav", NAV_PAGES[0])', self.main)
        self.assertIn('key=f"ignis_nav_{i:02d}"', self.main)
        self.assertIn('on_click=_ignis_navigate_to', self.main)
        self.assertIn("def _ignis_navigate_to(section: str)", self.main)

    def test_filters_still_use_existing_keys(self):
        for key in ("sidebar_region", "sidebar_sensores"):
            self.assertIn(f'key="{key}"', self.main)
        self.assertIn('st.session_state["region"] = region', self.main)
        self.assertIn('st.session_state["sensores"] = sensors', self.main)

    def test_sidebar_brand_and_resource_links(self):
        self.assertIn('asset_uri(BASE / "logo_ignis.png")', self.main)
        self.assertIn('class="ignis-side-brand"', self.main)
        self.assertIn("https://ema.fau.mil.uy/", self.main)
        self.assertIn("https://www.spaceappschallenge.org/2026/", self.main)

    def test_premium_navigation_and_keyboard_focus(self):
        self.assertIn(".ignis-side-brand", self.visual)
        self.assertIn('div[class*="st-key-ignis_nav_"] button[kind="primary"]', self.visual)
        self.assertIn('button:focus-visible', self.visual)
        self.assertIn("pointer-events:none", self.visual)
        self.assertNotIn("st.radio(", self.main)

    def test_no_duplicate_sidebar_rules_from_legacy_theme(self):
        self.assertNotIn("section[data-testid=\"stSidebar\"] div[role=\"radiogroup\"] label{", self.main)
        self.assertIn("apply_visual_theme()", self.main)

    def test_no_algorithm_changes(self):
        self.assertIn("def render_project_home", self.visual)
        self.assertIn("def render_control_center", self.visual)
        self.assertIn("def render_scientific_atlas", self.visual)
        self.assertIn("render_ignis_space_module", self.main)


if __name__ == "__main__":
    unittest.main()
