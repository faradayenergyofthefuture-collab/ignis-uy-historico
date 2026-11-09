"""Static regression checks for approved IGNIS landing concept."""
import ast
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


class PremiumLandingReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.visual=(ROOT/"ignis_visual.py").read_text(encoding="utf-8")
        cls.main=(ROOT/"ignis_historico.py").read_text(encoding="utf-8")
        cls.art=(ROOT/"assets"/"ignis_hero_premium.svg").read_text(encoding="utf-8")

    def test_python_syntax(self):
        for f in ["ignis_historico.py","ignis_visual.py"]:
            with self.subTest(file=f):
                ast.parse((ROOT/f).read_text(encoding="utf-8"))

    def test_svg_valid_and_descriptive(self):
        root=ET.fromstring(self.art)
        self.assertEqual(root.tag,"{http://www.w3.org/2000/svg}svg")
        self.assertIn("Tierra",root.attrib.get("aria-label",""))
        self.assertIn("Satellite",self.art) if "Satellite" in self.art else self.assertIn("satélite",self.art)
        self.assertIn("path",self.art)

    def test_hero_uses_new_artwork(self):
        self.assertIn("ignis_hero_premium.svg",self.visual)
        self.assertIn('asset_uri(hero_art, "image/svg+xml")',self.visual)
        self.assertIn("La escena espacial es ilustrativa",self.visual)

    def test_three_buttons_keep_callbacks(self):
        for key in ["hero_to_history","hero_to_dashboard","hero_to_upload"]:
            self.assertIn('key="'+key+'"',self.visual)
            self.assertIn('div.st-key-'+key+' button',self.visual)
        self.assertIn("on_click=navigate",self.visual)

    def test_sidebar_values_do_not_change(self):
        self.assertIn('st.session_state.setdefault("ignis_nav", NAV_PAGES[0])',self.main)
        self.assertIn('key=f"ignis_nav_{i:02d}"',self.main)
        self.assertIn("def _ignis_navigate_to(section: str)",self.main)
        self.assertNotIn("current_section = st.radio(",self.main)

    def test_line_icons_and_accessibility(self):
        self.assertIn("def _reference_styles",self.visual)
        self.assertIn("def _feature_icon",self.visual)
        self.assertIn("div.st-key-ignis_nav_{i - 1:02d} button::before",self.visual)
        self.assertIn("button:focus-visible",self.visual)
        self.assertIn('st.markdown(_reference_styles(),unsafe_allow_html=True)',self.visual)

    def test_visual_matches_reference_structure(self):
        for class_name in [
            "ignis-ui-topbar","ignis-ui-hero","ignis-ui-card--heat",
            "ignis-ui-card--atlas","ignis-ui-card--trace",
            "ignis-home-section-title",
        ]:
            self.assertIn(class_name,self.visual)
        self.assertIn("IGNIS UY<br><span>Histórico</span>",self.visual)
        self.assertIn("NASA Space Apps",self.visual)
        self.assertIn("ema.fau.mil.uy",self.visual)
        self.assertIn("min-height:421px",self.visual)
        self.assertIn("border-radius:3px",self.visual)

    def test_scientific_operations_untouched(self):
        self.assertIn("def render_control_center",self.visual)
        self.assertIn("def render_scientific_atlas",self.visual)
        self.assertIn("render_ignis_space_module",self.main)
        self.assertIn("st.session_state['combined'] = combined",self.main)
        self.assertNotIn("st.tabs(",self.main)


if __name__=="__main__":
    unittest.main()
