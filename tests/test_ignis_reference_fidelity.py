"""Regresión de fidelidad visual: navegación sin radios y fotografía nocturna."""
import ast
import copy
from pathlib import Path
import re
import unittest
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]


def generated_styles():
    path=ROOT/"ignis_visual.py"
    tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
    function=next(node for node in tree.body
                  if isinstance(node,ast.FunctionDef) and node.name=="_reference_styles")
    module=ast.Module(body=[copy.deepcopy(function)],type_ignores=[])
    context={}
    exec(compile(module,str(path),"exec"),context)
    return context["_reference_styles"]()


class IgnisReferenceFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main=(ROOT/"ignis_historico.py").read_text(encoding="utf-8")
        cls.visual=(ROOT/"ignis_visual.py").read_text(encoding="utf-8")
        cls.css=generated_styles()

    def test_source_parses(self):
        for name in ("ignis_historico.py","ignis_visual.py"):
            ast.parse((ROOT/name).read_text(encoding="utf-8"))

    def test_nav_is_fifteen_distinct_buttons_not_radio(self):
        self.assertNotIn("current_section = st.radio(",self.main)
        self.assertIn('key=f"ignis_nav_{i:02d}"',self.main)
        self.assertIn("for i, section in enumerate(NAV_PAGES):",self.main)
        self.assertIn("on_click=_ignis_navigate_to",self.main)
        self.assertIn('st.session_state.setdefault("ignis_nav", NAV_PAGES[0])',self.main)

    def test_exactly_one_icon_css_per_button(self):
        for i in range(15):
            target=f'div.st-key-ignis_nav_{i:02d} button::before'
            with self.subTest(index=i):
                self.assertEqual(self.css.count(target),1)
        self.assertNotIn("div:nth-child(1) label::after",self.css)

    def test_icons_unique_and_semantic(self):
        masks=re.findall(r'div\.st-key-ignis_nav_(\d{2}) button::before'
                         r'\{-webkit-mask-image:url\("data:image/svg\+xml,([^"]+)"\)',self.css)
        self.assertEqual(len(masks),15)
        self.assertEqual([int(index) for index,_ in masks],list(range(15)))
        self.assertEqual(len({url for _,url in masks}),15)
        # Dashboard has a grid and the upload page has an upload symbol.
        self.assertIn('rect',unquote(masks[1][1]))
        self.assertIn('path',unquote(masks[2][1]))

    def test_no_radio_controls_rendered(self):
        self.assertIn("button:focus-visible",self.visual)
        self.assertIn('button[kind="primary"]',self.visual)
        self.assertIn('st.button(',self.main)
        self.assertNotIn('label_visibility="collapsed"',self.main)

    def test_photo_background_with_vector_fallback_and_attribution(self):
        self.assertIn("Black_Marble_Americas.jpg",self.visual)
        self.assertIn('ignis_hero_premium.svg',self.visual)
        self.assertIn("NASA Earth Observatory / Suomi NPP VIIRS",self.visual)
        self.assertIn("no una",self.visual)

    def test_preserve_existing_navigation_and_science(self):
        self.assertIn('def _ignis_navigate_to(section: str)',self.main)
        for index in (0,1,2,4,6,14):
            self.assertIn(f"NAV_PAGES[{index}]",self.main)
        self.assertIn('key="sidebar_region"',self.main)
        self.assertIn('key="sidebar_sensores"',self.main)
        self.assertIn("render_scientific_atlas",self.visual)
        self.assertIn("render_control_center",self.visual)
        self.assertIn("render_ignis_space_module",self.main)


if __name__=="__main__":
    unittest.main()
