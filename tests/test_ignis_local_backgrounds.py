"""Regression tests: exact local image mapping for the IGNIS landing page.

No Streamlit runtime and no network calls are required.
"""
import ast
import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]

IMAGES = {
    "hero": "bg_portada.webp",
    "observaciones": "bg_observaciones.webp",
    "atlas": "bg_atlas.webp",
    "trazabilidad": "bg_trazabilidad.webp",
}


def isolated_background_fn(markdown):
    src = ROOT / "ignis_visual.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    fn = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef)
              and node.name == "_apply_local_home_backgrounds")
    namespace = {
        "Path": Path,
        "st": type("FakeStreamlit", (), {
            "markdown": staticmethod(markdown),
        }),
    }
    exec(compile(ast.Module(body=[copy.deepcopy(fn)], type_ignores=[]),
                 str(src), "exec"), namespace)
    return namespace["_apply_local_home_backgrounds"]


class HomeBackgroundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "ignis_visual.py").read_text(encoding="utf-8")

    def test_assets_are_real_binary_webp(self):
        for component, name in IMAGES.items():
            with self.subTest(component=component):
                asset = ROOT / "assets" / name
                self.assertTrue(asset.is_file(), msg=str(asset))
                data = asset.read_bytes()
                self.assertGreater(len(data), 40_000)
                self.assertEqual(data[0:4], b"RIFF")
                self.assertEqual(data[8:12], b"WEBP")

    def test_all_four_images_render_at_correct_places(self):
        css = []
        def fake_markdown(html, **kwargs):
            self.assertTrue(kwargs.get("unsafe_allow_html"))
            css.append(html)

        use_backgrounds = isolated_background_fn(fake_markdown)
        uri_map = use_backgrounds(
            ROOT,
            lambda path, mime: "data:" + mime + ";base64," + path.name
        )
        self.assertEqual(set(uri_map), set(IMAGES))
        self.assertEqual(len(css), 1)
        html = css[0]
        self.assertIn(".ignis-ui-hero {", html)
        for name in IMAGES.values():
            self.assertEqual(html.count("base64," + name), 1)
        self.assertIn("ignis-ui-card--heat", html)
        self.assertIn("ignis-ui-card--atlas", html)
        self.assertIn("ignis-ui-card--trace", html)

    def test_missing_assets_keep_fallback_without_crashing(self):
        css = []
        with TemporaryDirectory() as temporary:
            uri_map = isolated_background_fn(
                lambda html, **kwargs: css.append(html)
            )(Path(temporary), lambda path, mime: "data:" + mime + "," + path.name)
        self.assertEqual(uri_map, {})
        self.assertEqual(css, [])

    def test_images_are_optimized_not_external(self):
        self.assertIn('asset_uri(image_path, "image/webp")', self.source)
        self.assertNotIn("upload.wikimedia.org", self.source)
        self.assertNotIn("Black_Marble_Americas.jpg", self.source)
        self.assertIn("background-repeat:no-repeat!important;", self.source)
        self.assertIn("rgba(2,13,28,.94)", self.source)

    def test_scientific_disclaimer_and_legacy_fallback(self):
        self.assertIn("La escena espacial es ilustrativa.", self.source)
        self.assertIn("no fotografías satelitales fechadas", self.source)
        self.assertIn('"ignis_hero_premium.svg"', self.source)
        self.assertIn("def render_scientific_atlas", self.source)
        self.assertIn("def render_control_center", self.source)

    def test_buttons_keep_navigation_callbacks(self):
        for key in ("hero_to_history", "hero_to_dashboard", "hero_to_upload"):
            self.assertIn('key="' + key + '"', self.source)
        self.assertIn("on_click=navigate", self.source)

    def test_syntax(self):
        ast.parse(self.source)


if __name__ == "__main__":
    unittest.main()
