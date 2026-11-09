"""Regresiones: cuatro imágenes locales cargadas como fondo INLINE real.

Estas pruebas renderizan Inicio con un Streamlit simulado para verificar que
el HTML contenga cada WebP, no solo que una regla CSS separada se haya creado.
"""
import ast
import copy
from html import escape
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


class _Column:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeStreamlit:
    def __init__(self):
        self.html = []
        self.buttons = []
        self.captions = []

    def markdown(self, content, **kwargs):
        self.html.append(content)

    def columns(self, count, **kwargs):
        return [_Column() for _ in range(len(count) if isinstance(count, list) else count)]

    def button(self, label, **kwargs):
        self.buttons.append((label, kwargs))

    def caption(self, text):
        self.captions.append(text)


def isolate_home():
    path = ROOT / "ignis_visual.py"
    ast_tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"_home_background_image", "render_project_home"}
    nodes = [copy.deepcopy(node) for node in ast_tree.body
             if isinstance(node, ast.FunctionDef) and node.name in names]
    if len(nodes) != 2:
        raise AssertionError("No se pudieron aislar el render y su helper")
    runtime = {"Path": Path, "escape": escape, "_feature_icon": lambda name: "<svg/>"}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), runtime)
    return runtime


def render_home(base=ROOT):
    runtime = isolate_home()
    st = _FakeStreamlit()
    runtime["render_project_home"].__globals__["st"] = st
    runtime["render_project_home"](
        base, lambda path, mime="image/png": f"data:{mime};base64,{path.name}",
        [f"Página {i}" for i in range(15)],
        lambda page: None,
    )
    return st


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

    def test_four_images_are_on_the_actual_blocks(self):
        screen = render_home()
        html = "\n".join(screen.html)
        self.assertIn('class="ignis-ui-hero"><img class="ignis-bg-image ignis-bg-image--hero"', html)
        self.assertIn('class="ignis-ui-card ignis-ui-card--heat ignis-has-background"><img ', html)
        self.assertIn('class="ignis-ui-card ignis-ui-card--atlas ignis-has-background"><img ', html)
        self.assertIn('class="ignis-ui-card ignis-ui-card--trace ignis-has-background"><img ', html)
        for name in IMAGES.values():
            with self.subTest(asset=name):
                self.assertEqual(html.count("base64," + name), 1)
        self.assertNotIn("base64,ignis_hero_premium.svg", html)
        self.assertNotIn("base64,hero_espacio.jpg", html)
        self.assertEqual(html.count('class="ignis-bg-image '), 4)
        self.assertIn('aria-hidden="true"', html)
        self.assertIn('loading="eager"', html)
        self.assertIn('loading="lazy"', html)
        self.assertNotIn("background-image:linear-gradient(", html)

    def test_missing_images_fallback_to_svg_then_old_jpg(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            screen = render_home(base)
            html = "\n".join(screen.html)
            self.assertNotIn("data:image/webp", html)
            (base / "assets").mkdir()
            (base / "assets" / "ignis_hero_premium.svg").write_text("<svg/>")
            second = render_home(base)
            result = "\n".join(second.html)
            self.assertIn("base64,ignis_hero_premium.svg", result)
            self.assertIn("data:image/svg+xml", result)

    def test_images_are_not_external(self):
        self.assertNotIn("upload.wikimedia.org", self.source)
        self.assertNotIn("Black_Marble_Americas.jpg", self.source)
        self.assertIn("image/webp", self.source)
        self.assertIn("object-fit:cover!important;", self.source)
        self.assertIn("z-index:2!important;", self.source)
        self.assertIn("def _home_background_image", self.source)
        self.assertNotIn("def _home_image_style", self.source)

    def test_scientific_disclaimer_and_legacy_fallback(self):
        self.assertIn("La escena espacial es ilustrativa.", self.source)
        self.assertIn("no fotografías satelitales fechadas", self.source)
        self.assertIn('"ignis_hero_premium.svg"', self.source)
        self.assertIn("def render_scientific_atlas", self.source)
        self.assertIn("def render_control_center", self.source)


    def test_background_elements_use_actual_img_src_not_css_url(self):
        page = render_home()
        markup = "\n".join(page.html)
        self.assertEqual(markup.count('class="ignis-bg-image'), 4)
        for image_name in IMAGES.values():
            self.assertIn("src=\"data:image/webp;base64," + image_name + "\"", markup)
        self.assertNotIn('style="background-image:', markup)

    def test_decorative_images_are_below_text(self):
        self.assertIn("z-index:0!important;", self.source)
        self.assertIn("z-index:1!important;", self.source)
        self.assertIn("z-index:2!important;", self.source)
        self.assertIn(".ignis-ui-hero>:not(.ignis-bg-image)", self.source)
        self.assertIn(".ignis-ui-card.ignis-has-background>:not(.ignis-bg-image)", self.source)

    def test_buttons_keep_navigation_callbacks(self):
        screen = render_home()
        self.assertEqual(len(screen.buttons), 3)
        for _, kwargs in screen.buttons:
            self.assertEqual(kwargs.get("on_click") is not None, True)
        for key in ("hero_to_history", "hero_to_dashboard", "hero_to_upload"):
            self.assertIn('key="' + key + '"', self.source)

    def test_syntax(self):
        ast.parse(self.source)


if __name__ == "__main__":
    unittest.main()
