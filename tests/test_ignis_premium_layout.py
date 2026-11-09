"""Checks for the full-width, low-radius IGNIS visual design."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PremiumVisualLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.visual = (ROOT / "ignis_visual.py").read_text(encoding="utf-8")
        cls.main = (ROOT / "ignis_historico.py").read_text(encoding="utf-8")

    def test_python_syntax(self):
        for filename in ["ignis_visual.py", "ignis_historico.py"]:
            with self.subTest(filename=filename):
                ast.parse((ROOT / filename).read_text(encoding="utf-8"))

    def test_full_width_layout(self):
        self.assertIn("max-width:none!important", self.visual)
        self.assertIn("width:100%!important", self.visual)
        self.assertNotIn("max-width:1700px", self.visual)
        self.assertNotIn("max-width:1700px", self.main)

    def test_sharp_premium_geometry(self):
        self.assertIn("--ignis-radius-panel: 4px", self.visual)
        self.assertIn("--ignis-radius-control: 5px", self.visual)
        self.assertIn("border-radius:0;background:rgba", self.visual)
        self.assertIn("border:1px solid #315672;border-radius:0", self.visual)
        self.assertIn("box-shadow:none", self.visual)

    def test_mobile_padding_exists(self):
        self.assertIn("@media(max-width:850px)", self.visual)
        self.assertIn("padding:.8rem .65rem 1.75rem!important", self.visual)

    def test_existing_views_kept(self):
        for name in ["def render_project_home", "def render_control_center",
                     "def render_scientific_atlas", "def apply_visual_theme"]:
            self.assertIn(name, self.visual)
        self.assertIn("render_project_home(BASE, asset_uri", self.main)


if __name__ == "__main__":
    unittest.main()
