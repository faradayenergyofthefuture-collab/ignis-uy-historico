"""Pruebas de regresión sin depender de Streamlit ni del acceso a CelesTrak.

Ejecutar: python -m unittest discover -s tests -v
"""
import ast
import copy
from pathlib import Path
from typing import Optional
import unittest

ROOT = Path(__file__).resolve().parents[1]


def extract_tle_parser():
    source = ROOT / "ignis_espacio.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    node = next(item for item in tree.body
                if isinstance(item, ast.FunctionDef) and item.name == "_parse_tle_pair")
    only_parser = ast.Module(body=[copy.deepcopy(node)], type_ignores=[])
    namespace = {"Optional": Optional}
    exec(compile(only_parser, str(source), "exec"), namespace)
    return namespace["_parse_tle_pair"]


TLE1 = "1 54234U 22150A   26310.83611733  .00000027  00000-0  33390-4 0  9993"
TLE2 = "2 54234  98.7192 247.2882 0002441 124.2915 235.8492 14.19557144206781"


class OrbitAndNavigationRegressionTests(unittest.TestCase):
    def test_tle_two_lines(self):
        self.assertEqual(extract_tle_parser()(TLE1 + "\n" + TLE2), (TLE1, TLE2))

    def test_tle_three_lines_with_name(self):
        self.assertEqual(extract_tle_parser()("NOAA-21\n" + TLE1 + "\n" + TLE2),
                         (TLE1, TLE2))

    def test_tle_rejects_inconsistent_catalog(self):
        self.assertIsNone(extract_tle_parser()(TLE1 + "\n" + TLE2.replace("54234", "43013")))

    def test_noaa21_correct_catalog(self):
        source = (ROOT / "ignis_espacio.py").read_text(encoding="utf-8")
        self.assertIn('"catalog": "54234"', source)
        self.assertNotIn('"catalog": "49091"', source)

    def test_navigation_uses_widget_callbacks(self):
        source = (ROOT / "ignis_historico.py").read_text(encoding="utf-8")
        self.assertIn("def _ignis_navigate_to(", source)
        self.assertEqual(source.count("on_click=_ignis_navigate_to"), 3)
        self.assertEqual(source.count('st.session_state["ignis_nav"] ='), 1)

    def test_source_syntax(self):
        for path in [ROOT / "ignis_historico.py", ROOT / "ignis_espacio.py"]:
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


if __name__ == "__main__":
    unittest.main()
